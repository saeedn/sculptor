from pathlib import Path

import pytest

from coordinator.dag import Node
from coordinator.dag import build_graph
from coordinator.findings import Finding
from coordinator.journal import AttemptStarted
from coordinator.journal import ControlIntent
from coordinator.journal import ControlIntentName
from coordinator.journal import GateResult
from coordinator.journal import Journal
from coordinator.journal import PHASE_REVIEW_REOPEN_REASON
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
        self.seeds: dict[str, list[str | None]] = {}

    def run_attempt(
        self,
        node: Node,
        attempt_index: int,
        seed_context: str | None,
        registration_override: str | None = None,
    ) -> AttemptResult:
        self.calls.append(f"attempt:{node.node_id}:{attempt_index}")
        self.seeds.setdefault(node.node_id, []).append(seed_context)
        queue = self.attempts.get(node.node_id)
        if queue:
            return queue.pop(0)
        return AttemptResult(is_ok=True)

    def run_gates(self, node: Node, result: AttemptResult) -> GateOutcome:
        self.calls.append(f"gates:{node.node_id}")
        queue = self.gates.get(node.node_id)
        if queue:
            return queue.pop(0)
        return GateOutcome(gate="mechanical", passed=True)

    def restore_attempt(self, node: Node, attempt_index: int, attempt_directory: Path, base_commit: str) -> None:
        self.calls.append(f"restore:{node.node_id}:{attempt_index}:{base_commit}")


def make_manifest(tasks: list[TaskSpec]) -> PlanManifest:
    # attempts=1: these tests exercise the state machine, not the retry
    # ladder — one failure is final (the ladder has its own tests).
    return PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[], attempts=1),
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


def append_intent(
    tmp_path: Path, intent: ControlIntentName, node_id: str | None = None, amount: int | None = None
) -> None:
    ensure_state_dir(tmp_path)
    Journal(journal_path(tmp_path)).append(ControlIntent(intent=intent, node_id=node_id, amount=amount))


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
    executor = FakeExecutor(attempts={"a": [AttemptResult(is_ok=False, error="crashed")]})
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
    executor = FakeExecutor(attempts={"a": [AttemptResult(is_ok=False, error="crashed")]})
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


def test_manual_retry_carries_failure_context(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    executor = FakeExecutor(
        gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="missing frobnicator")]}
    )
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    # The real executor journals its gate verdicts; the fake does not.
    Journal(journal_path(tmp_path)).append(
        GateResult(node_id="a", gate="mechanical", passed=False, findings="missing frobnicator")
    )
    append_intent(tmp_path, "retry", node_id="a")
    executor_2 = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    seed = executor_2.seeds["a"][0]
    assert seed is not None and "missing frobnicator" in seed


def test_pause_undone_by_resume_in_same_batch_is_not_sticky(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    append_intent(tmp_path, "pause")
    append_intent(tmp_path, "resume")
    scheduler = make_scheduler(tmp_path, manifest, FakeExecutor())
    assert scheduler.run() == "completed"
    snapshot = Snapshot.from_events(replay(journal_path(tmp_path)))
    assert snapshot.run_status != "paused"


def test_stale_abort_is_dropped_on_resume(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    # The user aborted, then the coordinator died before consuming it.
    # Re-running IS the decision to continue — the stale abort must not
    # cancel the resumed run.
    append_intent(tmp_path, "abort")
    resumed = make_scheduler(tmp_path, manifest, FakeExecutor(), resume=True)
    assert resumed.run() == "completed"


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


def test_resume_reaps_mid_flight_reviewer_too(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    # Killed during "a"'s agentic gate: the implementer had finished but
    # the reviewer (journaled under "a.review") was still alive.
    journal.append(RunStarted(run_id="run-old", plan_dir=str(tmp_path), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="a", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="a", attempt_index=0, worker_registration="w", pid=11, attempt_dir="/a/0"))
    journal.append(TaskStateChanged(node_id="a", old_state="running", new_state="gate-checking"))
    journal.append(
        AttemptStarted(node_id="a.review", attempt_index=0, worker_registration="w", pid=99, attempt_dir="/a.review/0")
    )
    reaped: list[int] = []
    scheduler = make_scheduler(tmp_path, manifest, FakeExecutor(), reaped=reaped, resume=True)
    assert sorted(reaped) == [11, 99]
    assert scheduler.states["a"] == NodeState.PENDING


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


def test_resume_discarded_attempt_does_not_burn_budget(tmp_path: Path) -> None:
    manifest = PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[], attempts=2),
        phases=[PhaseSpec(id=1, name="P", review="none", tasks=[task("a")])],
    )
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    journal.append(RunStarted(run_id="run-old", plan_dir=str(tmp_path), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="a", old_state="pending", new_state="running"))
    journal.append(AttemptStarted(node_id="a", attempt_index=0, worker_registration="w", attempt_dir="/a/0"))
    # The discarded mid-flight attempt keeps its dir index but not its
    # budget slot: the node still gets 2 real attempts (indexes 1 and 2).
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="real failure")]})
    resumed = make_scheduler(tmp_path, manifest, executor, resume=True)
    assert resumed.run() == "completed"
    assert executor.calls == ["attempt:a:1", "gates:a", "attempt:a:2", "gates:a"]


def test_phase_review_reopen_restores_the_attempt_budget(tmp_path: Path) -> None:
    # "a" spends its whole ladder passing, then a phase review sends it
    # back. The reopened task must get a full budget for the new work,
    # not fail the run on its first stumble.
    manifest = PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[], attempts=2),
        phases=[PhaseSpec(id=1, name="P", review="agentic", tasks=[task("a")])],
    )
    fail = GateOutcome(gate="mechanical", passed=False, findings="not yet")
    review_fail = GateOutcome(
        gate="phase-review",
        passed=False,
        findings="[blocker] (task a) missing case",
        findings_list=(Finding(task_id="a", severity="blocker", summary="missing case"),),
    )
    ok = GateOutcome(gate="mechanical", passed=True)
    executor = FakeExecutor(gates={"a": [fail, ok, fail, ok], "phase-review:1": [review_fail]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "completed"
    assert executor.calls == [
        "attempt:a:0",
        "gates:a",
        "attempt:a:1",
        "gates:a",
        "attempt:phase-review:1:0",
        "gates:phase-review:1",
        # Budget restored: a failure here would be terminal without it.
        "attempt:a:2",
        "gates:a",
        "attempt:a:3",
        "gates:a",
        "attempt:phase-review:1:1",
        "gates:phase-review:1",
    ]


def test_restored_budget_survives_a_resume(tmp_path: Path) -> None:
    # The reset is derived from the journal, so a coordinator restarted
    # between the reopen and the retry sees the same fresh ladder.
    manifest = PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[], attempts=2),
        phases=[PhaseSpec(id=1, name="P", review="none", tasks=[task("a")])],
    )
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    journal.append(RunStarted(run_id="run-old", plan_dir=str(tmp_path), manifest_hash="h"))
    for index in range(2):
        journal.append(AttemptStarted(node_id="a", attempt_index=index, worker_registration="w", attempt_dir="/a"))
    journal.append(
        TaskStateChanged(node_id="a", old_state="passed", new_state="pending", reason=PHASE_REVIEW_REOPEN_REASON)
    )
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="boom")]})
    resumed = make_scheduler(tmp_path, manifest, executor, resume=True)
    assert resumed.run() == "completed"
    assert executor.calls == ["attempt:a:2", "gates:a", "attempt:a:3", "gates:a"]


def review_manifest(rounds: int | None, attempts: int = 1) -> PlanManifest:
    return PlanManifest(
        version=1,
        defaults=ManifestDefaults(worker="w", verification=[], attempts=attempts),
        phases=[PhaseSpec(id=1, name="P", review="agentic", review_rounds=rounds, tasks=[task("a")])],
    )


def review_failure(task_id: str | None = "a") -> GateOutcome:
    return GateOutcome(
        gate="phase-review",
        passed=False,
        findings="[blocker] missing case",
        findings_list=(Finding(task_id=task_id, severity="blocker", summary="missing case"),),
    )


def test_phase_review_reopens_once_per_round_in_its_budget(tmp_path: Path) -> None:
    # Two rounds of findings go back to the build agents; only the third
    # failing review is the human's problem.
    manifest = review_manifest(rounds=2)
    executor = FakeExecutor(gates={"phase-review:1": [review_failure(), review_failure(), review_failure()]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    assert scheduler.states["phase-review:1"] == NodeState.WAITING_HUMAN
    reopens = [
        e
        for e in replay(journal_path(tmp_path))
        if isinstance(e, TaskStateChanged) and e.node_id == "a" and e.reason == PHASE_REVIEW_REOPEN_REASON
    ]
    assert len(reopens) == 2
    assert executor.calls.count("attempt:a:0") == 1
    assert [call for call in executor.calls if call.startswith("attempt:a")] == [
        "attempt:a:0",
        "attempt:a:1",
        "attempt:a:2",
    ]


def test_phase_review_with_zero_rounds_escalates_immediately(tmp_path: Path) -> None:
    manifest = review_manifest(rounds=0)
    executor = FakeExecutor(gates={"phase-review:1": [review_failure()]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    assert scheduler.states["a"] == NodeState.PASSED
    assert not [
        e
        for e in replay(journal_path(tmp_path))
        if isinstance(e, TaskStateChanged) and e.reason == PHASE_REVIEW_REOPEN_REASON
    ]


def test_unattributed_findings_escalate_without_spending_a_round(tmp_path: Path) -> None:
    # Nothing to hand back, so re-reviewing the same tree is pure spin:
    # the run stops at once and keeps its rounds for real fixes.
    manifest = review_manifest(rounds=2)
    executor = FakeExecutor(gates={"phase-review:1": [review_failure(task_id=None)]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    assert executor.calls == ["attempt:a:0", "gates:a", "attempt:phase-review:1:0", "gates:phase-review:1"]
    assert not [
        e
        for e in replay(journal_path(tmp_path))
        if isinstance(e, TaskStateChanged) and e.reason == PHASE_REVIEW_REOPEN_REASON
    ]


def test_every_finding_against_a_task_reaches_its_retry_context(tmp_path: Path) -> None:
    manifest = review_manifest(rounds=1)
    two_findings = GateOutcome(
        gate="phase-review",
        passed=False,
        findings="two blockers",
        findings_list=(
            Finding(task_id="a", severity="blocker", summary="missing case"),
            Finding(task_id="a", severity="blocker", summary="leaks a handle"),
        ),
    )
    executor = FakeExecutor(gates={"phase-review:1": [two_findings]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "completed"
    seed = executor.seeds["a"][1]
    assert seed is not None
    assert "missing case" in seed and "leaks a handle" in seed


class ExtendingExecutor(FakeExecutor):
    """Appends an extend intent the moment the phase review fails.

    Models the human granting another round while the coordinator is
    still alive, so the scheduler still holds the failing verdict.
    """

    def __init__(self, plan_dir: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.plan_dir = plan_dir

    def run_gates(self, node: Node, result: AttemptResult) -> GateOutcome:
        outcome = super().run_gates(node, result)
        if node.node_id == "phase-review:1" and not outcome.passed:
            append_intent(self.plan_dir, "extend", node_id="phase-review:1")
        return outcome


def test_extend_intent_reopens_a_review_that_ran_out_of_rounds(tmp_path: Path) -> None:
    manifest = review_manifest(rounds=0)
    executor = ExtendingExecutor(tmp_path, gates={"phase-review:1": [review_failure()]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "completed"
    # The granted round sends the findings the scheduler already has back
    # to the task — no second reviewer run to re-derive the same verdict.
    assert executor.calls == [
        "attempt:a:0",
        "gates:a",
        "attempt:phase-review:1:0",
        "gates:phase-review:1",
        "attempt:a:1",
        "gates:a",
        "attempt:phase-review:1:1",
        "gates:phase-review:1",
    ]
    seeds = executor.seeds["a"]
    assert seeds[1] is not None and "missing case" in seeds[1]


def test_extend_intent_on_a_resumed_review_costs_no_round(tmp_path: Path) -> None:
    # A resumed coordinator has lost the verdict, so it re-reviews to get
    # the findings back. That repeat must not spend the granted round.
    manifest = review_manifest(rounds=0)
    executor = FakeExecutor(gates={"phase-review:1": [review_failure()]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "waiting-human"
    # The real executor journals its verdicts; the fake does not.
    Journal(journal_path(tmp_path)).append(
        GateResult(node_id="phase-review:1", gate="phase-review", passed=False, findings="missing case")
    )
    append_intent(tmp_path, "extend", node_id="phase-review:1")
    executor_2 = FakeExecutor(gates={"phase-review:1": [review_failure()]})
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert executor_2.calls == [
        # The re-review that recovers the findings...
        "attempt:phase-review:1:1",
        "gates:phase-review:1",
        # ...then the round the human actually paid for.
        "attempt:a:1",
        "gates:a",
        "attempt:phase-review:1:2",
        "gates:phase-review:1",
    ]


def test_extend_intent_widens_a_failed_task_ladder(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])  # attempts=1: one failure is terminal
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="boom")]})
    scheduler = make_scheduler(tmp_path, manifest, executor)
    assert scheduler.run() == "failed"
    append_intent(tmp_path, "extend", node_id="a", amount=3)
    executor_2 = FakeExecutor(
        gates={
            "a": [
                GateOutcome(gate="mechanical", passed=False, findings="boom"),
                GateOutcome(gate="mechanical", passed=False, findings="boom"),
            ]
        }
    )
    resumed = make_scheduler(tmp_path, manifest, executor_2, resume=True)
    assert resumed.run() == "completed"
    assert executor_2.calls == ["attempt:a:1", "gates:a", "attempt:a:2", "gates:a", "attempt:a:3", "gates:a"]


def test_extended_budget_survives_a_later_resume(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    executor = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="boom")]})
    assert make_scheduler(tmp_path, manifest, executor).run() == "failed"
    # The extend is consumed by a run that pauses before using any of it.
    append_intent(tmp_path, "extend", node_id="a", amount=2)
    append_intent(tmp_path, "pause")
    assert make_scheduler(tmp_path, manifest, FakeExecutor(), resume=True).run() == "paused"
    append_intent(tmp_path, "resume")
    executor_3 = FakeExecutor(gates={"a": [GateOutcome(gate="mechanical", passed=False, findings="boom")]})
    resumed = make_scheduler(tmp_path, manifest, executor_3, resume=True)
    assert resumed.run() == "completed"
    assert executor_3.calls == ["attempt:a:1", "gates:a", "attempt:a:2", "gates:a"]


def write_stop_signals(attempt_directory: Path) -> None:
    attempt_directory.mkdir(parents=True, exist_ok=True)
    with open(attempt_directory / "signals.jsonl", "w") as f:
        f.write('{"event": "SessionStart", "ts": 1.0, "payload": {"session_id": "dead-sess"}}\n')
        f.write('{"event": "Stop", "ts": 2.0, "payload": {"session_id": "dead-sess"}}\n')


def test_resume_gates_completed_attempt_without_rerunning(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    ensure_state_dir(tmp_path)
    attempt_directory = tmp_path / "_state" / "attempts" / "a" / "0"
    write_stop_signals(attempt_directory)
    journal = Journal(journal_path(tmp_path))
    journal.append(RunStarted(run_id="run-dead", plan_dir=str(tmp_path), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="a", old_state="pending", new_state="running"))
    journal.append(
        AttemptStarted(
            node_id="a",
            attempt_index=0,
            worker_registration="w",
            attempt_dir=str(attempt_directory),
            base_commit="basecafe",
        )
    )
    executor = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor, resume=True)
    assert resumed.run() == "completed"
    # Restored and gated; no fresh worker attempt.
    assert executor.calls == ["restore:a:0:basecafe", "gates:a"]


def test_resume_discards_stopped_attempt_without_base_commit(tmp_path: Path) -> None:
    manifest = make_manifest([task("a")])
    ensure_state_dir(tmp_path)
    attempt_directory = tmp_path / "_state" / "attempts" / "a" / "0"
    write_stop_signals(attempt_directory)
    journal = Journal(journal_path(tmp_path))
    journal.append(RunStarted(run_id="run-old", plan_dir=str(tmp_path), manifest_hash="h"))
    journal.append(TaskStateChanged(node_id="a", old_state="pending", new_state="running"))
    # An old journal without base_commit cannot be gated on resume.
    journal.append(
        AttemptStarted(node_id="a", attempt_index=0, worker_registration="w", attempt_dir=str(attempt_directory))
    )
    executor = FakeExecutor()
    resumed = make_scheduler(tmp_path, manifest, executor, resume=True)
    assert resumed.run() == "completed"
    assert executor.calls == ["attempt:a:1", "gates:a"]
