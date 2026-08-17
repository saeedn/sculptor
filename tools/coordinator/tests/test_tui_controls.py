"""Pilot tests: TUI controls append journal intents; drill-down renders."""

import threading
from pathlib import Path

from textual.widgets import DataTable

from coordinator.journal import AttemptStarted
from coordinator.journal import ControlIntent
from coordinator.journal import GateResult
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.statedir import state_dir
from coordinator.tui.app import CoordinatorApp
from coordinator.tui.drilldown import NodeDetailScreen
from coordinator.tui.drilldown import TextScreen
from tests.test_tui import make_plan_dir


def intents(plan_dir: Path) -> list[tuple[str, str | None]]:
    return [(e.intent, e.node_id) for e in replay(journal_path(plan_dir)) if isinstance(e, ControlIntent)]


def start_journal(plan_dir: Path) -> Journal:
    ensure_state_dir(plan_dir)
    journal = Journal(journal_path(plan_dir))
    journal.append(RunStarted(run_id="run-x", plan_dir=str(plan_dir), manifest_hash="h"))
    return journal


def make_app(plan_dir: Path) -> CoordinatorApp:
    return CoordinatorApp(plan_dir, should_start_run=False)


async def test_run_level_controls_append_intents(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    start_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.press("r")
        assert intents(plan_dir) == [("pause", None), ("resume", None)]
        assert "requested: pause, resume" in app.status_text


async def test_row_controls_append_node_intents(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    start_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        # Cursor starts on the first row ("1.1").
        await pilot.press("t")
        assert intents(plan_dir) == [("retry", "1.1")]
        # Skip needs a confirmation; decline first, then accept.
        await pilot.press("s")
        await pilot.press("n")
        assert len(intents(plan_dir)) == 1
        await pilot.press("s")
        await pilot.press("y")
        assert intents(plan_dir)[-1] == ("skip", "1.1")


async def test_abort_requires_confirmation(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    start_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await pilot.press("A")
        await pilot.press("y")
        assert intents(plan_dir) == [("abort", None)]


async def test_approve_only_for_waiting_human(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal = start_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await pilot.press("a")
        assert intents(plan_dir) == []
        journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
        journal.append(TaskStateChanged(node_id="1.1", old_state="running", new_state="gate-checking"))
        journal.append(TaskStateChanged(node_id="1.1", old_state="gate-checking", new_state="waiting-human"))
        app.refresh_state()
        await pilot.press("a")
        assert intents(plan_dir) == [("approve", "1.1")]


async def test_drilldown_renders_attempt_history(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal = start_journal(plan_dir)
    journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="1.1", attempt_index=0, worker_registration="w", pid=42, attempt_dir="/a/0"))
    journal.append(SignalObserved(node_id="1.1", attempt_index=0, event="Stop", session_id="sess-drill"))
    journal.append(GateResult(node_id="1.1", gate="mechanical", passed=False, findings="lint exploded"))
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, NodeDetailScreen)
        assert screen.node_id == "1.1"
        table = screen.query_one("#attempts", DataTable)
        assert table.row_count == 1
        assert str(table.get_cell("0", "session id")) == "sess-drill"
        body = str(screen.query_one("#detail-body").render())
        assert "lint exploded" in body
        assert "claude --resume sess-drill" in body


async def test_failure_report_screen(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal = start_journal(plan_dir)
    journal.append(RunPaused(reason="failed", resume_hint="failure report"))
    (state_dir(plan_dir) / "failure_report.md").write_text("# Coordinator failure report\n\n## Node 1.1\n")
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await pilot.press("f")
        screen = app.screen
        assert isinstance(screen, TextScreen)
        assert "Coordinator failure report" in screen.body_text


async def test_ctrl_c_does_not_kill_a_live_run(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        stop = threading.Event()
        run_thread = threading.Thread(target=stop.wait, daemon=True)
        run_thread.start()
        app._run_thread = run_thread
        await pilot.press("ctrl+c")
        assert app.is_running
        stop.set()
        run_thread.join(timeout=5.0)
        app._run_thread = None
        await pilot.press("ctrl+c")
    assert not app.is_running
