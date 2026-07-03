"""End-to-end matrix: the full run loop driven by scenario fake workers.

No LLM, no network — a scripted sys.executable worker emits the same
hook-shaped signals real workers produce and makes real git commits.
"""

import subprocess
import sys
import time
from pathlib import Path

import yaml

from coordinator.journal import CommitRecorded
from coordinator.journal import GateResult
from coordinator.journal import TaskStateChanged
from coordinator.journal import load_snapshot
from coordinator.journal import replay
from coordinator.run import execute_plan
from coordinator.statedir import journal_path
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
) -> tuple[Path, Path, Path]:
    """A git repo containing a plan wired to the scenario fake worker.

    Returns (repo, plan_dir, scenario_dir).
    """
    repo = make_git_repo(tmp_path / "repo")
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    script = tmp_path / "scenario_worker.py"
    script.write_text(SCENARIO_WORKER)
    write_scenario_registration_yaml(repo / ".sculptor" / "workers", "fake-scenario", script, scenario_dir, mode)
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    manifest = {
        "version": 1,
        "defaults": {
            "worker": "fake-scenario",
            "verification": verification if verification is not None else ["true"],
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


def test_all_pass_three_tasks_two_phases(tmp_path: Path) -> None:
    phases = [
        {"id": 1, "name": "P1", "review": "agentic", "tasks": [task_entry("1.1"), task_entry("1.2", ["1.1"])]},
        {"id": 2, "name": "P2", "review": "none", "tasks": [task_entry("2.1")]},
    ]
    repo, plan_dir, scenario_dir = make_plan(tmp_path, phases)
    for node_id in ("1.1", "1.2", "2.1"):
        write_scenario(scenario_dir, node_id, 0, pass_actions(node_id))
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


def test_resume_after_kill_skips_completed_tasks(tmp_path: Path) -> None:
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

    assert run_plan(plan_dir, repo, resume=True) == "completed"
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
