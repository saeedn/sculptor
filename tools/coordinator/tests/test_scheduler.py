from pathlib import Path

import pytest

from coordinator.dag import Node
from coordinator.dag import build_graph
from coordinator.journal import AttemptStarted
from coordinator.journal import ControlIntent
from coordinator.journal import ControlIntentName
from coordinator.journal import Journal
from coordinator.journal import RunStarted
from coordinator.journal import Snapshot
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.manifest import ManifestDefaults
from coordinator.manifest import ManifestError
from coordinator.manifest import PhaseSpec
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec
from coordinator.scheduler import AttemptResult
from coordinator.scheduler import GateOutcome
from coordinator.scheduler import IllegalTransition
from coordinator.scheduler import NodeState
from coordinator.scheduler import Scheduler
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.statedir import read_run_id


class FakeExecutor:
    """Scripted executor: per-node queues of results; records call order."""

    def __init__(
        self,
        attempts: dict[str, list[AttemptResult]] | None = None,
        gates: dict[str, list[GateOutcome]] | None = None,
    ) -> None:
        self.attempts = attempts or {}
        self.gates = gates or {}
        self.calls: list[str] = []

    def run_attempt(self, node: Node, attempt_index: int, seed_context: str | None) -> AttemptResult:
        self.calls.append(f"attempt:{node.node_id}:{attempt_index}")
        queue = self.attempts.get(node.node_id)
        if queue:
            return queue.pop(0)
        return AttemptResult(ok=True)

    def run_gates(self, node: Node, result: AttemptResult) -> GateOutcome:
        self.calls.append(f"gates:{node.node_id}")
        queue = self.gates.get(node.node_id)
        if queue:
            return queue.pop(0)
        return GateOutcome(gate="mechanical", passed=True)


def make_manifest(tasks: list[TaskSpec]) -> PlanManifest:
    return PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[]),
        phases=[PhaseSpec(id=1, name="P", review="none", tasks=tasks)],
    )


def task(task_id: str, deps: list[str] | None = None, kind: str = "task") -> TaskSpec:
    return TaskSpec(id=task_id, file=f"{task_id}.md", deps=deps or [], kind=kind)


def make_scheduler(
    tmp_path: Path,
    manifest: PlanManifest,
    executor: FakeExecutor,
    reaped: list[int] | None = None,
    resume: bool = False,
) -> Scheduler:
    ensure_state_dir(tmp_path)
    graph = build_graph(manifest)
    journal = Journal(journal_path(tmp_path))
    reaper = (reaped if reaped is not None else []).append
    factory = Scheduler.load if resume else Scheduler
    return factory(tmp_path, manifest, graph, journal, executor, reaper)


def append_intent(tmp_path: Path, intent: ControlIntentName, node_id: str | None = None) -> None:
    ensure_state_dir(tmp_path)
    Journal(journal_path(tmp_path)).append(ControlIntent(intent=intent, node_id=node_id))


def test_happy_path_sequential_order(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b", ["a"]), task("c", ["b"])])
    executor = FakeExecutor()
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "completed"
    assert all(state == NodeState.PASSED for state in scheduler.states.values())
    # Each node is fully processed (attempt then gates) before the next starts.
    assert executor.calls == ["attempt:a:0", "gates:a", "attempt:b:0", "gates:b", "attempt:c:0", "gates:c"]
    events = list(replay(journal_path(tmp_path)))
    assert isinstance(events[0], RunStarted)
    assert read_run_id(tmp_path) == events[0].run_id


def test_gate_failure_blocks_dependents_but_not_independent_branch(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b", ["a"]), task("c", ["a"]), task("d", ["b"])])
    executor = FakeExecutor(gates={"b": [GateOutcome(gate="mechanical", passed=False, findings="boom")]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    assert scheduler.states["b"] == NodeState.FAILED
    assert scheduler.states["c"] == NodeState.PASSED
    assert scheduler.states["d"] == NodeState.PENDING
    assert "attempt:d:0" not in executor.calls


def test_attempt_failure_marks_failed(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    executor = FakeExecutor(attempts={"a": [AttemptResult(ok=False, error="crashed")]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    assert scheduler.states["a"] == NodeState.FAILED
    assert "gates:a" not in executor.calls


def test_pause_and_resume(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    append_intent(tmp_path, "pause")
    executor = FakeExecutor()
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "paused"
    assert executor.calls == []
    # Without a resume intent, a resumed run stays paused.
    still_paused = make_scheduler(tmp_path, manifest, FakeExecutor(), resume=True)
    assert still_paused.run() == "paused"
    append_intent(tmp_path, "resume")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert executor_2.calls == ["attempt:a:0", "gates:a"]


def test_consumed_intents_do_not_double_apply(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    append_intent(tmp_path, "pause")
    scheduler = make_scheduler(tmp_path, manifest, FakeExecutor())
    assert scheduler.run() == "paused"
    append_intent(tmp_path, "resume")
    resumed = make_scheduler(tmp_path, manifest, FakeExecutor(), resume=True)
    # The old pause intent is consumed; only the fresh resume applies.
    assert resumed.run() == "completed"


def test_retry_intent_reruns_failed_node(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b", ["a"])])
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="flaky")]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    append_intent(tmp_path, "retry", node_id="a")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    # Attempt history is preserved: the retry is attempt index 1.
    assert executor_2.calls == ["attempt:a:1", "gates:a", "attempt:b:0", "gates:b"]


def test_skip_intent_satisfies_dependents(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b", ["a"])])
    executor = FakeExecutor(attempts={"a": [AttemptResult(ok=False, error="crashed")]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    append_intent(tmp_path, "skip", node_id="a")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert resumed.states["a"] == NodeState.SKIPPED
    assert resumed.states["b"] == NodeState.PASSED
    assert executor_2.calls == ["attempt:b:0", "gates:b"]


def test_waiting_human_and_approve(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b", ["a"])])
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="human", passed=False, waiting_human=True)]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    assert scheduler.states["a"] == NodeState.WAITING_HUMAN
    append_intent(tmp_path, "approve", node_id="a")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert resumed.states["a"] == NodeState.PASSED
    # The approved node is not re-executed.
    assert executor_2.calls == ["attempt:b:0", "gates:b"]


def test_retry_intent_requeues_waiting_human(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="human", passed=False, waiting_human=True)]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    append_intent(tmp_path, "retry", node_id="a")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert executor_2.calls == ["attempt:a:1", "gates:a"]


def test_abort_intent_stops_run(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    append_intent(tmp_path, "abort")
    executor = FakeExecutor()
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "aborted"
    assert executor.calls == []
    snapshot = Snapshot.from_events(replay(journal_path(tmp_path)))
    assert snapshot.run_status == "paused"
    assert snapshot.pause_reason == "aborted"


def test_resume_discards_mid_flight_attempt_and_reaps(tmp_path: Path) -> None:
    manifest = make_manifest([task("a"), task("b")])
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    # A previous run: "a" completed, "b" was mid-flight when the
    # coordinator was killed (attempt-started with a recorded PID).
    journal.append(RunStarted(run_id="run-old", plan_dir=str(tmp_path), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="a", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="a", attempt_index=0, worker_registration="w", pid=11, attempt_dir="/a/0"))
    journal.append(TaskStateChanged(node_id="a", old_state="running", new_state="gate-checking"))
    journal.append(TaskStateChanged(node_id="a", old_state="gate-checking", new_state="passed"))
    journal.append(TaskStateChanged(node_id="b", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="b", attempt_index=0, worker_registration="w", pid=77, attempt_dir="/b/0"))
    executor = FakeExecutor()
    reaped: list[int] = []
    scheduler = make_scheduler(tmp_path, manifest, executor, reaped=reaped, resume=True)
    # Only the mid-flight attempt's PID is reaped, and the node re-runs.
    assert reaped == [77]
    assert scheduler.states["b"] == NodeState.PENDING
    assert scheduler.run() == "completed"
    assert executor.calls == ["attempt:b:1", "gates:b"]
    assert "attempt:a:1" not in executor.calls


def test_illegal_transition_raises(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    scheduler = make_scheduler(tmp_path, manifest, FakeExecutor())
    with pytest.raises(IllegalTransition):
        scheduler.transition("a", NodeState.PASSED)


def test_unsupported_kind_rejected_at_run_start(tmp_path: Path) -> None:
    manifest = make_manifest([task("a", kind="review")])
    scheduler = make_scheduler(tmp_path, manifest, FakeExecutor())
    with pytest.raises(ManifestError) as exc_info:
        scheduler.run()
    assert "not supported yet" in str(exc_info.value)


def test_phase_review_node_uses_default_worker(tmp_path: Path) -> None:
    manifest = PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[]),
        phases=[PhaseSpec(id=1, name="P", review="agentic", tasks=[task("a")])],
    )
    executor = FakeExecutor()
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "completed"
    assert scheduler.states["phase-review:1"] == NodeState.PASSED
    attempt_events = [e for e in replay(journal_path(tmp_path)) if isinstance(e, AttemptStarted)]
    assert [e.worker_registration for e in attempt_events] == ["w", "w"]
