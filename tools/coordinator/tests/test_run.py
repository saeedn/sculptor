import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import GateResult
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.main import app
from coordinator.manifest import ManifestError
from coordinator.run import RunError
from coordinator.run import execute_plan
from coordinator.run import find_incomplete_plans
from coordinator.run import find_plan_by_run_id
from coordinator.run import iter_plan_dirs
from coordinator.statedir import attempt_dir
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.statedir import read_run_id
from coordinator.statedir import write_run_id
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


def make_plan_repo(tmp_path: Path, worker_script_body: str, review: str = "none") -> tuple[Path, Path]:
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
    # Scheduler write-ahead + executor post-spawn (with pid) per task.
    assert {e.node_id for e in attempt_events} == {"1.1", "1.2"}
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
    }
    passed = [e for e in events if isinstance(e, TaskStateChanged) and e.new_state == "passed"]
    assert {e.node_id for e in passed} == {"1.1", "1.2"}
    assert any("1.1: pending -> running" in m for m in messages)


def test_run_over_existing_state_resumes_instead_of_restarting(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    messages: list[str] = []
    assert run_plan(plan_dir, repo, progress=messages.append) == "completed"
    first_run_id = read_run_id(plan_dir)
    messages.clear()
    # A re-issued launch command (Sculptor tab restart) must continue the
    # recorded run — never reuse attempt dirs or interleave a second run.
    assert run_plan(plan_dir, repo, progress=messages.append) == "completed"
    assert any("existing run state found" in m for m in messages)
    assert read_run_id(plan_dir) == first_run_id
    events = list(replay(journal_path(plan_dir)))
    # Exactly one run and no re-attempts: the completed tasks stay done.
    assert len([e for e in events if isinstance(e, RunStarted)]) == 1
    assert not any(isinstance(e, AttemptStarted) and e.attempt_index > 0 for e in events)


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


def test_iter_plan_dirs_prunes_state_and_git(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "plan.yaml").touch()
    (tmp_path / "b" / "nested").mkdir(parents=True)
    (tmp_path / "b" / "nested" / "plan.yaml").touch()
    # plan.yaml files inside pruned dirs must not be found (fake-worker
    # tests create whole git repos under _state/attempts/*).
    (tmp_path / "a" / "_state" / "attempts").mkdir(parents=True)
    (tmp_path / "a" / "_state" / "attempts" / "plan.yaml").touch()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "plan.yaml").touch()
    found = sorted(iter_plan_dirs(tmp_path))
    assert found == [tmp_path / "a", tmp_path / "b" / "nested"]


def test_find_plan_by_run_id(tmp_path: Path) -> None:
    for name, run_id in (("one", "run-first"), ("two", "run-second")):
        plan_dir = tmp_path / "plans" / name
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.yaml").touch()
        ensure_state_dir(plan_dir)
        write_run_id(plan_dir, run_id)
    assert find_plan_by_run_id(tmp_path, "run-second") == tmp_path / "plans" / "two"
    with pytest.raises(RunError) as exc_info:
        find_plan_by_run_id(tmp_path, "run-missing")
    assert "run-missing" in str(exc_info.value)
    assert str(tmp_path) in str(exc_info.value)


def test_find_incomplete_plans(tmp_path: Path) -> None:
    # A completed run is excluded; a started-but-unfinished one is listed.
    complete_repo, complete_plan = make_plan_repo(tmp_path / "complete", COMMIT_THEN_STOP)
    assert run_plan(complete_plan, complete_repo) == "completed"
    incomplete_repo, incomplete_plan = make_plan_repo(tmp_path / "incomplete", COMMIT_THEN_STOP)
    ensure_state_dir(incomplete_plan)
    Journal(journal_path(incomplete_plan)).append(
        RunStarted(run_id="run-incomplete", plan_dir=str(incomplete_plan), manifest_hash="h")
    )
    plans = find_incomplete_plans(tmp_path)
    assert [plan.plan_dir for plan in plans] == [incomplete_plan]
    assert plans[0].run_id == "run-incomplete"
    assert plans[0].completed == 0
    assert plans[0].total == 2


def test_no_args_picker_resumes_selected_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    ensure_state_dir(plan_dir)
    Journal(journal_path(plan_dir)).append(RunStarted(run_id="run-picker", plan_dir=str(plan_dir), manifest_hash="h"))
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["run"], input="1\n")
    assert result.exit_code == 0, result.output
    assert "run-picker" in result.output
    assert "1." in result.output


def test_no_args_picker_with_no_incomplete_plans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run"])
    assert result.exit_code == 1


def test_unknown_per_task_escalation_worker_fails_fast(tmp_path: Path) -> None:
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    plan = (plan_dir / "plan.yaml").read_text()
    plan = plan.replace(
        "        file: 01_01_first.md\n", "        file: 01_01_first.md\n        escalation_worker: no-such-worker\n"
    )
    (plan_dir / "plan.yaml").write_text(plan)
    subprocess.run(["git", "-C", str(repo), "commit", "-aqm", "edit plan"], check=True)
    with pytest.raises(ManifestError, match="no-such-worker"):
        run_plan(plan_dir, repo)


def test_resume_gates_a_completed_but_ungated_attempt(tmp_path: Path) -> None:
    """A coordinator dies after its worker's Stop lands but before consuming
    it; the resumed coordinator must gate the finished attempt, not redo it."""
    repo, plan_dir = make_plan_repo(tmp_path, COMMIT_THEN_STOP)
    base_commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    # The dead run's worker committed its work...
    (repo / "file_1.1.txt").write_text("content from the dead run\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "fake commit for 1.1"], check=True)
    # ...and its Stop reached signals.jsonl, unconsumed.
    attempt = attempt_dir(plan_dir, "1.1", 0)
    attempt.mkdir(parents=True)
    with open(attempt / "signals.jsonl", "w") as f:
        f.write(
            json.dumps(
                {
                    "event": "SessionStart",
                    "ts": 1.0,
                    "payload": {"session_id": "dead-sess", "transcript_path": "/tmp/dead.jsonl"},
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {"event": "Stop", "ts": 2.0, "payload": {"session_id": "dead-sess", "last_assistant_message": "done"}}
            )
            + "\n"
        )
    ensure_state_dir(plan_dir)
    journal = Journal(journal_path(plan_dir))
    journal.append(RunStarted(run_id="run-dead", plan_dir=str(plan_dir), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"))
    journal.append(
        AttemptStarted(node_id="1.1", attempt_index=0, worker_registration="fake-worker", attempt_dir=str(attempt))
    )
    journal.append(
        AttemptStarted(
            node_id="1.1",
            attempt_index=0,
            worker_registration="fake-worker",
            attempt_dir=str(attempt),
            base_commit=base_commit,
        )
    )
    write_run_id(plan_dir, "run-dead")

    assert run_plan(plan_dir, repo, resume=True) == "completed"

    events = list(replay(journal_path(plan_dir)))
    # 1.1 was gated, never re-attempted.
    assert not any(isinstance(e, AttemptStarted) and e.node_id == "1.1" and e.attempt_index == 1 for e in events)
    resumes = [e for e in events if isinstance(e, TaskStateChanged) and e.reason == "resume-gates"]
    assert [(e.node_id, e.old_state, e.new_state) for e in resumes] == [
        ("1.1", "running", "pending"),
        ("1.1", "pending", "running"),
    ]
    gate_results = [e for e in events if isinstance(e, GateResult) and e.node_id == "1.1"]
    assert gate_results and gate_results[-1].passed is True
    commits = [e for e in events if isinstance(e, CommitRecorded) and e.node_id == "1.1"]
    assert len(commits) == 1
    # The dead run's work was preserved, not redone by a fresh worker.
    assert (repo / "file_1.1.txt").read_text() == "content from the dead run\n"
    # The rest of the plan proceeded normally.
    assert (repo / "file_1.2.txt").is_file()
