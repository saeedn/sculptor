import json
import time

import httpx
import typer

from sculpt.auth import get_authenticated_client
from sculpt.auth import get_default_base_url
from sculpt.client import Client
from sculpt.client.api.default import create_workspace_agent
from sculpt.client.api.default import create_workspace_v2
from sculpt.client.api.default import post_agent_terminal_input
from sculpt.client.models.agent_type_name import AgentTypeName
from sculpt.client.models.create_agent_request import CreateAgentRequest
from sculpt.client.models.create_workspace_request_v2 import CreateWorkspaceRequestV2
from sculpt.client.models.http_validation_error import HTTPValidationError
from sculpt.client.models.terminal_input_request import TerminalInputRequest
from sculpt.client.types import UNSET
from sculpt.commands._follow_helpers import follow_until_terminal
from sculpt.commands._harness_helpers import resolve_harness_selection
from sculpt.commands._workspace_helpers import resolve_requested_branch_name
from sculpt.commands.data_types import RunOutput
from sculpt.formatting import cli_error
from sculpt.formatting import handle_connection_error
from sculpt.resolve import resolve_project

# How long to wait for a freshly created terminal agent to reach its prompt
# before giving up on delivering the prompt, and how often to re-check.
_PROMPT_DELIVERY_TIMEOUT_SECONDS = 60.0
_PROMPT_DELIVERY_POLL_SECONDS = 0.5
# Substring of the server's 409 detail for a permanently prompt-incapable agent
# (e.g. a plain Terminal harness). Distinguished from the transient "not at its
# prompt yet" 409 so we don't retry a write that can never succeed.
_NOT_OPT_IN_DETAIL = "does not accept automated prompts"


def _response_detail(response: object) -> str:
    """Best-effort extraction of FastAPI's ``{"detail": ...}`` body, for messaging."""
    content = getattr(response, "content", b"") or b""
    try:
        body = json.loads(content)
    except (ValueError, TypeError):
        return content.decode(errors="replace") if isinstance(content, bytes) else str(content)
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else str(detail)
    return ""


def _deliver_prompt(client: Client, agent_id: str, prompt: str, *, submit: bool, json_output: bool) -> None:
    """Type the prompt into a freshly created terminal agent, waiting for readiness.

    The agent was just created, so its terminal program is still launching and
    has not reached its prompt; the delivery endpoint refuses to write into a
    not-yet-ready TUI (HTTP 409, "busy or not at its prompt" / "terminal not
    running"). Poll those away until the program is at its prompt or the timeout
    elapses — the same thing a human does by waiting for the terminal to load
    before typing. A 409 means the guards rejected the write before any bytes
    were sent, so retrying is safe. "Does not accept automated prompts" is a
    permanent rejection and is surfaced immediately rather than retried.
    """
    deadline = time.monotonic() + _PROMPT_DELIVERY_TIMEOUT_SECONDS
    body = TerminalInputRequest(text=prompt, submit=submit)
    while True:
        try:
            response = post_agent_terminal_input.sync_detailed(agent_id=agent_id, client=client, body=body)
        except httpx.ConnectError:
            handle_connection_error(json_output)

        status = response.status_code.value
        if status < 400:
            return

        detail = _response_detail(response)
        if status == 409 and _NOT_OPT_IN_DETAIL in detail:
            cli_error(
                "This agent does not accept automated prompts, so `sculpt run` cannot deliver one. "
                "Omit --harness to use your default agent, or pick a prompt-capable harness.",
                json_output=json_output,
            )
        if status == 409 and time.monotonic() < deadline:
            time.sleep(_PROMPT_DELIVERY_POLL_SECONDS)
            continue
        cli_error(
            f"Agent created but failed to deliver the prompt (server returned {status})",
            detail=detail,
            json_output=json_output,
        )


def run_cmd(
    prompt: str = typer.Argument(..., help="The task prompt"),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help=(
            "Path to the repository. If omitted, the project is taken from the"
            + " SCULPT_PROJECT_ID env var (set in every Sculptor workspace shell),"
            + " or matched against the current working directory."
        ),
    ),
    branch: str | None = typer.Option(None, "--branch", help="Source branch"),
    branch_name: str | None = typer.Option(
        None,
        "--branch-name",
        help="New branch name (required for worktree; auto-generated if omitted)",
    ),
    target_branch: str | None = typer.Option(
        None,
        "--target-branch",
        help="Diff/merge target branch (auto-resolved from the repo if omitted)",
    ),
    name: str | None = typer.Option(None, "--name", help="Agent name"),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help=(
            "Agent harness to run the prompt with. If omitted, uses your"
            + " most-recently-used harness from the Sculptor app."
        ),
    ),
    submit: bool = typer.Option(True, "--submit/--no-submit", help="Press Enter after typing the prompt"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream the agent's activity after creation"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="The Sculptor server URL"),
) -> None:
    """Create a workspace and terminal agent, then type the prompt into its shell."""
    base_url = base_url or get_default_base_url()

    client = get_authenticated_client(base_url)

    # An omitted harness lets the server apply the user's most-recently-used one.
    selection = resolve_harness_selection(harness, client, json_output)

    # `sculpt run` exists to deliver a prompt, so reject a harness that cannot
    # accept one up front — before creating a workspace/agent we would have to
    # tear down. The built-in Terminal harness is a plain shell: a typed prompt
    # would be executed as shell commands, so it never accepts automated prompts.
    # (A registered agent that does not accept prompts is caught at delivery time
    # via the server's permanent 409.)
    if selection is not None and selection.agent_type == AgentTypeName.TERMINAL:
        cli_error(
            "`sculpt run` needs an agent that accepts automated prompts, but the Terminal "
            "harness is a plain shell that does not. Omit --harness to use your default "
            "agent, or pick a prompt-capable harness.",
            json_output=json_output,
        )

    project_id = resolve_project(repo, client)

    resolved_branch_name = resolve_requested_branch_name(
        client=client,
        project_id=project_id,
        branch_name=branch_name,
        workspace_name=name,
        json_output=json_output,
    )

    # Create workspace
    ws_request = CreateWorkspaceRequestV2(
        project_id=project_id,
        source_branch=branch,
        description=name,
        requested_branch_name=resolved_branch_name,
        target_branch=target_branch,
    )

    try:
        ws_result = create_workspace_v2.sync(client=client, body=ws_request)  # type: ignore[arg-type]
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if ws_result is None:
        cli_error("Failed to create workspace", detail="No response from server", json_output=json_output)

    if isinstance(ws_result, HTTPValidationError):
        cli_error("Validation error", detail=str(ws_result), json_output=json_output)

    workspace_id = ws_result.object_id

    # Create the agent. An omitted --harness sends no agent type, so the server
    # applies the user's most-recently-used harness (the same default the app's
    # "+" button uses).
    agent_request = CreateAgentRequest(
        name=name,
        agent_type=selection.agent_type if selection is not None else UNSET,
        registration_id=(
            selection.registration_id if selection is not None and selection.registration_id is not None else UNSET
        ),
    )

    try:
        agent_result = create_workspace_agent.sync(workspace_id=workspace_id, client=client, body=agent_request)
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if agent_result is None:
        cli_error("Failed to create agent", detail="No response from server", json_output=json_output)

    if isinstance(agent_result, HTTPValidationError):
        cli_error("Validation error", detail=str(agent_result), json_output=json_output)

    # Type the prompt into the new agent's terminal (as if the user typed it),
    # waiting for the just-launched program to reach its prompt first.
    _deliver_prompt(client, agent_result.id, prompt, submit=submit, json_output=json_output)

    if json_output:
        output = RunOutput(
            workspace_id=workspace_id,
            agent_id=agent_result.id,
            prompt=prompt,
        )
        typer.echo(output.model_dump_json(indent=2))
    else:
        typer.echo(f"Workspace: {workspace_id}")
        typer.echo(f"Agent: {agent_result.id}")

    if follow:
        if not json_output:
            typer.echo(f"Following agent {agent_result.id}...", err=True)
        follow_until_terminal(base_url, agent_result.id, json_output=json_output)
