"""Shared helpers for --follow streaming across commands."""

import json
from typing import assert_never

import httpx
import typer

from sculpt.auth import build_client
from sculpt.commands.data_types import AgentStatusOutput
from sculpt.formatting import cli_error
from sculpt.session import SessionTokenError
from sculpt.session import get_session_token
from sculpt.ws_client import AgentSnapshot
from sculpt.ws_client import ExitReason
from sculpt.ws_client import follow_agent


def get_session_token_safe(base_url: str, json_output: bool) -> str:
    """Get a session token, exiting on failure."""
    try:
        return get_session_token(build_client(base_url))
    except SessionTokenError as e:
        cli_error(str(e), json_output=json_output)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        cli_error(f"Could not connect to Sculptor server at {base_url}", json_output=json_output)


def handle_exit_reason(reason: ExitReason, json_output: bool) -> None:
    """Map an ExitReason to an exit code. Always raises typer.Exit or calls cli_error."""
    if json_output:
        typer.echo(json.dumps({"type": "exit", "data": {"reason": reason.value}}, default=str))

    match reason:
        case ExitReason.TERMINAL_STATE:
            raise typer.Exit(code=0)
        case ExitReason.WAITING:
            raise typer.Exit(code=2)
        case ExitReason.CTRL_C:
            raise typer.Exit(code=0)
        case ExitReason.RETRY_EXHAUSTED:
            cli_error("Connection lost: reconnection retries exhausted", json_output=json_output)
        case _ as unreachable:
            assert_never(unreachable)


def on_status_json(snapshot: AgentSnapshot) -> None:
    """Emit a status NDJSON envelope."""
    output = AgentStatusOutput(
        id=snapshot.task_id,
        status=snapshot.status,
        updated_at=snapshot.updated_at,
        error_detail=snapshot.error_detail,
    )
    typer.echo(json.dumps({"type": "status", "data": output.model_dump()}, default=str))


def on_reconnect_json() -> None:
    """Emit a reconnected NDJSON envelope."""
    typer.echo(json.dumps({"type": "reconnected", "data": {}}, default=str))


def on_reconnect_text() -> None:
    """Print reconnected notice to stderr."""
    typer.echo("Reconnected", err=True)


def on_reconnect_separator() -> None:
    """Print reconnected separator to stdout."""
    typer.echo("--- Reconnected ---")


def noop_status(_snapshot: AgentSnapshot) -> None:
    """Ignore status snapshots (used when status output is not wanted)."""
    pass


def follow_until_terminal(base_url: str, agent_id: str, *, json_output: bool) -> None:
    """Follow an agent until it reaches a terminal/waiting state. Used by the run command."""
    session_token = get_session_token_safe(base_url, json_output)
    if json_output:
        status_cb = on_status_json
        reconnect_cb = on_reconnect_json
    else:
        status_cb = noop_status
        reconnect_cb = on_reconnect_separator

    exit_reason = follow_agent(base_url, session_token, agent_id, status_cb, reconnect_cb)
    handle_exit_reason(exit_reason, json_output)
