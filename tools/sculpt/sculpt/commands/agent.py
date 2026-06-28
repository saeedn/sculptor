import asyncio
import datetime
import functools
import json
import os

import httpx
import typer
import websockets.exceptions

from sculpt.auth import get_authenticated_client
from sculpt.auth import get_default_base_url
from sculpt.client import Client
from sculpt.client.api.default import create_workspace_agent
from sculpt.client.api.default import delete_workspace_agent
from sculpt.client.api.default import list_workspace_agents
from sculpt.client.api.default import post_agent_terminal_input
from sculpt.client.api.default import rename_workspace_agent
from sculpt.client.models.coding_agent_task_view import CodingAgentTaskView
from sculpt.client.models.create_agent_request import CreateAgentRequest
from sculpt.client.models.http_validation_error import HTTPValidationError
from sculpt.client.models.rename_agent_request import RenameAgentRequest
from sculpt.client.models.terminal_input_request import TerminalInputRequest
from sculpt.client.models.task_status import TaskStatus
from sculpt.client.types import UNSET
from sculpt.commands._follow_helpers import get_session_token_safe
from sculpt.commands._follow_helpers import handle_exit_reason
from sculpt.commands._follow_helpers import on_reconnect_json
from sculpt.commands._follow_helpers import on_reconnect_text
from sculpt.commands._follow_helpers import on_status_json
from sculpt.commands._harness_helpers import resolve_harness_selection
from sculpt.commands.data_types import AgentCreateOutput
from sculpt.commands.data_types import AgentDeleteOutput
from sculpt.commands.data_types import AgentListItem
from sculpt.commands.data_types import AgentRenameOutput
from sculpt.commands.data_types import AgentSendOutput
from sculpt.commands.data_types import AgentShowOutput
from sculpt.commands.data_types import AgentStatusOutput
from sculpt.formatting import cli_error
from sculpt.formatting import format_datetime
from sculpt.formatting import format_table
from sculpt.formatting import handle_connection_error
from sculpt.formatting import is_tty
from sculpt.formatting import overwrite_lines
from sculpt.formatting import truncate
from sculpt.resolve import resolve_agent_id
from sculpt.resolve import resolve_by_prefix
from sculpt.resolve import resolve_project
from sculpt.resolve import resolve_workspace_id
from sculpt.ws_client import AgentNotFoundError
from sculpt.ws_client import AgentSnapshot
from sculpt.ws_client import ScopeForbiddenError
from sculpt.ws_client import ScopeMalformedError
from sculpt.ws_client import ScopeNotFoundError
from sculpt.ws_client import fetch_agent_state
from sculpt.ws_client import fetch_all_agents
from sculpt.ws_client import follow_agent

agent_app = typer.Typer(
    name="agent",
    help="Manage agents.",
)

# Display widths for the `list` table and the `send --json` message echo.
_ID_DISPLAY_PREFIX_LENGTH = 11
_TITLE_DISPLAY_MAX_LENGTH = 40
_MESSAGE_PREVIEW_MAX_LENGTH = 100


def resolve_workspace(workspace: str | None, client: Client, json_output: bool) -> str:
    """Resolve workspace from flag or env var, with prefix resolution."""
    if workspace is not None:
        return resolve_workspace_id(client, workspace, json_output)
    env_value = os.environ.get("SCULPT_WORKSPACE_ID")
    if env_value is not None:
        return resolve_workspace_id(client, env_value, json_output)
    cli_error("--workspace is required (or set SCULPT_WORKSPACE_ID)", json_output=json_output)


def _get_task_title(task: CodingAgentTaskView) -> str:
    return task.title or "Untitled agent"


def _format_snapshot_datetime(iso_str: str) -> str:
    """Format an ISO datetime string for display."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return format_datetime(dt)
    except (ValueError, TypeError):
        return iso_str


@agent_app.command("create")
def create(
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace ID (or set SCULPT_WORKSPACE_ID)"),
    name: str | None = typer.Option(None, "--name", help="Agent name"),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help=(
            "Harness to create: Terminal, or a registered terminal agent by name"
            + " (e.g. 'Claude CLI'). If omitted, the server uses your"
            + " most-recently-used harness from the Sculptor app."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Create a new agent in a workspace (use `sculpt run` to also send a prompt)."""
    base_url = base_url or get_default_base_url()

    client = get_authenticated_client(base_url)
    workspace_id = resolve_workspace(workspace, client, json_output)

    selection = resolve_harness_selection(harness, client, json_output)

    request = CreateAgentRequest(
        name=name,
        agent_type=selection.agent_type if selection is not None else UNSET,
        registration_id=(
            selection.registration_id
            if selection is not None and selection.registration_id is not None
            else UNSET
        ),
    )

    try:
        result = create_workspace_agent.sync(workspace_id=workspace_id, client=client, body=request)
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if result is None:
        cli_error("Failed to create agent", detail="No response from server", json_output=json_output)

    if isinstance(result, HTTPValidationError):
        cli_error("Validation error", detail=str(result), json_output=json_output)

    if json_output:
        output = AgentCreateOutput(
            id=result.id,
            title=_get_task_title(result),
            status=result.status.value,
            workspace_id=result.workspace_id,
            created_at=result.created_at.isoformat(),
        )
        typer.echo(output.model_dump_json(indent=2))
        return

    typer.echo(f"Agent created: {result.id}")
    typer.echo(f"Status: {result.status.value}")


@agent_app.command("list")
def list_cmd(
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace ID (or set SCULPT_WORKSPACE_ID)"),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status (BUILDING, ERROR, READY, RUNNING)"),
    show_all: bool = typer.Option(False, "--all", help="List agents across all workspaces"),
    repo: str | None = typer.Option(None, "--repo", help="Path to the repository"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """List agents."""
    base_url = base_url or get_default_base_url()

    valid_statuses = [s.value for s in TaskStatus]
    if status is not None:
        status = status.upper()
        if status not in valid_statuses:
            cli_error(f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}", json_output=json_output)

    session_token = get_session_token_safe(base_url, json_output)

    # Choose the connect-time scope. Precedence: --all > --workspace / env > per-project default.
    ws_id = workspace or os.environ.get("SCULPT_WORKSPACE_ID")
    if show_all:
        scope = "all"
    elif ws_id:
        client = get_authenticated_client(base_url)
        resolved_ws_id = resolve_workspace_id(client, ws_id, json_output)
        scope = f"workspace:{resolved_ws_id}"
    else:
        client = get_authenticated_client(base_url)
        project_id = resolve_project(repo, client)
        scope = f"project:{project_id}"

    try:
        agents = fetch_all_agents(base_url, session_token, scope=scope)
    except ScopeNotFoundError:
        cli_error(f"Scope target not found: {scope}", json_output=json_output)
    except ScopeForbiddenError:
        cli_error(f"Not authorized to view scope: {scope}", json_output=json_output)
    except ScopeMalformedError as e:
        cli_error(f"Invalid scope: {e}", json_output=json_output)
    except (OSError, websockets.exceptions.WebSocketException):
        cli_error("Could not connect to Sculptor server", json_output=json_output)

    if status is not None:
        agents = [a for a in agents if a.status == status]

    agents.sort(key=lambda t: t.created_at, reverse=True)

    if json_output:
        items = [
            AgentListItem(
                id=t.task_id,
                title=t.title or t.task_id,
                status=t.status,
                workspace_id=t.workspace_id,
                created_at=t.created_at,
            )
            for t in agents
        ]
        typer.echo(json.dumps([item.model_dump() for item in items], indent=2))
        return

    if not agents:
        typer.echo("No agents found.")
        return

    headers = ["ID", "STATUS", "WORKSPACE", "CREATED", "TITLE"]
    rows = [
        [
            t.task_id[:_ID_DISPLAY_PREFIX_LENGTH],
            t.status,
            t.workspace_id[:_ID_DISPLAY_PREFIX_LENGTH],
            _format_snapshot_datetime(t.created_at),
            truncate(t.title or t.task_id, _TITLE_DISPLAY_MAX_LENGTH),
        ]
        for t in agents
    ]
    typer.echo(format_table(headers, rows))


def _fetch_agents_for_workspace(
    client: Client, workspace_id: str, json_output: bool
) -> list[CodingAgentTaskView]:
    try:
        result = list_workspace_agents.sync(workspace_id=workspace_id, client=client)
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if result is None:
        cli_error("Failed to list agents", detail="No response from server", json_output=json_output)

    if isinstance(result, HTTPValidationError):
        cli_error("Validation error", detail=str(result), json_output=json_output)

    return [a for a in result if isinstance(a, CodingAgentTaskView)]



@agent_app.command("show")
def show(
    agent_id: str = typer.Argument(..., help="Agent ID or prefix"),
    timeout: float = typer.Option(30.0, "--timeout", help="Timeout in seconds for WebSocket connection"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Show details of an agent."""
    base_url = base_url or get_default_base_url()
    full_agent_id = resolve_agent_id(base_url, agent_id, json_output)
    snapshot = _fetch_snapshot(base_url, full_agent_id, timeout, json_output)

    if json_output:
        output = AgentShowOutput(
            id=snapshot.task_id,
            title=snapshot.title or "Untitled",
            status=snapshot.status,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            repo_id=snapshot.project_id,
            workspace_id=snapshot.workspace_id,
            is_deleted=snapshot.is_deleted,
            error_detail=snapshot.error_detail,
        )
        typer.echo(output.model_dump_json(indent=2))
        return

    created_dt = datetime.datetime.fromisoformat(snapshot.created_at)
    updated_dt = datetime.datetime.fromisoformat(snapshot.updated_at)

    lines = [
        f"Agent: {snapshot.task_id}",
        f"Title: {snapshot.title or 'Untitled'}",
        f"Status: {snapshot.status}",
        f"Created: {format_datetime(created_dt)}",
        f"Updated: {format_datetime(updated_dt)}",
        f"Repo ID: {snapshot.project_id}",
        f"Workspace ID: {snapshot.workspace_id}",
    ]
    if snapshot.error_detail:
        lines.append(f"Error: {snapshot.error_detail}")
    typer.echo("\n".join(lines))


@agent_app.command("rename")
def rename(
    agent_id: str = typer.Argument(..., help="Agent ID or prefix"),
    title: str = typer.Argument(..., help="New title for the agent"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace ID (or set SCULPT_WORKSPACE_ID)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Rename an agent."""
    base_url = base_url or get_default_base_url()
    client = get_authenticated_client(base_url)
    workspace_id = resolve_workspace(workspace, client, json_output)

    agents = _fetch_agents_for_workspace(client, workspace_id, json_output)
    agent = resolve_by_prefix(agent_id, agents, lambda a: a.id)

    request = RenameAgentRequest(title=title)

    try:
        result = rename_workspace_agent.sync(
            workspace_id=workspace_id, agent_id=agent.id, client=client, body=request
        )
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if result is None:
        cli_error("Failed to rename agent", detail="No response from server", json_output=json_output)

    if isinstance(result, HTTPValidationError):
        cli_error("Validation error", detail=str(result), json_output=json_output)

    if json_output:
        output = AgentRenameOutput(id=agent.id, title=title)
        typer.echo(output.model_dump_json())
        return

    typer.echo(f"Agent {agent.id} renamed to '{title}'.")


@agent_app.command("delete")
def delete(
    agent_id: str = typer.Argument(..., help="Agent ID or prefix"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace ID (or set SCULPT_WORKSPACE_ID)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Delete an agent."""
    base_url = base_url or get_default_base_url()
    client = get_authenticated_client(base_url)
    workspace_id = resolve_workspace(workspace, client, json_output)

    agents = _fetch_agents_for_workspace(client, workspace_id, json_output)
    agent = resolve_by_prefix(agent_id, agents, lambda a: a.id)
    resolved_id = agent.id

    try:
        delete_workspace_agent.sync(workspace_id=workspace_id, agent_id=resolved_id, client=client)
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if json_output:
        output = AgentDeleteOutput(deleted=True, id=resolved_id)
        typer.echo(output.model_dump_json())
        return

    typer.echo(f"Agent {resolved_id} deleted.")


@agent_app.command("send")
def send(
    agent_id: str = typer.Argument(..., help="Agent ID or prefix"),
    message: str = typer.Argument(..., help="Text to type into the agent's terminal"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace ID (or set SCULPT_WORKSPACE_ID)"),
    submit: bool = typer.Option(True, "--submit/--no-submit", help="Press Enter after writing the text"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Type text into a terminal agent's shell (as if the user typed it)."""
    base_url = base_url or get_default_base_url()

    client = get_authenticated_client(base_url)
    workspace_id = resolve_workspace(workspace, client, json_output)

    agents = _fetch_agents_for_workspace(client, workspace_id, json_output)
    agent = resolve_by_prefix(agent_id, agents, lambda a: a.id)

    request = TerminalInputRequest(text=message, submit=submit)

    try:
        response = post_agent_terminal_input.sync_detailed(agent_id=agent.id, client=client, body=request)
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if response.status_code.value >= 400:
        detail = ""
        try:
            body = response.parsed or json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            body = None
        if isinstance(body, dict):
            detail = body.get("detail", "")
        cli_error(
            detail or f"Server returned {response.status_code.value}",
            json_output=json_output,
        )

    if json_output:
        output = AgentSendOutput(sent=True, agent_id=agent.id, message=message[:_MESSAGE_PREVIEW_MAX_LENGTH])
        typer.echo(output.model_dump_json())
        return

    typer.echo(f"Sent to agent {agent.id}.")


@agent_app.command("status")
def status(
    agent_id: str = typer.Argument(..., help="Agent ID or prefix"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream status updates in real-time"),
    timeout: float = typer.Option(10.0, "--timeout", help="Timeout in seconds for WebSocket connection"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Show lightweight status of an agent."""
    base_url = base_url or get_default_base_url()
    agent_id = resolve_agent_id(base_url, agent_id, json_output)

    if follow:
        session_token = get_session_token_safe(base_url, json_output)
        if json_output:
            on_status = on_status_json
            on_reconnect = on_reconnect_json
        elif is_tty():
            prev_lines = [0]
            on_status = functools.partial(_on_status_inplace, prev_lines=prev_lines)
            on_reconnect = on_reconnect_text
        else:
            on_status = _on_status_append
            on_reconnect = on_reconnect_text

        try:
            exit_reason = follow_agent(base_url, session_token, agent_id, on_status, on_reconnect)
        except ScopeNotFoundError:
            cli_error(f"Agent not found: {agent_id}", json_output=json_output)
        except ScopeForbiddenError:
            cli_error("Not authorized to view this agent", json_output=json_output)
        except ScopeMalformedError as e:
            cli_error(f"Invalid agent id: {e}", json_output=json_output)
        handle_exit_reason(exit_reason, json_output)
        return

    snapshot = _fetch_snapshot(base_url, agent_id, timeout, json_output)

    if json_output:
        typer.echo(_status_output(snapshot).model_dump_json(indent=2))
        return

    typer.echo(_format_status_text(snapshot))


def _fetch_snapshot(base_url: str, agent_id: str, timeout: float, json_output: bool) -> AgentSnapshot:
    """Fetch an agent snapshot via WebSocket, handling errors."""
    session_token = get_session_token_safe(base_url, json_output)

    try:
        return fetch_agent_state(base_url, session_token, agent_id, timeout)
    except ScopeNotFoundError:
        cli_error(f"Agent not found: {agent_id}", json_output=json_output)
    except ScopeForbiddenError:
        cli_error("Not authorized to view this agent", json_output=json_output)
    except ScopeMalformedError as e:
        cli_error(f"Invalid agent id: {e}", json_output=json_output)
    except AgentNotFoundError as e:
        cli_error(f"Agent not found: {e}", json_output=json_output)
    except asyncio.TimeoutError:
        cli_error("Connection timed out", json_output=json_output)
    except (OSError, websockets.exceptions.WebSocketException):
        cli_error("Could not connect to Sculptor server", json_output=json_output)


def _status_output(snapshot: AgentSnapshot) -> AgentStatusOutput:
    """Build the status output model from a snapshot."""
    return AgentStatusOutput(
        id=snapshot.task_id,
        status=snapshot.status,
        updated_at=snapshot.updated_at,
        error_detail=snapshot.error_detail,
    )


def _format_status_text(snapshot: AgentSnapshot) -> str:
    """Format status text lines from a snapshot."""
    lines = [
        f"Agent: {snapshot.task_id}",
        f"Status: {snapshot.status}",
    ]
    if snapshot.error_detail:
        lines.append(f"Error: {snapshot.error_detail}")
    if snapshot.updated_at:
        updated_dt = datetime.datetime.fromisoformat(snapshot.updated_at)
        lines.append(f"Updated: {format_datetime(updated_dt)}")
    return "\n".join(lines)


def _on_status_inplace(snapshot: AgentSnapshot, prev_lines: list[int]) -> None:
    """Render status text in-place on a TTY."""
    prev_lines[0] = overwrite_lines(_format_status_text(snapshot), prev_lines[0])


def _on_status_append(snapshot: AgentSnapshot) -> None:
    """Print status text (append mode)."""
    typer.echo(_format_status_text(snapshot))
