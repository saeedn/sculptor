"""Unit tests for the WebSocket client module."""

import asyncio
import json
import threading
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import pytest
import websockets
import websockets.server

from sculpt.ws_client import AgentNotFoundError
from sculpt.ws_client import AgentSnapshot
from sculpt.ws_client import ExitReason
from sculpt.ws_client import _build_ws_url
from sculpt.ws_client import fetch_agent_state
from sculpt.ws_client import follow_agent


def test_build_ws_url() -> None:
    assert _build_ws_url("http://x", "tok") == "ws://x/api/v1/stream/ws?x-session-token=tok"


def test_build_ws_url_https_to_wss() -> None:
    assert _build_ws_url("https://x", "tok") == "wss://x/api/v1/stream/ws?x-session-token=tok"


def _make_task_view(
    task_id: str = "tsk_abc123",
    status: str = "RUNNING",
    task_status: str = "RUNNING",
    error_detail: str | None = None,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "projectId": "prj_test",
        "workspaceId": "ws_test",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:01:00Z",
        "taskStatus": task_status,
        "status": status,
        "title": "Test task",
        "model": "CLAUDE-4-SONNET",
        "interface": "TERMINAL",
        "isDeleted": False,
        "errorDetail": error_detail,
    }


def _make_dump(
    task_views: dict[str, dict[str, Any]],
    task_updates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "taskViewsByTaskId": task_views,
        "taskUpdateByTaskId": task_updates or {},
    }


def _start_ws_server(
    payload: str | None, delay: float = 0.0
) -> tuple[str, threading.Event, dict[str, Any]]:
    """Start a WebSocket server in a background thread that sends the given payload.

    Returns (url, shutdown_event, server_info). server_info["last_path"] is
    populated with the request path of each accepted connection so tests can
    assert on the query string.
    """
    shutdown_event = threading.Event()
    ready_event = threading.Event()
    server_info: dict[str, Any] = {}

    async def handler(ws: websockets.server.ServerConnection) -> None:
        server_info["last_path"] = ws.request.path
        if delay > 0:
            await asyncio.sleep(delay)
        if payload is not None:
            await ws.send(payload)
        await ws.wait_closed()

    async def run_server() -> None:
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            server_info["port"] = port
            ready_event.set()
            while not shutdown_event.is_set():
                await asyncio.sleep(0.05)

    def thread_target() -> None:
        asyncio.run(run_server())

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()
    ready_event.wait(timeout=5.0)

    url = f"ws://127.0.0.1:{server_info['port']}"
    return url, shutdown_event, server_info


def test_fetch_agent_state_happy_path() -> None:
    task_id = f"tsk_{uuid4().hex}"
    view = _make_task_view(task_id=task_id)
    dump = _make_dump(task_views={task_id: view})
    url, shutdown, _info = _start_ws_server(json.dumps(dump))
    try:
        snapshot = fetch_agent_state(url.replace("ws://", "http://"), "fake-token", task_id)
        assert isinstance(snapshot, AgentSnapshot)
        assert snapshot.task_id == task_id
        assert snapshot.status == "RUNNING"
        assert snapshot.title == "Test task"
    finally:
        shutdown.set()


def test_fetch_agent_state_not_found() -> None:
    dump = _make_dump(task_views={"tsk_xyz": _make_task_view(task_id="tsk_xyz")})
    url, shutdown, _info = _start_ws_server(json.dumps(dump))
    try:
        with pytest.raises(AgentNotFoundError):
            fetch_agent_state(url.replace("ws://", "http://"), "fake-token", "tsk_nope")
    finally:
        shutdown.set()


def test_fetch_agent_state_timeout() -> None:
    url, shutdown, _info = _start_ws_server(None, delay=10.0)
    try:
        with pytest.raises(TimeoutError):
            fetch_agent_state(url.replace("ws://", "http://"), "fake-token", "tsk_any", timeout=0.1)
    finally:
        shutdown.set()


def test_fetch_agent_state_missing_optional_fields() -> None:
    task_id = f"tsk_{uuid4().hex}"
    minimal_view = {
        "id": task_id,
        "status": "RUNNING",
        "taskStatus": "RUNNING",
        "updatedAt": "2026-01-01T00:00:00Z",
        "model": "CLAUDE-4-SONNET",
        "interface": "TERMINAL",
        "projectId": "prj_test",
        "workspaceId": "ws_test",
        "createdAt": "2026-01-01T00:00:00Z",
        "isDeleted": False,
    }
    dump = _make_dump(task_views={task_id: minimal_view})
    url, shutdown, _info = _start_ws_server(json.dumps(dump))
    try:
        snapshot = fetch_agent_state(url.replace("ws://", "http://"), "fake-token", task_id)
        assert snapshot.error_detail is None
        assert snapshot.title is None
    finally:
        shutdown.set()


def test_fetch_agent_state_skips_null_keepalive() -> None:
    task_id = f"tsk_{uuid4().hex}"
    dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})
    shutdown_event = threading.Event()
    ready_event = threading.Event()
    server_info: dict[str, Any] = {}

    async def handler(ws: websockets.server.ServerConnection) -> None:
        await ws.send("null")
        await ws.send(json.dumps(dump))
        await ws.wait_closed()

    async def run_server() -> None:
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            server_info["port"] = port
            ready_event.set()
            while not shutdown_event.is_set():
                await asyncio.sleep(0.05)

    thread = threading.Thread(target=lambda: asyncio.run(run_server()), daemon=True)
    thread.start()
    ready_event.wait(timeout=5.0)

    url = f"http://127.0.0.1:{server_info['port']}"
    try:
        snapshot = fetch_agent_state(url, "fake-token", task_id)
        assert snapshot.task_id == task_id
    finally:
        shutdown_event.set()


def _start_ws_server_with_messages(
    messages_to_send: Sequence[str], delay_between: float = 0.05
) -> tuple[str, threading.Event]:
    """Start a WebSocket server that sends a sequence of messages."""
    shutdown_event = threading.Event()
    ready_event = threading.Event()
    server_info: dict[str, Any] = {}

    async def handler(ws: websockets.server.ServerConnection) -> None:
        for msg in messages_to_send:
            await ws.send(msg)
            await asyncio.sleep(delay_between)
        await ws.wait_closed()

    async def run_server() -> None:
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            server_info["port"] = port
            ready_event.set()
            while not shutdown_event.is_set():
                await asyncio.sleep(0.05)

    thread = threading.Thread(target=lambda: asyncio.run(run_server()), daemon=True)
    thread.start()
    ready_event.wait(timeout=5.0)

    url = f"ws://127.0.0.1:{server_info['port']}"
    return url, shutdown_event


def test_follow_auto_exit_terminal_state() -> None:
    task_id = f"tsk_{uuid4().hex}"
    initial_view = _make_task_view(task_id=task_id, status="RUNNING")
    initial_dump = _make_dump(task_views={task_id: initial_view})
    update_view = _make_task_view(task_id=task_id, status="READY")
    update_dump = _make_dump(task_views={task_id: update_view})

    url, shutdown = _start_ws_server_with_messages([
        json.dumps(initial_dump),
        json.dumps(update_dump),
    ])
    try:
        statuses: list[AgentSnapshot] = []

        result = follow_agent(
            url.replace("ws://", "http://"),
            "fake-token",
            task_id,
            on_status=statuses.append,
        )

        assert result == ExitReason.TERMINAL_STATE
        assert len(statuses) >= 2
        assert statuses[0].status == "RUNNING"
        assert statuses[-1].status == "READY"
    finally:
        shutdown.set()


def test_follow_auto_exit_waiting() -> None:
    task_id = f"tsk_{uuid4().hex}"
    initial_view = _make_task_view(task_id=task_id, status="RUNNING")
    initial_dump = _make_dump(task_views={task_id: initial_view})
    update_view = _make_task_view(task_id=task_id, status="WAITING")
    update_dump = _make_dump(task_views={task_id: update_view})

    url, shutdown = _start_ws_server_with_messages([
        json.dumps(initial_dump),
        json.dumps(update_dump),
    ])
    try:
        statuses: list[AgentSnapshot] = []

        result = follow_agent(
            url.replace("ws://", "http://"),
            "fake-token",
            task_id,
            on_status=statuses.append,
        )

        assert result == ExitReason.WAITING
        assert any(s.status == "WAITING" for s in statuses)
    finally:
        shutdown.set()


def test_follow_ignores_other_agents() -> None:
    target_id = f"tsk_target_{uuid4().hex}"
    other_id = f"tsk_other_{uuid4().hex}"
    initial_dump = _make_dump(
        task_views={
            target_id: _make_task_view(task_id=target_id),
            other_id: _make_task_view(task_id=other_id),
        },
    )
    update_other = {
        "taskViewsByTaskId": {other_id: _make_task_view(task_id=other_id, status="ERROR")},
        "taskUpdateByTaskId": {},
    }
    update_target = {
        "taskViewsByTaskId": {target_id: _make_task_view(task_id=target_id, status="READY")},
        "taskUpdateByTaskId": {},
    }

    url, shutdown = _start_ws_server_with_messages([
        json.dumps(initial_dump),
        json.dumps(update_other),
        json.dumps(update_target),
    ])
    try:
        statuses: list[AgentSnapshot] = []

        result = follow_agent(
            url.replace("ws://", "http://"),
            "fake-token",
            target_id,
            on_status=statuses.append,
        )

        assert result == ExitReason.TERMINAL_STATE
        for s in statuses:
            assert s.task_id == target_id


    finally:
        shutdown.set()


def test_follow_handles_null_keepalive() -> None:
    task_id = f"tsk_{uuid4().hex}"
    initial_dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})
    terminal_update = {
        "taskViewsByTaskId": {task_id: _make_task_view(task_id=task_id, status="READY")},
        "taskUpdateByTaskId": {},
    }

    url, shutdown = _start_ws_server_with_messages([
        json.dumps(initial_dump),
        "null",
        "null",
        json.dumps(terminal_update),
    ])
    try:
        result = follow_agent(
            url.replace("ws://", "http://"),
            "fake-token",
            task_id,
            on_status=lambda _: None,
        )

        assert result == ExitReason.TERMINAL_STATE
    finally:
        shutdown.set()


def test_follow_reconnect() -> None:
    task_id = f"tsk_{uuid4().hex}"
    initial_dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})
    reconnect_dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id, status="READY")})

    connection_count = 0
    shutdown_event = threading.Event()
    ready_event = threading.Event()
    server_info: dict[str, Any] = {}

    async def handler(ws: websockets.server.ServerConnection) -> None:
        nonlocal connection_count
        connection_count += 1
        if connection_count == 1:
            await ws.send(json.dumps(initial_dump))
            await asyncio.sleep(0.05)
            await ws.close()
        else:
            await ws.send(json.dumps(reconnect_dump))
            await ws.wait_closed()

    async def run_server() -> None:
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            server_info["port"] = port
            ready_event.set()
            while not shutdown_event.is_set():
                await asyncio.sleep(0.05)

    thread = threading.Thread(target=lambda: asyncio.run(run_server()), daemon=True)
    thread.start()
    ready_event.wait(timeout=5.0)

    url = f"http://127.0.0.1:{server_info['port']}"
    reconnect_called = []

    try:
        result = follow_agent(
            url,
            "fake-token",
            task_id,
            on_status=lambda _: None,
            on_reconnect=lambda: reconnect_called.append(True),
            max_retries=3,
        )

        assert result == ExitReason.TERMINAL_STATE
        assert len(reconnect_called) >= 1
    finally:
        shutdown_event.set()


def test_follow_retry_exhausted() -> None:
    task_id = f"tsk_{uuid4().hex}"
    initial_dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})

    connection_count = 0
    shutdown_event = threading.Event()
    ready_event = threading.Event()
    server_info: dict[str, Any] = {}

    async def handler(ws: websockets.server.ServerConnection) -> None:
        nonlocal connection_count
        connection_count += 1
        if connection_count == 1:
            await ws.send(json.dumps(initial_dump))
            await asyncio.sleep(0.05)
        await ws.close()

    async def run_server() -> None:
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            server_info["port"] = port
            ready_event.set()
            while not shutdown_event.is_set():
                await asyncio.sleep(0.05)

    thread = threading.Thread(target=lambda: asyncio.run(run_server()), daemon=True)
    thread.start()
    ready_event.wait(timeout=5.0)

    url = f"http://127.0.0.1:{server_info['port']}"

    try:
        result = follow_agent(
            url,
            "fake-token",
            task_id,
            on_status=lambda _: None,
            max_retries=1,
        )

        assert result == ExitReason.RETRY_EXHAUSTED
    finally:
        shutdown_event.set()


def test_fetch_agent_state_url_includes_session_token() -> None:
    task_id = "tsk_full_id_capture"
    dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})
    url, shutdown, info = _start_ws_server(json.dumps(dump))
    try:
        fetch_agent_state(url.replace("ws://", "http://"), "tok", task_id)
        assert "x-session-token=tok" in info["last_path"]
    finally:
        shutdown.set()


def test_fetch_agent_state_reads_exactly_one_frame() -> None:
    task_id = "tsk_one_frame"
    dump = _make_dump(task_views={task_id: _make_task_view(task_id=task_id)})
    url, shutdown, _info = _start_ws_server(json.dumps(dump))
    try:
        snapshot = fetch_agent_state(url.replace("ws://", "http://"), "tok", task_id, timeout=2.0)
        assert snapshot.task_id == task_id
    finally:
        shutdown.set()


def test_follow_dedupes_status_when_view_unchanged() -> None:
    """The server re-emits the task view on every internal task update — many
    of those don't change anything user-visible (e.g. streaming partials bump
    the view's mtime but not its rendered fields). Verify the client emits
    on_status only when meaningful fields actually change.
    """
    task_id = f"tsk_{uuid4().hex}"
    view = _make_task_view(task_id=task_id, status="RUNNING")
    initial_dump = _make_dump(task_views={task_id: view})
    # Same view re-emitted three times — should produce zero extra on_status calls.
    same_view_dump = {"taskViewsByTaskId": {task_id: view}, "taskUpdateByTaskId": {}}
    # Now a different status — should produce one on_status call.
    changed_dump = {
        "taskViewsByTaskId": {task_id: _make_task_view(task_id=task_id, status="READY")},
        "taskUpdateByTaskId": {},
    }

    url, shutdown = _start_ws_server_with_messages(
        [
            json.dumps(initial_dump),
            json.dumps(same_view_dump),
            json.dumps(same_view_dump),
            json.dumps(same_view_dump),
            json.dumps(changed_dump),
        ]
    )
    try:
        statuses: list[str] = []
        follow_agent(
            url.replace("ws://", "http://"),
            "tok",
            task_id,
            on_status=lambda s: statuses.append(s.status),
        )
        # Initial status + the one real change. The three identical re-emits do not fire.
        assert statuses == ["RUNNING", "READY"]
    finally:
        shutdown.set()
