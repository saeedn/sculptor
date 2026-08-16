"""Pilot tests: the dashboard renders exclusively from the on-disk state."""

import asyncio
from pathlib import Path

from textual.widgets import DataTable

from coordinator.journal import AttemptStarted
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import TaskStateChanged
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.tui.app import CoordinatorApp

PLAN_YAML = """\
version: 1
defaults:
  worker: w
  verification: ["true"]
phases:
  - id: 1
    name: Core
    review: {review}
    tasks:
      - id: "1.1"
        file: 01_01_first.md
      - id: "1.2"
        file: 01_02_second.md
        deps: ["1.1"]
"""


def make_plan_dir(tmp_path: Path, review: str = "none") -> Path:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.yaml").write_text(PLAN_YAML.format(review=review))
    (plan_dir / "01_01_first.md").write_text("# 1.1\n")
    (plan_dir / "01_02_second.md").write_text("# 1.2\n")
    ensure_state_dir(plan_dir)
    return plan_dir


def journal_for(plan_dir: Path) -> Journal:
    return Journal(journal_path(plan_dir))


def write_mid_run_journal(plan_dir: Path) -> None:
    journal = journal_for(plan_dir)
    journal.append(RunStarted(run_id="run-tui", plan_dir=str(plan_dir), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="1.1", attempt_index=0, worker_registration="w", pid=1, attempt_dir="/a/0"))
    journal.append(TaskStateChanged(node_id="1.1", old_state="running", new_state="gate-checking"))
    journal.append(TaskStateChanged(node_id="1.1", old_state="gate-checking", new_state="passed"))
    journal.append(TaskStateChanged(node_id="1.2", old_state="pending", new_state="running"))
    journal.append(
        AttemptStarted(node_id="1.2", attempt_index=0, worker_registration="w-opus", pid=2, attempt_dir="/b/0")
    )
    journal.append(SignalObserved(node_id="1.2", attempt_index=0, event="SessionStart", session_id="s2"))


def make_app(plan_dir: Path) -> CoordinatorApp:
    return CoordinatorApp(plan_dir, should_start_run=False)


async def test_table_renders_mid_run_state(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    write_mid_run_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test():
        table = app.query_one(DataTable)
        assert table.row_count == 2
        assert str(table.get_cell("1.1", "state")) == "passed"
        assert str(table.get_cell("1.2", "state")) == "running"
        assert str(table.get_cell("1.1", "attempts")) == "1/2"
        assert str(table.get_cell("1.2", "worker")) == "w-opus"
        assert "SessionStart" in str(table.get_cell("1.2", "activity"))
        status_text = app.status_text
        assert "run-tui" in status_text
        assert "1/2 passed" in status_text
        assert "running" in status_text


async def test_refresh_picks_up_appended_events(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal = journal_for(plan_dir)
    journal.append(RunStarted(run_id="run-tui", plan_dir=str(plan_dir), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        assert str(table.get_cell("1.1", "state")) == "running"
        journal.append(TaskStateChanged(node_id="1.1", old_state="running", new_state="passed"))
        # Poll until the 0.5s refresh interval picks the event up — a
        # fixed pause flakes under CI load.
        for _ in range(50):
            if str(table.get_cell("1.1", "state")) == "passed":
                break
            await pilot.pause(0.1)
        assert str(table.get_cell("1.1", "state")) == "passed"


async def test_status_bar_complete_and_failed(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal = journal_for(plan_dir)
    journal.append(RunStarted(run_id="run-tui", plan_dir=str(plan_dir), manifest_hash="h"))
    for node_id in ("1.1", "1.2"):
        journal.append(TaskStateChanged(node_id=node_id, old_state="pending", new_state="running"))
        journal.append(TaskStateChanged(node_id=node_id, old_state="running", new_state="gate-checking"))
        journal.append(TaskStateChanged(node_id=node_id, old_state="gate-checking", new_state="passed"))
    app = make_app(plan_dir)
    async with app.run_test():
        status_text = app.status_text
        assert "complete" in status_text
        assert "2/2 passed" in status_text

    failed_plan = make_plan_dir(tmp_path / "failed")
    failed_journal = journal_for(failed_plan)
    failed_journal.append(RunStarted(run_id="run-2", plan_dir=str(failed_plan), manifest_hash="h"))
    failed_journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
    failed_journal.append(TaskStateChanged(node_id="1.1", old_state="running", new_state="failed"))
    failed_journal.append(RunPaused(reason="failed", resume_hint="failure report: x"))
    failed_app = make_app(failed_plan)
    async with failed_app.run_test():
        status_text = failed_app.status_text
        assert "paused (failed)" in status_text


async def test_phase_review_node_rendered(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path, review="agentic")
    journal_for(plan_dir).append(RunStarted(run_id="run-tui", plan_dir=str(plan_dir), manifest_hash="h"))
    app = make_app(plan_dir)
    async with app.run_test():
        table = app.query_one(DataTable)
        assert table.row_count == 3
        assert str(table.get_cell("phase-review:1", "name")) == "phase review"
        assert str(table.get_cell("phase-review:1", "state")) == "pending"


async def test_run_thread_crash_is_visible(tmp_path: Path) -> None:
    plan_dir = make_plan_dir(tmp_path)
    journal_for(plan_dir).append(RunStarted(run_id="run-tui", plan_dir=str(plan_dir), manifest_hash="h"))
    app = make_app(plan_dir)
    async with app.run_test():
        app._on_run_done(None, RuntimeError("scheduler exploded"))
        app.refresh_state()
        status_text = app.status_text
        assert "RUN CRASHED" in status_text
        assert "scheduler exploded" in status_text


async def test_run_level_notice_reaches_the_dashboard(tmp_path: Path) -> None:
    # A notice posted from the run thread must surface as a toast, not
    # vanish the way the progress firehose does in TUI mode.
    plan_dir = make_plan_dir(tmp_path)
    write_mid_run_journal(plan_dir)
    app = make_app(plan_dir)
    async with app.run_test() as pilot:
        await asyncio.to_thread(app._post_notice, "existing run state found (run-tui) — resuming.")
        await pilot.pause()
        assert app.notices == ["existing run state found (run-tui) — resuming."]
        assert any("resuming" in notification.message for notification in app._notifications)
