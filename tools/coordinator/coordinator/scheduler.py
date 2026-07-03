"""Per-node state machine and the sequential run scheduler.

The scheduler consumes the DAG in deterministic topological order and
drives each node through
``pending -> running -> gate-checking -> passed | failed | waiting-human``.
Every transition is appended to the journal BEFORE it takes effect
(write-ahead), so a killed coordinator resumes from disk without
redoing completed work. Control intents (pause/resume/retry/skip/
approve/abort) arrive through the same journal, giving the scheduler
one ordered input history.

Worker execution and gates are injected as an :class:`Executor` — the
scheduler never reads ``signals.jsonl`` or task files; it sees only
:class:`AttemptResult` / :class:`GateOutcome` values and the journal.
Increment 1 executes sequentially: at most one node is in flight at a
time.
"""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal
from typing import Protocol

from coordinator.dag import Graph
from coordinator.dag import Node
from coordinator.dag import TASK_NODE
from coordinator.dag import runnable
from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import ControlIntent
from coordinator.journal import Event
from coordinator.journal import GateResult
from coordinator.journal import IntentsConsumed
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import Snapshot
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.journal import save_snapshot
from coordinator.manifest import ManifestError
from coordinator.manifest import PlanManifest
from coordinator.statedir import attempt_dir
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import new_run_id
from coordinator.statedir import write_run_id


class NodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    GATE_CHECKING = "gate-checking"
    PASSED = "passed"
    FAILED = "failed"
    WAITING_HUMAN = "waiting-human"
    SKIPPED = "skipped"


_LEGAL_TRANSITIONS: dict[NodeState, frozenset[NodeState]] = {
    NodeState.PENDING: frozenset({NodeState.RUNNING, NodeState.SKIPPED}),
    # RUNNING/GATE_CHECKING -> PENDING is the resume path discarding a
    # mid-flight attempt; -> FAILED is an abort.
    NodeState.RUNNING: frozenset({NodeState.GATE_CHECKING, NodeState.FAILED, NodeState.PENDING}),
    NodeState.GATE_CHECKING: frozenset(
        {NodeState.PASSED, NodeState.FAILED, NodeState.WAITING_HUMAN, NodeState.PENDING}
    ),
    NodeState.WAITING_HUMAN: frozenset({NodeState.PASSED, NodeState.PENDING, NodeState.SKIPPED}),
    NodeState.FAILED: frozenset({NodeState.PENDING, NodeState.SKIPPED}),
    NodeState.PASSED: frozenset(),
    NodeState.SKIPPED: frozenset(),
}


class IllegalTransition(Exception):
    pass


AttemptStatus = Literal["completed", "exited-without-stop", "waiting", "timeout", "killed"]


@dataclass(frozen=True)
class AttemptResult:
    ok: bool
    status: AttemptStatus | None = None
    error: str | None = None
    commit: str | None = None
    pid: int | None = None
    session_id: str | None = None
    transcript_path: str | None = None
    last_assistant_message: str | None = None
    signals: tuple[str, ...] = ()
    exit_code: int | None = None
    bytes_drained: int | None = None


@dataclass(frozen=True)
class GateOutcome:
    gate: str
    passed: bool
    waiting_human: bool = False
    findings: str | None = None


class Executor(Protocol):
    def run_attempt(self, node: Node, attempt_index: int, seed_context: str | None) -> AttemptResult: ...

    def run_gates(self, node: Node, result: AttemptResult) -> GateOutcome: ...


RunStatus = Literal["completed", "failed", "paused", "waiting-human", "aborted"]

Reaper = Callable[[int], None]


def manifest_hash(plan_dir: Path, manifest: PlanManifest) -> str:
    manifest_file = plan_dir / "plan.yaml"
    if manifest_file.is_file():
        return hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    return hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()


class Scheduler:
    """Drives one run of a plan's DAG. Use :meth:`load` to resume from disk."""

    def __init__(
        self,
        plan_dir: Path,
        manifest: PlanManifest,
        graph: Graph,
        journal: Journal,
        executor: Executor,
        reaper: Reaper,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.plan_dir = plan_dir
        self.manifest = manifest
        self.graph = graph
        self.journal = journal
        self.executor = executor
        self.reaper = reaper
        self.clock = clock
        self.states: dict[str, NodeState] = {node_id: NodeState.PENDING for node_id in graph.nodes}
        self.attempt_counts: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
        self._paused = False
        self._aborted = False
        self._resumed = False
        self._intents_position = 0

    @classmethod
    def load(
        cls,
        plan_dir: Path,
        manifest: PlanManifest,
        graph: Graph,
        journal: Journal,
        executor: Executor,
        reaper: Reaper,
        clock: Callable[[], float] = time.time,
    ) -> "Scheduler":
        """Resume from the journal: restore states, discard mid-flight attempts, reap PIDs."""
        scheduler = cls(plan_dir, manifest, graph, journal, executor, reaper, clock)
        scheduler._resumed = True
        snapshot = Snapshot.from_events(replay(journal.path))
        scheduler._intents_position = snapshot.intents_consumed
        scheduler._paused = snapshot.run_status == "paused"
        for node_id, node_snapshot in snapshot.nodes.items():
            if node_id not in scheduler.states:
                continue
            scheduler.states[node_id] = NodeState(node_snapshot.state)
            scheduler.attempt_counts[node_id] = len(node_snapshot.attempts)
        for node_id, state in scheduler.states.items():
            if state in (NodeState.RUNNING, NodeState.GATE_CHECKING):
                node_snapshot = snapshot.nodes.get(node_id)
                if node_snapshot is not None and node_snapshot.attempts:
                    pid = node_snapshot.attempts[-1].pid
                    if pid is not None:
                        reaper(pid)
                scheduler.transition(node_id, NodeState.PENDING, reason="resume-discard")
        return scheduler

    def transition(self, node_id: str, new_state: NodeState, reason: str | None = None) -> None:
        """The single code path for state changes: journal first, then mutate."""
        old_state = self.states[node_id]
        if new_state not in _LEGAL_TRANSITIONS[old_state]:
            raise IllegalTransition(f"node {node_id}: illegal transition {old_state.value} -> {new_state.value}")
        self.journal.append(
            TaskStateChanged(
                ts=self.clock(),
                node_id=node_id,
                old_state=old_state.value,
                new_state=new_state.value,
                reason=reason,
            )
        )
        self.states[node_id] = new_state

    def run(self) -> RunStatus:
        """Execute until a stop condition; returns the final run status."""
        self._guard_unsupported_kinds()
        ensure_state_dir(self.plan_dir)
        if not self._resumed:
            run_id = new_run_id()
            self.journal.append(
                RunStarted(
                    ts=self.clock(),
                    run_id=run_id,
                    plan_dir=str(self.plan_dir),
                    manifest_hash=manifest_hash(self.plan_dir, self.manifest),
                )
            )
            write_run_id(self.plan_dir, run_id)
        status = self._loop()
        self._save_snapshot()
        return status

    def _loop(self) -> RunStatus:
        while True:
            self._consume_intents()
            if self._aborted:
                self._fail_in_flight_nodes(reason="aborted")
                self.journal.append(RunPaused(ts=self.clock(), reason="aborted"))
                return "aborted"
            if self._paused:
                return "paused"
            ready = self._runnable_nodes()
            if not ready:
                if any(state == NodeState.WAITING_HUMAN for state in self.states.values()):
                    return "waiting-human"
                if any(state == NodeState.FAILED for state in self.states.values()):
                    return "failed"
                return "completed"
            self._execute_node(self.graph.nodes[ready[0]])
            self._save_snapshot()

    def _runnable_nodes(self) -> list[str]:
        completed = {
            node_id for node_id, state in self.states.items() if state in (NodeState.PASSED, NodeState.SKIPPED)
        }
        failed = {node_id for node_id, state in self.states.items() if state == NodeState.FAILED}
        in_flight = {
            node_id
            for node_id, state in self.states.items()
            if state in (NodeState.RUNNING, NodeState.GATE_CHECKING, NodeState.WAITING_HUMAN)
        }
        return runnable(self.graph, completed=completed, failed=failed, running=in_flight)

    def _execute_node(self, node: Node) -> None:
        self.transition(node.node_id, NodeState.RUNNING, reason="start")
        attempt_index = self.attempt_counts[node.node_id]
        self.attempt_counts[node.node_id] += 1
        self.journal.append(
            AttemptStarted(
                ts=self.clock(),
                node_id=node.node_id,
                attempt_index=attempt_index,
                worker_registration=self._worker_for(node),
                attempt_dir=str(attempt_dir(self.plan_dir, node.node_id, attempt_index)),
            )
        )
        result = self.executor.run_attempt(node, attempt_index, seed_context=None)
        if result.commit is not None:
            self.journal.append(CommitRecorded(ts=self.clock(), node_id=node.node_id, commit=result.commit))
        if not result.ok:
            self.on_attempt_failure(node, attempt_index, result)
            return
        self.transition(node.node_id, NodeState.GATE_CHECKING, reason="attempt-finished")
        outcome = self.executor.run_gates(node, result)
        self.journal.append(
            GateResult(
                ts=self.clock(),
                node_id=node.node_id,
                gate=outcome.gate,
                passed=outcome.passed,
                findings=outcome.findings,
            )
        )
        if outcome.waiting_human:
            self.transition(node.node_id, NodeState.WAITING_HUMAN, reason=f"gate {outcome.gate} requires approval")
        elif outcome.passed:
            self.transition(node.node_id, NodeState.PASSED, reason="gates-passed")
        else:
            self.on_gate_failure(node, attempt_index, outcome)

    def on_attempt_failure(self, node: Node, attempt_index: int, result: AttemptResult) -> None:
        """Seam for the retry/escalation ladder; for now an attempt failure is final."""
        self.transition(node.node_id, NodeState.FAILED, reason=result.error or "attempt-failed")

    def on_gate_failure(self, node: Node, attempt_index: int, outcome: GateOutcome) -> None:
        """Seam for the retry/escalation ladder; for now a failed gate is final."""
        self.transition(node.node_id, NodeState.FAILED, reason=outcome.findings or f"gate {outcome.gate} failed")

    def _worker_for(self, node: Node) -> str:
        if node.kind == TASK_NODE and node.task is not None and node.task.worker is not None:
            return node.task.worker
        return self.manifest.defaults.worker

    def _consume_intents(self) -> None:
        events: list[Event] = list(replay(self.journal.path))
        intents = [event for event in events[self._intents_position :] if isinstance(event, ControlIntent)]
        # Mark the batch consumed before acting on it (write-ahead): a crash
        # mid-batch drops intents rather than double-applying them.
        self._intents_position = len(events)
        if intents:
            self.journal.append(IntentsConsumed(ts=self.clock(), position=self._intents_position))
            self._intents_position += 1
        for intent in intents:
            self._apply_intent(intent)

    def _apply_intent(self, intent: ControlIntent) -> None:
        if intent.intent == "pause":
            self._paused = True
            self.journal.append(RunPaused(ts=self.clock(), reason="pause-intent"))
        elif intent.intent == "resume":
            self._paused = False
        elif intent.intent == "abort":
            self._aborted = True
        elif intent.intent == "retry":
            if intent.node_id is not None and self.states.get(intent.node_id) in (
                NodeState.FAILED,
                NodeState.WAITING_HUMAN,
            ):
                self.transition(intent.node_id, NodeState.PENDING, reason="retry-intent")
        elif intent.intent == "skip":
            if intent.node_id is not None and self.states.get(intent.node_id) in (
                NodeState.PENDING,
                NodeState.FAILED,
                NodeState.WAITING_HUMAN,
            ):
                self.transition(
                    intent.node_id,
                    NodeState.SKIPPED,
                    reason="skip-intent: dependents proceed as if this node had passed",
                )
        elif intent.intent == "approve":
            if intent.node_id is not None and self.states.get(intent.node_id) == NodeState.WAITING_HUMAN:
                self.transition(intent.node_id, NodeState.PASSED, reason="approve-intent")

    def _fail_in_flight_nodes(self, reason: str) -> None:
        for node_id, state in self.states.items():
            if state in (NodeState.RUNNING, NodeState.GATE_CHECKING):
                self.transition(node_id, NodeState.FAILED, reason=reason)

    def _guard_unsupported_kinds(self) -> None:
        problems = [
            f"task {node.task.id}: kind {node.task.kind!r} is not supported yet (arrives in increment 2)"
            for node in self.graph.nodes.values()
            if node.kind == TASK_NODE and node.task is not None and node.task.kind != "task"
        ]
        if problems:
            raise ManifestError(problems)

    def _save_snapshot(self) -> None:
        save_snapshot(Snapshot.from_events(replay(self.journal.path)), self.plan_dir)
