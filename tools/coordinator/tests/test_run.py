import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import GateResult
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.main import app
from coordinator.manifest import ManifestError
from coordinator.run import RunError
from coordinator.run import execute_plan
from coordinator.statedir import journal_path
from tests.fakes import COMMIT_THEN_STOP
from tests.fakes import STOP_WITHOUT_COMMIT
from tests.fakes import make_git_repo
from tests.fakes import write_registration_yaml

PLAN_TEMPLATE = """\
version: 1
defaults:
  worker: fake-worker
  verification:
    - "true"
phases:
  - id: 1
    name: Phase one
    review: {review}
    tasks:
      - id: "1.1"
        file: 01_01_first.md
      - id: "1.2"
        file: 01_02_second.md
        deps: ["1.1"]
"""


def make_plan_repo(tmp_path: Path, worker_script_body: str, review: str = "agentic") -> tuple[Path, Path]:
    """A git repo containing a two-task plan and a repo-level fake-worker registration."""
    repo = make_git_repo(tmp_path / "repo")
    script = tmp_path / "fake_worker.py"
    script.write_text(worker_script_body)
    write_registration_yaml(repo / ".sculptor" / "workers", "fake-worker", script)
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.yaml").write_text(PLAN_TEMPLATE.format(review=review))
    (plan_dir / "01_01_first.md").write_text("# Task 1.1\n")
    (plan_dir / "01_02_second.md").write_text("# Task 1.2\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add plan"], check=True)
    return repo, plan_dir


def run_plan(plan_dir: Path, repo: Path, progress=None, resume: bool = False):
    return execute_plan(
        plan_dir,
        resume=resume,
        repo_root=repo,
        timeout_seconds=20.0,
        poll_interval=0.05,
        kill_grace_seconds=1.0,
        progress=progress,
    )


def test_two_task_plan_passes(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    messages: list[str] = []
    status = run_plan(plan_dir, repo, progress=messages.append)
    assert status == "completed"
    assert (repo / "file_1.1.txt").is_file()
    assert (repo / "file_1.2.txt").is_file()

    events = list(replay(journal_path(plan_dir)))
    assert isinstance(events[0], RunStarted)
    attempt_events = [e for e in events if isinstance(e, AttemptStarted)]
    # Scheduler write-ahead + executor post-spawn (with pid) for each task,
    # plus the scheduler's record for the phase-review node.
    assert {e.node_id for e in attempt_events} == {"1.1", "1.2", "phase-review:1"}
    assert any(e.pid is not None for e in attempt_events if e.node_id == "1.1")
    signal_events = [e for e in events if isinstance(e, SignalObserved)]
    assert {e.event for e in signal_events} >= {"SessionStart", "Stop"}
    assert any(e.session_id == "fake-1.1" for e in signal_events)
    commit_events = [e for e in events if isinstance(e, CommitRecorded)]
    assert {e.node_id for e in commit_events} == {"1.1", "1.2"}
    gate_results = [e for e in events if isinstance(e, GateResult)]
    assert {(e.node_id, e.gate, e.passed) for e in gate_results} >= {
        ("1.1", "mechanical", True),
        ("1.2", "mechanical", True),
        ("phase-review:1", "phase-review", True),
    }
    passed = [e for e in events if isinstance(e, TaskStateChanged) and e.new_state == "passed"]
    assert {e.node_id for e in passed} == {"1.1", "1.2", "phase-review:1"}
    assert any("1.1: pending -> running" in m for m in messages)


def test_dirty_tree_at_start_refused(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    (repo / "uncommitted.txt").write_text("dirt\n")
    with pytest.raises(RunError) as exc_info:
        run_plan(plan_dir, repo)
    assert "uncommitted.txt" in str(exc_info.value)
    # Refused before any journal write.
    assert not journal_path(plan_dir).exists()


def test_mid_run_user_edit_pauses(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)

    def sabotage_after_first_task(message: str) -> None:
        if message.startswith("1.1: gate-checking -> passed"):
            (repo / "user_edit.txt").write_text("surprise\n")

    status = run_plan(plan_dir, repo, progress=sabotage_after_first_task)
    assert status == "paused"
    events = list(replay(journal_path(plan_dir)))
    paused = [e for e in events if isinstance(e, RunPaused)]
    assert [e.reason for e in paused] == ["dirty-tree"]
    # The second task never ran a worker.
    assert not (repo / "file_1.2.txt").exists()


def test_missing_commit_fails_task(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, STOP_WITHOUT_COMMIT, review="none")
    status = run_plan(plan_dir, repo)
    assert status == "failed"
    events = list(replay(journal_path(plan_dir)))
    gate_results = [e for e in events if isinstance(e, GateResult) and e.node_id == "1.1"]
    assert gate_results[-1].passed is False
    assert gate_results[-1].findings is not None
    assert "produced no commit" in gate_results[-1].findings


def test_unknown_worker_fails_fast(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    plan_yaml = plan_dir / "plan.yaml"
    plan_yaml.write_text(plan_yaml.read_text().replace("worker: fake-worker", "worker: no-such-worker"))
    with pytest.raises(ManifestError) as exc_info:
        run_plan(plan_dir, repo)
    assert "no-such-worker" in str(exc_info.value)
    assert not journal_path(plan_dir).exists()


def test_status_command_renders_snapshot(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    assert run_plan(plan_dir, repo) == "completed"
    result = CliRunner().invoke(app, ["status", str(plan_dir)])
    assert result.exit_code == 0
    assert "1.1" in result.output
    assert "passed" in result.output
    json_result = CliRunner().invoke(app, ["status", str(plan_dir), "--json"])
    assert json_result.exit_code == 0
    assert '"run_status"' in json_result.output
