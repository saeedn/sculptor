"""WebSocket client for fetching agent state from the Sculptor streaming endpoint."""

import asyncio
import enum
import json
import urllib.parse
from collections.abc import Callable
from typing import Any

import pydantic
import websockets
import websockets.exceptions


class AgentNotFoundError(Exception):
    """Raised when the target agent ID or prefix is not found in the WebSocket dump."""


class ExitReason(enum.Enum):
    TERMINAL_STATE = "terminal_state"
    WAITING = "waiting"
    CTRL_C = "ctrl_c"
    RETRY_EXHAUSTED = "retry_exhausted"


class AgentSnapshot(pydantic.BaseModel):
    """All data for a single agent extracted from the WebSocket dump."""

    model_config = pydantic.ConfigDict(frozen=True)

    task_id: str
    status: str
    task_status: str
    error_detail: str | None
    updated_at: str
    title: str | None
    project_id: str
    workspace_id: str
    created_at: str
    is_deleted: bool


def _build_ws_url(base_url: str, session_token: str) -> str:
    """Convert an HTTP base URL to a WebSocket URL for the streaming endpoint."""
    if base_url.startswith("https://"):
        ws_url = "wss://" + base_url[len("https://") :]
    elif base_url.startswith("http://"):
        ws_url = "ws://" + base_url[len("http://") :]
    else:
        ws_url = base_url
    return f"{ws_url}/api/v1/stream/ws?x-session-token={urllib.parse.quote(session_token, safe='')}"


_TERMINAL_STATUSES = frozenset({"READY", "ERROR"})
_TERMINAL_TASK_STATUSES = frozenset({"FAILED", "DELETED", "SUCCEEDED"})

_MAX_RECONNECT_DELAY_SECONDS = 30


def _is_terminal_state(snapshot: AgentSnapshot) -> bool:
    return snapshot.status in _TERMINAL_STATUSES or snapshot.task_status in _TERMINAL_TASK_STATUSES


def _is_waiting_state(snapshot: AgentSnapshot) -> bool:
    return snapshot.status == "WAITING"


def _snapshot_from_view(task_id: str, view: dict[str, Any]) -> AgentSnapshot:
    """Build an AgentSnapshot from a single task view dict."""
    return AgentSnapshot(
        task_id=view.get("id", task_id),
        status=view.get("status", "UNKNOWN"),
        task_status=view.get("taskStatus", "UNKNOWN"),
        error_detail=view.get("errorDetail"),
        updated_at=view.get("updatedAt", ""),
        title=view.get("title"),
        project_id=view.get("projectId", ""),
        workspace_id=view.get("workspaceId", ""),
        created_at=view.get("createdAt", ""),
        is_deleted=view.get("isDeleted", False),
    )


def _extract_snapshot(task_id: str, dump: dict[str, Any]) -> AgentSnapshot:
    """Extract an AgentSnapshot from the WebSocket state dump."""
    task_views = dump.get("taskViewsByTaskId", {})
    view = task_views[task_id]
    return _snapshot_from_view(task_id, view)


async def _receive_initial_dump(ws: Any, timeout: float = 30.0) -> dict[str, Any]:
    """Receive and parse the initial state dump, skipping null keepalives."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        dump = json.loads(raw)
        if dump is not None:
            return dump


async def _fetch_agent_state_async(ws_url: str, agent_id: str, timeout: float) -> AgentSnapshot:
    """Connect to the WebSocket, receive the initial dump, and extract the agent."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        dump = await _receive_initial_dump(ws, timeout=timeout)
        task_views = dump.get("taskViewsByTaskId", {})
        if agent_id not in task_views:
            raise AgentNotFoundError(f"Agent {agent_id} not found in initial frame")
        return _extract_snapshot(agent_id, dump)


def fetch_agent_state(base_url: str, session_token: str, agent_id: str, timeout: float = 10.0) -> AgentSnapshot:
    """Fetch agent state via a one-shot WebSocket connection.

    Reads exactly one frame, extracts the agent's view, and disconnects.
    """
    ws_url = _build_ws_url(base_url, session_token)
    return asyncio.run(_fetch_agent_state_async(ws_url, agent_id, timeout))


async def _fetch_all_agents_async(ws_url: str, timeout: float) -> list[AgentSnapshot]:
    """Connect to the WebSocket, receive the initial dump, and extract all agents."""
    async with websockets.connect(ws_url, max_size=None) as ws:
        dump = await _receive_initial_dump(ws, timeout=timeout)
        task_views = dump.get("taskViewsByTaskId", {})
        return [_snapshot_from_view(task_id, view) for task_id, view in task_views.items()]


def fetch_all_agents(
    base_url: str,
    session_token: str,
    timeout: float = 10.0,
) -> list[AgentSnapshot]:
    """Fetch all agent snapshots via a one-shot WebSocket connection.

    The server always emits every agent; callers filter client-side.
    """
    ws_url = _build_ws_url(base_url, session_token)
    return asyncio.run(_fetch_all_agents_async(ws_url, timeout))


def _status_signature(snapshot: AgentSnapshot) -> tuple[Any, ...]:
    """Fields whose change should produce a fresh status emission.

    The server re-emits the task view on every internal task update — including
    ones that don't change anything user-visible (e.g. streaming partials, which
    bump the view's mtime but not its rendered fields). Comparing on the rendered
    fields lets the client emit one status per real change instead of one per
    server-side bump.
    """
    return (
        snapshot.status,
        snapshot.task_status,
        snapshot.error_detail,
        snapshot.is_deleted,
    )


async def _follow_loop(
    ws: Any,
    task_id: str,
    on_status: Callable[[AgentSnapshot], None],
    last_status_sig: list[tuple[Any, ...]],
) -> ExitReason:
    """Process incremental WebSocket updates until a terminal/waiting state."""
    while True:
        raw = await ws.recv()
        dump = json.loads(raw)
        if dump is None:
            continue

        task_views = dump.get("taskViewsByTaskId", {})
        if task_id in task_views:
            snapshot = _snapshot_from_view(task_id, task_views[task_id])
            sig = _status_signature(snapshot)
            if sig != last_status_sig[0]:
                last_status_sig[0] = sig
                on_status(snapshot)
            if _is_terminal_state(snapshot):
                return ExitReason.TERMINAL_STATE
            if _is_waiting_state(snapshot):
                return ExitReason.WAITING


async def _follow_agent_async(
    ws_url: str,
    agent_id: str,
    on_status: Callable[[AgentSnapshot], None],
    on_reconnect: Callable[[], None] | None,
    max_retries: int = 5,
) -> ExitReason:
    """Follow an agent via the WebSocket with reconnection support."""
    retry_count = 0
    task_id = agent_id
    last_status_sig: list[tuple[Any, ...]] = [()]

    while True:
        try:
            async with websockets.connect(ws_url, max_size=None) as ws:
                dump = await _receive_initial_dump(ws)

                task_views = dump.get("taskViewsByTaskId", {})
                if task_id not in task_views:
                    raise AgentNotFoundError(f"Agent {task_id} not found in initial frame")

                snapshot = _extract_snapshot(task_id, dump)

                is_reconnect = retry_count > 0
                if is_reconnect and on_reconnect is not None:
                    on_reconnect()

                last_status_sig[0] = _status_signature(snapshot)
                on_status(snapshot)

                retry_count = 0

                if _is_terminal_state(snapshot):
                    return ExitReason.TERMINAL_STATE
                if _is_waiting_state(snapshot):
                    return ExitReason.WAITING

                return await _follow_loop(ws, task_id, on_status, last_status_sig)

        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
            retry_count += 1
            if retry_count > max_retries:
                return ExitReason.RETRY_EXHAUSTED
            delay = min(2 ** (retry_count - 1), _MAX_RECONNECT_DELAY_SECONDS)
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return ExitReason.CTRL_C


def follow_agent(
    base_url: str,
    session_token: str,
    agent_id: str,
    on_status: Callable[[AgentSnapshot], None],
    on_reconnect: Callable[[], None] | None = None,
    max_retries: int = 5,
) -> ExitReason:
    """Follow an agent via the WebSocket, calling on_status on status changes.

    on_status fires only when meaningful fields actually change (not on every
    server-side task-view bump).

    Returns an ExitReason indicating why the follow loop ended.
    """
    ws_url = _build_ws_url(base_url, session_token)
    try:
        return asyncio.run(
            _follow_agent_async(
                ws_url,
                agent_id,
                on_status,
                on_reconnect,
                max_retries,
            )
        )
    except KeyboardInterrupt:
        return ExitReason.CTRL_C
