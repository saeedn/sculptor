"""End-to-end matrix: the full run loop driven by scenario fake workers.

No LLM, no network — a scripted sys.executable worker emits the same
hook-shaped signals real workers produce and makes real git commits.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import yaml
from typer.testing import CliRunner

from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import ControlIntent
from coordinator.journal import GateResult
from coordinator.journal import Journal
from coordinator.journal import ReviewHandoff
from coordinator.journal import RunPaused
from coordinator.journal import TaskStateChanged
from coordinator.journal import load_snapshot
from coordinator.journal import replay
from coordinator.main import app as cli_app
from coordinator.run import execute_plan
from coordinator.statedir import journal_path
from coordinator.statedir import read_run_id
from tests.fakes import SCENARIO_WORKER
from tests.fakes import make_git_repo
from tests.fakes import pass_actions
from tests.fakes import write_scenario
from tests.fakes import write_scenario_registration_yaml


def make_plan(
    tmp_path: Path,
    phases: list[dict],
    verification: list[str] | None = None,
    mode: str = "print",
    defaults_extra: dict | None = None,
) -> tuple[Path, Path, Path]:
    """A git repo containing a plan wired to the scenario fake worker.

    Returns (repo, plan_dir, scenario_dir).
    """
    repo = make_git_repo(tmp_path / "repo")
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    script = tmp_path / "scenario_worker.py"
    script.write_text(SCENARIO_WORKER)
    workers_dir = repo / ".sculptor" / "workers"
    write_scenario_registration_yaml(workers_dir, "fake-scenario", script, scenario_dir, mode)
    write_scenario_registration_yaml(workers_dir, "fake-escalation", script, scenario_dir, mode)
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    manifest = {
        "version": 1,
        "defaults": {
            "worker": "fake-scenario",
            "verification": verification if verification is not None else ["true"],
            **(defaults_extra or {}),
        },
        "phases": phases,
    }
    (plan_dir / "plan.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    for phase in phases:
        for task in phase["tasks"]:
            (plan_dir / task["file"]).write_text(f"# Task {task['id']}\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add plan"], check=True)
    return repo, plan_dir, scenario_dir


def run_plan(plan_dir: Path, repo: Path, resume: bool = False, trust_home: Path | None = None):
    return execute_plan(
        plan_dir,
        resume=resume,
        repo_root=repo,
        timeout_seconds=30.0,
        poll_interval=0.05,
        kill_grace_seconds=1.0,
        trust_home=trust_home,
    )


def git_log_messages(repo: Path) -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(repo), "log", "--reverse", "--format=%s"], capture_output=True, text=True, check=True
    ).stdout
    return output.splitlines()


def task_entry(task_id: str, deps: list[str] | None = None, **extra) -> dict:
    return {"id": task_id, "file": f"{task_id.replace('.', '_')}.md", "deps": deps or [], **extra}


def passing_review_actions() -> list[dict]:
    return [{"signal": "SessionStart"}, {"verdict": {"pass": True, "findings": []}}, {"signal": "Stop"}]


def test_all_pass_three_tasks_two_phases(tmp_path: Path) -> None:
    phases = [
        {"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1"), task_entry("1.2", ["1.1"])]},
        {"id": 2, "name": "P2", "review": "none", "tasks": [task_entry("2.1")]},
    ]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    for node_id in ("1.1", "1.2", "2.1"):
        write_scenario(scenario_dir, node_id, 0, pass_actions(node_id))
    # The phase-boundary agentic review runs a real (fake) reviewer.
    write_scenario(scenario_dir, "phase-review:1", 0, passing_review_actions())
    assert run_plan(plan_dir, repo) == "completed"
    messages = git_log_messages(repo)
    # Deps honored: commits land in dependency order.
    assert messages[-3:] == ["fake commit for 1.1", "fake commit for 1.2", "fake commit for 2.1"]
    snapshot = load_snapshot(plan_dir)
    assert {n.state for n in snapshot.nodes.values()} == {"passed"}
    commit_nodes = {e.node_id for e in replay(journal_path(plan_dir)) if isinstance(e, CommitRecorded)}
    assert commit_nodes == {"1.1", "1.2", "2.1"}


def test_gate_fail_no_commit_blocks_dependents_not_independent(tmp_path: Path) -> None:
    phases = [
        {
            "id": 1,
            "name": "P1",
            "review": "none",
            "tasks": [task_entry("a"), task_entry("b", ["a"]), task_entry("c")],
        }
    ]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    # "a" stops without committing; "c" is independent and passes.
    write_scenario(scenario_dir, "a", 0, [{"signal": "SessionStart"}, {"signal": "Stop"}])
    write_scenario(scenario_dir, "c", 0, pass_actions("c"))
    assert run_plan(plan_dir, repo) == "failed"
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["a"].state == "failed"
    # "b" never started — a never-touched node has no snapshot entry.
    assert "b" not in snapshot.nodes
    assert snapshot.nodes["c"].state == "passed"
    gate_results = [e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult) and e.node_id == "a"]
    assert gate_results[-1].passed is False
    assert gate_results[-1].findings is not None
    assert "produced no commit" in gate_results[-1].findings


def test_worker_exits_without_stop_fails(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, [{"signal": "SessionStart"}])
    assert run_plan(plan_dir, repo) == "failed"
    # A lifecycle failure never reaches the gates: the scheduler fails
    # the node directly with the launcher's distinct error as reason.
    failures = [
        e
        for e in replay(journal_path(plan_dir))
        if isinstance(e, TaskStateChanged) and e.node_id == "a" and e.new_state == "failed"
    ]
    assert failures[-1].reason == "attempt exited-without-stop"


def test_no_change_task_passes_without_commit(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a", no_change=True)]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, [{"signal": "SessionStart"}, {"signal": "Stop"}])
    assert run_plan(plan_dir, repo) == "completed"
    assert load_snapshot(plan_dir).nodes["a"].state == "passed"
    assert load_snapshot(plan_dir).nodes["a"].commits == []


def test_verification_failure_fails_gate_with_log(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases, verification=["echo verifying && false"])
    write_scenario(scenario_dir, "a", 0, pass_actions("a"))
    assert run_plan(plan_dir, repo) == "failed"
    log = plan_dir / "_state" / "attempts" / "a" / "0" / "gate_mechanical_0.log"
    assert log.read_text() == "verifying\n"
    gate_results = [e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult)]
    assert gate_results[-1].findings is not None
    assert "echo verifying && false" in gate_results[-1].findings


def test_interactive_mode_all_pass(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases, mode="interactive")
    write_scenario(scenario_dir, "a", 0, pass_actions("a"))
    trust_home = tmp_path / "home"
    trust_home.mkdir()
    assert run_plan(plan_dir, repo, trust_home=trust_home) == "completed"
    # The PTY path ran: output was drained and trust was seeded in the
    # injected (fake) home, never the real one.
    assert (plan_dir / "_state" / "attempts" / "a" / "0" / "pty_output.raw").exists()
    assert str(repo.resolve()) in (trust_home / ".claude.json").read_text()


def failing_review_actions(task_id: str | None) -> list[dict]:
    return [
        {"signal": "SessionStart"},
        {
            "verdict": {
                "pass": False,
                "findings": [
                    {"task_id": task_id, "severity": "blocker", "summary": "wrong output", "detail": "off by one"}
                ],
            }
        },
        {"signal": "Stop"},
    ]


def test_phase_review_reopen_then_pass(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    # The reopened task re-runs (its file already exists; recommit a fix).
    write_scenario(
        scenario_dir,
        "1.1",
        1,
        [
            {"signal": "SessionStart"},
            {"write": {"path": "file_1.1.txt", "content": "fixed content\n"}},
            {"commit": "fix for review findings"},
            {"signal": "Stop"},
        ],
    )
    write_scenario(scenario_dir, "phase-review:1", 0, failing_review_actions("1.1"))
    write_scenario(scenario_dir, "phase-review:1", 1, passing_review_actions())
    assert run_plan(plan_dir, repo) == "completed"
    events = list(replay(journal_path(plan_dir)))
    reopens = [
        e
        for e in events
        if isinstance(e, TaskStateChanged) and e.node_id == "1.1" and e.reason == "phase-review-reopen"
    ]
    assert len(reopens) == 1
    # The reopened attempt was seeded with the review findings.
    context = plan_dir / "_state" / "attempts" / "1.1" / "1" / "context.md"
    assert "wrong output" in context.read_text()
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["1.1"].state == "passed"
    assert snapshot.nodes["phase-review:1"].state == "passed"


def test_phase_review_fails_twice_waits_for_human(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    # Findings with no task attribution: the review itself retries, then
    # the second failure escalates to a human.
    write_scenario(scenario_dir, "phase-review:1", 0, failing_review_actions(None))
    write_scenario(scenario_dir, "phase-review:1", 1, failing_review_actions(None))
    assert run_plan(plan_dir, repo) == "waiting-human"
    assert load_snapshot(plan_dir).nodes["phase-review:1"].state == "waiting-human"


def test_per_task_agentic_gate_passes(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("1.1", gates=["mechanical", "agentic"])]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    write_scenario(scenario_dir, "1.1.review", 0, passing_review_actions())
    assert run_plan(plan_dir, repo) == "completed"
    gate_results = [e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult) and e.node_id == "1.1"]
    assert {(e.gate, e.passed) for e in gate_results} == {("mechanical", True), ("agentic", True)}


def test_reviewer_without_verdict_fails_closed(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    # Reviewer stops cleanly but never writes verdict.json; the retried
    # review (no attempt-1 scenario) crashes, so a human is needed.
    write_scenario(scenario_dir, "phase-review:1", 0, [{"signal": "SessionStart"}, {"signal": "Stop"}])
    assert run_plan(plan_dir, repo) == "waiting-human"
    gate_results = [
        e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult) and e.node_id == "phase-review:1"
    ]
    assert gate_results[0].passed is False
    assert gate_results[0].findings is not None
    assert "no valid verdict" in gate_results[0].findings


def test_reviewer_that_commits_voids_the_review(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    write_scenario(
        scenario_dir,
        "phase-review:1",
        0,
        [
            {"signal": "SessionStart"},
            {"write": {"path": "reviewer_sneaky.txt", "content": "x"}},
            {"commit": "reviewer should not commit"},
            {"verdict": {"pass": True, "findings": []}},
            {"signal": "Stop"},
        ],
    )
    assert run_plan(plan_dir, repo) == "waiting-human"
    gate_results = [
        e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult) and e.node_id == "phase-review:1"
    ]
    assert gate_results[0].passed is False
    assert gate_results[0].findings is not None
    assert "reviewer modified the repository" in gate_results[0].findings


def stop_without_commit_actions() -> list[dict]:
    return [{"signal": "SessionStart"}, {"signal": "Stop"}]


def test_retry_after_gate_failure_succeeds(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, stop_without_commit_actions())
    write_scenario(scenario_dir, "a", 1, pass_actions("a"))
    assert run_plan(plan_dir, repo) == "completed"
    events = list(replay(journal_path(plan_dir)))
    retries = [e for e in events if isinstance(e, TaskStateChanged) and e.reason == "retry"]
    assert len(retries) == 1
    # The retry attempt was seeded with the prior gate findings.
    context = plan_dir / "_state" / "attempts" / "a" / "1" / "context.md"
    assert "produced no commit" in context.read_text()
    assert load_snapshot(plan_dir).nodes["a"].state == "passed"


def test_escalation_uses_escalation_registration_with_full_history(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(
        tmp_path, phases, defaults_extra={"escalation_worker": "fake-escalation", "attempts": 2}
    )
    write_scenario(scenario_dir, "a", 0, stop_without_commit_actions())
    write_scenario(scenario_dir, "a", 1, stop_without_commit_actions())
    write_scenario(scenario_dir, "a", 2, pass_actions("a"))
    assert run_plan(plan_dir, repo) == "completed"
    events = list(replay(journal_path(plan_dir)))
    attempt_2 = [e for e in events if isinstance(e, AttemptStarted) and e.node_id == "a" and e.attempt_index == 2]
    assert all(e.worker_registration == "fake-escalation" for e in attempt_2)
    assert attempt_2
    escalations = [e for e in events if isinstance(e, TaskStateChanged) and e.reason == "escalate"]
    assert len(escalations) == 1
    # The escalated attempt sees ALL prior attempts' failure context.
    context = (plan_dir / "_state" / "attempts" / "a" / "2" / "context.md").read_text()
    assert "Attempt 0" in context
    assert "Attempt 1" in context


def test_exhausted_ladder_fails_with_report(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a"), task_entry("c")]}]
    repo, plan_dir, scenario_dir = make_plan(
        tmp_path, phases, defaults_extra={"escalation_worker": "fake-escalation", "attempts": 2}
    )
    for attempt in (0, 1, 2):
        write_scenario(scenario_dir, "a", attempt, stop_without_commit_actions())
    write_scenario(scenario_dir, "c", 0, pass_actions("c"))
    assert run_plan(plan_dir, repo) == "failed"
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["a"].state == "failed"
    assert snapshot.nodes["c"].state == "passed"
    report = (plan_dir / "_state" / "failure_report.md").read_text()
    assert "## Node a" in report
    assert "fake-a-" in report
    assert "claude --resume" in report
    assert "fake-escalation" in report


def test_rate_limited_attempt_pauses_without_burning_budget(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    # attempts=1: if the rate-limited attempt burned budget, the retry
    # after resume would already be exhausted.
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases, defaults_extra={"attempts": 1})
    write_scenario(
        scenario_dir,
        "a",
        0,
        [
            {"transcript": "Error: You've reached your usage limit. resets at 2026-07-03T18:00:00Z\n"},
            {"signal": "SessionStart"},
        ],
    )
    write_scenario(scenario_dir, "a", 1, pass_actions("a"))
    assert run_plan(plan_dir, repo) == "paused"
    events = list(replay(journal_path(plan_dir)))
    paused = [e for e in events if isinstance(e, RunPaused)]
    assert paused[-1].reason == "rate-limit"
    assert paused[-1].resume_hint is not None
    assert "resets at" in paused[-1].resume_hint
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["a"].state == "pending"
    assert "rate-limited" in snapshot.nodes["a"].attempts[0].signals
    # Re-running the coordinator continues and completes.
    assert run_plan(plan_dir, repo, resume=True) == "completed"
    assert load_snapshot(plan_dir).nodes["a"].state == "passed"


def test_human_phase_review_waits_and_approves(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "human", "tasks": [task_entry("1.1")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "1.1", 0, pass_actions("1.1"))
    assert run_plan(plan_dir, repo) == "waiting-human"
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["phase-review:1"].state == "waiting-human"
    # The phase diff was written for presentation.
    diff = (plan_dir / "_state" / "attempts" / "phase-review_1" / "0" / "human_review.patch").read_text()
    assert "file_1.1.txt" in diff
    # Approve via the CLI escape hatch, then resume.
    result = CliRunner().invoke(cli_app, ["intent", str(plan_dir), "approve", "phase-review:1"])
    assert result.exit_code == 0
    assert run_plan(plan_dir, repo, resume=True) == "completed"
    gate_results = [
        e for e in replay(journal_path(plan_dir)) if isinstance(e, GateResult) and e.node_id == "phase-review:1"
    ]
    assert gate_results[-1].gate == "human"
    assert gate_results[-1].passed is True
    assert gate_results[-1].findings == "approved by user"


def test_human_gated_task_blocks_then_approves(tmp_path: Path) -> None:
    phases = [
        {
            "id": 1,
            "name": "P1",
            "review": "none",
            "tasks": [task_entry("a", gates=["mechanical", "human"]), task_entry("b", ["a"])],
        }
    ]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, pass_actions("a"))
    write_scenario(scenario_dir, "b", 0, pass_actions("b"))
    assert run_plan(plan_dir, repo) == "waiting-human"
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["a"].state == "waiting-human"
    # Commits were recorded before the human wait, and the task diff is
    # presented from the implementer's attempt dir.
    assert snapshot.nodes["a"].commits
    diff = (plan_dir / "_state" / "attempts" / "a" / "0" / "human_review.patch").read_text()
    assert "file_a.txt" in diff
    result = CliRunner().invoke(cli_app, ["intent", str(plan_dir), "approve", "a"])
    assert result.exit_code == 0
    assert run_plan(plan_dir, repo, resume=True) == "completed"
    assert load_snapshot(plan_dir).nodes["b"].state == "passed"


def test_intent_cli_validates(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    _, plan_dir, _ = make_plan(tmp_path, phases)
    runner = CliRunner()
    assert runner.invoke(cli_app, ["intent", str(plan_dir), "bogus"]).exit_code == 1
    assert runner.invoke(cli_app, ["intent", str(plan_dir), "retry"]).exit_code == 1
    assert runner.invoke(cli_app, ["intent", str(plan_dir), "retry", "no-such-node"]).exit_code == 1
    assert runner.invoke(cli_app, ["intent", str(plan_dir), "pause"]).exit_code == 0


def test_abort_kills_in_flight_worker(tmp_path: Path) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, [{"signal": "SessionStart"}, {"sleep": 60}])

    result_holder: dict = {}
    thread = threading.Thread(target=lambda: result_holder.update(status=run_plan(plan_dir, repo)), daemon=True)
    thread.start()

    def worker_pid() -> int | None:
        if not journal_path(plan_dir).is_file():
            return None
        for event in replay(journal_path(plan_dir)):
            if isinstance(event, AttemptStarted) and event.pid is not None:
                return event.pid
        return None

    deadline = time.monotonic() + 20
    pid = None
    while time.monotonic() < deadline and pid is None:
        pid = worker_pid()
        time.sleep(0.05)
    assert pid is not None
    assert psutil.pid_exists(pid)
    Journal(journal_path(plan_dir)).append(ControlIntent(intent="abort"))
    thread.join(timeout=20)
    assert not thread.is_alive()
    assert result_holder["status"] == "aborted"
    assert not psutil.pid_exists(pid)
    assert load_snapshot(plan_dir).nodes["a"].state == "failed"


def use_fake_sculpt(tmp_path: Path, monkeypatch, workspace_env: bool = False) -> Path:
    """A fake `sculpt` on PATH + SCULPT_AGENT_ID: signaling turns on against it.

    With ``workspace_env`` the full in-Sculptor env is simulated and the
    fake answers `agent create` with a JSON id, so the Review handoff
    engages too.
    """
    bin_dir = tmp_path / "sculpt-bin"
    bin_dir.mkdir(exist_ok=True)
    log_path = tmp_path / "sculpt_calls.log"
    script = bin_dir / "sculpt"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{log_path}"\n'
        'if [ "$1" = "agent" ] && [ "$2" = "create" ]; then\n'
        '  echo \'{"id": "tsk_review123"}\'\n'
        "fi\n"
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SCULPT_AGENT_ID", "tsk_fake")
    if workspace_env:
        monkeypatch.setenv("SCULPT_WORKSPACE_ID", "ws_fake")
    return log_path


def test_signal_sequence_with_fake_sculpt(tmp_path: Path, monkeypatch) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a"), task_entry("b", ["a"])]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, pass_actions("a"))
    write_scenario(scenario_dir, "b", 0, pass_actions("b"))
    log_path = use_fake_sculpt(tmp_path, monkeypatch)
    assert run_plan(plan_dir, repo) == "completed"
    signals = log_path.read_text().splitlines()
    run_id = read_run_id(plan_dir)
    assert run_id is not None
    # The coordinator's session id IS its run id, reported before work starts.
    assert signals[0] == f"signal session-id {run_id}"
    assert signals[1] == "signal busy"
    # One files-changed per task commit keeps the diff viewer live.
    assert signals.count("signal files-changed") == 2
    assert signals[-1] == "signal idle"


def test_review_handoff_spawns_agent_after_full_success(tmp_path: Path, monkeypatch) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, pass_actions("a"))
    log_path = use_fake_sculpt(tmp_path, monkeypatch, workspace_env=True)
    assert run_plan(plan_dir, repo) == "completed"
    log = log_path.read_text()
    calls = log.splitlines()
    assert "agent create --harness Claude CLI --json" in calls
    send_calls = [line for line in calls if line.startswith("agent send tsk_review123")]
    assert len(send_calls) == 1
    # The multiline seed is one send argument, spread over log lines by echo.
    assert "/sculptor-workflow:review" in log
    assert f"Plan folder: {plan_dir.resolve()}" in log
    # The handoff happens before the final idle signal and is journaled.
    assert calls[-1] == "signal idle"
    events = list(replay(journal_path(plan_dir)))
    handoffs = [e for e in events if isinstance(e, ReviewHandoff)]
    assert [e.agent_id for e in handoffs] == ["tsk_review123"]
    assert load_snapshot(plan_dir).review_agent_id == "tsk_review123"


def test_no_review_handoff_on_failed_run(tmp_path: Path, monkeypatch) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, stop_without_commit_actions())
    log_path = use_fake_sculpt(tmp_path, monkeypatch, workspace_env=True)
    assert run_plan(plan_dir, repo) == "failed"
    assert "agent create --harness Claude CLI --json" not in log_path.read_text()


def test_signal_waiting_on_failed_run(tmp_path: Path, monkeypatch) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("a")]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    write_scenario(scenario_dir, "a", 0, stop_without_commit_actions())
    log_path = use_fake_sculpt(tmp_path, monkeypatch)
    assert run_plan(plan_dir, repo) == "failed"
    # A failure report needs the user's attention: waiting, not idle.
    assert log_path.read_text().splitlines()[-1] == "signal waiting"


RESUME_DRIVER = """\
import sys
from pathlib import Path
from coordinator.run import execute_plan
execute_plan(
    Path(sys.argv[1]),
    repo_root=Path(sys.argv[2]),
    timeout_seconds=60.0,
    poll_interval=0.05,
    kill_grace_seconds=1.0,
)
"""


def wait_for_journal(plan_dir: Path, predicate, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    path = journal_path(plan_dir)
    while time.monotonic() < deadline:
        if path.is_file() and predicate(path.read_text()):
            return
        time.sleep(0.05)
    raise AssertionError("journal condition not reached within timeout")


def test_resume_after_kill_skips_completed_tasks(tmp_path: Path, monkeypatch) -> None:
    phases = [{"id": 1, "name": "P1", "review": "none", "tasks": [task_entry("t1"), task_entry("t2", ["t1"])]}]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    # t1 passes on attempt 0 and has NO scenario for attempt 1 — a re-run
    # would crash and fail the resumed run.
    write_scenario(scenario_dir, "t1", 0, pass_actions("t1"))
    # t2's first attempt hangs (no Stop); the coordinator dies mid-flight.
    write_scenario(scenario_dir, "t2", 0, [{"signal": "SessionStart"}, {"sleep": 30}])
    write_scenario(scenario_dir, "t2", 1, pass_actions("t2"))

    coordinator = subprocess.Popen(
        [sys.executable, "-c", RESUME_DRIVER, str(plan_dir), str(repo)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Kill only once t2 is provably mid-flight (t1 fully passed).
        wait_for_journal(plan_dir, lambda text: '"type":"attempt-started"' in text and '"node_id":"t2"' in text)
        coordinator.kill()
    finally:
        coordinator.wait(timeout=10)

    # Resume through the CLI path: `coordinator resume <run-id>` discovers
    # the plan by its recorded run id from the working directory.
    run_id = read_run_id(plan_dir)
    assert run_id is not None
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(cli_app, ["resume", run_id])
    assert result.exit_code == 0, result.output
    events = list(replay(journal_path(plan_dir)))
    # The mid-flight t2 attempt was discarded and re-ran as attempt 1.
    discards = [
        e for e in events if isinstance(e, TaskStateChanged) and e.reason == "resume-discard" and e.node_id == "t2"
    ]
    assert len(discards) == 1
    # t1 never got a second attempt.
    assert '"node_id":"t1","attempt_index":1' not in journal_path(plan_dir).read_text()
    assert git_log_messages(repo)[-2:] == ["fake commit for t1", "fake commit for t2"]
    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["t1"].state == "passed"
    assert snapshot.nodes["t2"].state == "passed"
    assert [a.attempt_index for a in snapshot.nodes["t2"].attempts] == [0, 1]
