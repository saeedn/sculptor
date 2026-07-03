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
from coordinator.dag import PHASE_REVIEW_NODE
from coordinator.dag import TASK_NODE
from coordinator.dag import runnable
from coordinator.journal import AttemptStarted
from coordinator.journal import ControlIntent
from coordinator.journal import Event
from coordinator.journal import GateResult
from coordinator.journal import IntentsConsumed
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import Snapshot
from coordinator.journal import TaskStateChanged
from coordinator.journal import replay
from coordinator.journal import save_snapshot
from coordinator.ladder import AttemptRecordLite
from coordinator.ladder import Exhausted
from coordinator.ladder import FailureRecord
from coordinator.ladder import attempt_plan
from coordinator.ladder import format_seed_context
from coordinator.ladder import next_attempt
from coordinator.manifest import ManifestError
from coordinator.manifest import PlanManifest
from coordinator.ratelimit import classify_attempt
from coordinator.statedir import attempt_dir
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import new_run_id
from coordinator.statedir import state_dir
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
    # PASSED -> PENDING is the phase-review reopen path.
    NodeState.PASSED: frozenset({NodeState.PENDING}),
    NodeState.SKIPPED: frozenset(),
}

# Pause reasons that survive a coordinator restart: these need an
# explicit resume intent. Everything else (rate-limit, dirty-tree,
# failed) is cleared by re-invoking the coordinator — re-running IS the
# human's decision to continue.
_STICKY_PAUSE_REASONS = frozenset({"pause-intent", "aborted"})


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
    # Parsed reviewer findings (review.Finding objects) when the agentic
    # gate ran; the retry ladder formats these into the retry context.
    findings_list: tuple[object, ...] = ()


class Executor(Protocol):
    def run_attempt(
        self,
        node: Node,
        attempt_index: int,
        seed_context: str | None,
        registration_override: str | None = None,
    ) -> AttemptResult: ...

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
        on_transition: Callable[[str, str, str, str | None], None] | None = None,
    ) -> None:
        self.plan_dir = plan_dir
        self.manifest = manifest
        self.graph = graph
        self.journal = journal
        self.executor = executor
        self.reaper = reaper
        self.clock = clock
        self.on_transition = on_transition
        self.states: dict[str, NodeState] = {node_id: NodeState.PENDING for node_id in graph.nodes}
        self.attempt_counts: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
        self._paused = False
        self._aborted = False
        self._resumed = False
        self._intents_position = 0
        self._attempt_records: dict[str, list[AttemptRecordLite]] = {node_id: [] for node_id in graph.nodes}
        self._failures: dict[str, list[FailureRecord]] = {node_id: [] for node_id in graph.nodes}
        self._seed_context: dict[str, str] = {}
        self._registration_override: dict[str, str] = {}
        self._last_results: dict[str, AttemptResult] = {}
        self._phase_review_failures: dict[str, int] = {node_id: 0 for node_id in graph.nodes}

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
        on_transition: Callable[[str, str, str, str | None], None] | None = None,
    ) -> "Scheduler":
        """Resume from the journal: restore states, discard mid-flight attempts, reap PIDs."""
        scheduler = cls(plan_dir, manifest, graph, journal, executor, reaper, clock, on_transition)
        scheduler._resumed = True
        snapshot = Snapshot.from_events(replay(journal.path))
        scheduler._intents_position = snapshot.intents_consumed
        scheduler._paused = snapshot.run_status == "paused" and snapshot.pause_reason in _STICKY_PAUSE_REASONS
        for node_id, node_snapshot in snapshot.nodes.items():
            if node_id not in scheduler.states:
                continue
            scheduler.states[node_id] = NodeState(node_snapshot.state)
            scheduler.attempt_counts[node_id] = len(node_snapshot.attempts)
            scheduler._attempt_records[node_id] = [
                AttemptRecordLite(
                    attempt_index=attempt.attempt_index,
                    registration=attempt.worker_registration,
                    rate_limited="rate-limited" in attempt.signals,
                )
                for attempt in node_snapshot.attempts
            ]
            # Rebuild failure history from journaled gate findings so a
            # resumed retry still gets seeded context (attempt indexes
            # are approximate — the full logs live in the attempt dirs).
            scheduler._failures[node_id] = [
                FailureRecord(
                    attempt_index=index,
                    registration=None,
                    status=None,
                    findings=gate.findings,
                    last_assistant_message=None,
                )
                for index, gate in enumerate(node_snapshot.gates)
                if gate.passed is False
            ]
            scheduler._phase_review_failures[node_id] = sum(
                1 for gate in node_snapshot.gates if gate.gate == "phase-review" and gate.passed is False
            )
            if scheduler._failures[node_id] and scheduler.states[node_id] == NodeState.PENDING:
                scheduler._seed_context[node_id] = format_seed_context(scheduler._failures[node_id])
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
        if self.on_transition is not None:
            self.on_transition(node_id, old_state.value, new_state.value, reason)

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
                    report_path = self._write_failure_report()
                    self.journal.append(
                        RunPaused(ts=self.clock(), reason="failed", resume_hint=f"failure report: {report_path}")
                    )
                    print(f"run failed — see the failure report: {report_path}")
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
        seed_context = self._seed_context.pop(node.node_id, None)
        registration_override = self._registration_override.pop(node.node_id, None)
        worker_name = registration_override or self._worker_for(node)
        self._attempt_records[node.node_id].append(
            AttemptRecordLite(attempt_index=attempt_index, registration=worker_name)
        )
        self.journal.append(
            AttemptStarted(
                ts=self.clock(),
                node_id=node.node_id,
                attempt_index=attempt_index,
                worker_registration=worker_name,
                attempt_dir=str(attempt_dir(self.plan_dir, node.node_id, attempt_index)),
            )
        )
        result = self.executor.run_attempt(
            node, attempt_index, seed_context=seed_context, registration_override=registration_override
        )
        self._last_results[node.node_id] = result
        if not result.ok:
            self.on_attempt_failure(node, attempt_index, result)
            return
        self.transition(node.node_id, NodeState.GATE_CHECKING, reason="attempt-finished")
        # Gate/commit journaling (gate-started/gate-result/commit-recorded)
        # is the executor's job — it knows the per-gate detail.
        outcome = self.executor.run_gates(node, result)
        if outcome.waiting_human:
            self.transition(node.node_id, NodeState.WAITING_HUMAN, reason=f"gate {outcome.gate} requires approval")
        elif outcome.passed:
            self.transition(node.node_id, NodeState.PASSED, reason="gates-passed")
        else:
            self.on_gate_failure(node, attempt_index, outcome)

    def _pause_for_rate_limit(self, node: Node, attempt_index: int, resume_hint: str | None) -> None:
        """A rate-limited attempt burns no budget: mark it, revert, pause."""
        records = self._attempt_records[node.node_id]
        if records and records[-1].attempt_index == attempt_index:
            records[-1].rate_limited = True
        self.journal.append(
            SignalObserved(ts=self.clock(), node_id=node.node_id, attempt_index=attempt_index, event="rate-limited")
        )
        self.transition(node.node_id, NodeState.PENDING, reason="rate-limited")
        self.journal.append(
            RunPaused(
                ts=self.clock(),
                reason="rate-limit",
                resume_hint=resume_hint or "rate limited; re-run the coordinator when the limit resets",
            )
        )
        self._paused = True

    def _schedule_next_rung(self, node: Node, reason_findings: str | None) -> None:
        """Ladder arithmetic after a non-rate-limited failure."""
        budget = attempt_plan(node.task, self.manifest.defaults)
        decision = next_attempt(self._attempt_records[node.node_id], budget)
        if isinstance(decision, Exhausted):
            self.transition(node.node_id, NodeState.FAILED, reason=reason_findings or "attempts exhausted")
            return
        self._seed_context[node.node_id] = format_seed_context(self._failures[node.node_id])
        if decision.registration_override is not None:
            self._registration_override[node.node_id] = decision.registration_override
        reason = "escalate" if decision.escalated else "retry"
        self.transition(node.node_id, NodeState.PENDING, reason=reason)

    def on_attempt_failure(self, node: Node, attempt_index: int, result: AttemptResult) -> None:
        if result.status == "killed":
            # An aborted attempt never retries; the abort intent itself is
            # processed at the top of the next loop iteration.
            self.transition(node.node_id, NodeState.FAILED, reason="aborted")
            return
        rate_limit = classify_attempt(result, attempt_dir(self.plan_dir, node.node_id, attempt_index))
        if rate_limit is not None:
            self._pause_for_rate_limit(node, attempt_index, rate_limit.resume_hint)
            return
        self._failures[node.node_id].append(
            FailureRecord(
                attempt_index=attempt_index,
                registration=self._attempt_records[node.node_id][-1].registration,
                status=result.status,
                findings=result.error,
                last_assistant_message=result.last_assistant_message,
            )
        )
        self._schedule_next_rung(node, result.error or "attempt-failed")

    def on_gate_failure(self, node: Node, attempt_index: int, outcome: GateOutcome) -> None:
        result = self._last_results.get(node.node_id)
        if result is not None:
            rate_limit = classify_attempt(result, attempt_dir(self.plan_dir, node.node_id, attempt_index))
            if rate_limit is not None:
                self._pause_for_rate_limit(node, attempt_index, rate_limit.resume_hint)
                return
        if node.kind == PHASE_REVIEW_NODE:
            self._on_phase_review_failure(node, outcome)
            return
        self._failures[node.node_id].append(
            FailureRecord(
                attempt_index=attempt_index,
                registration=self._attempt_records[node.node_id][-1].registration,
                status=result.status if result is not None else None,
                findings=outcome.findings,
                last_assistant_message=result.last_assistant_message if result is not None else None,
            )
        )
        self._schedule_next_rung(node, outcome.findings or f"gate {outcome.gate} failed")

    def _on_phase_review_failure(self, node: Node, outcome: GateOutcome) -> None:
        """Re-open the offending tasks; a second review failure needs a human."""
        self._phase_review_failures[node.node_id] += 1
        if self._phase_review_failures[node.node_id] >= 2:
            self.transition(
                node.node_id, NodeState.WAITING_HUMAN, reason="phase review failed twice; needs a human decision"
            )
            return
        reopened = False
        for finding in outcome.findings_list:
            task_id = getattr(finding, "task_id", None)
            if task_id is None or self.states.get(task_id) != NodeState.PASSED:
                continue
            self._failures[task_id].append(
                FailureRecord(
                    attempt_index=self.attempt_counts[task_id] - 1,
                    registration=None,
                    status=None,
                    findings=f"phase review finding: {getattr(finding, 'summary', '')}: "
                    f"{getattr(finding, 'detail', '')}",
                    last_assistant_message=None,
                )
            )
            self._seed_context[task_id] = format_seed_context(self._failures[task_id])
            self.transition(task_id, NodeState.PENDING, reason="phase-review-reopen")
            reopened = True
        # The review node re-runs after the reopened tasks pass again (or
        # immediately, when no finding named a task).
        reason = "phase-review-retry" if reopened else "phase-review-retry (no task attributed)"
        self.transition(node.node_id, NodeState.PENDING, reason=reason)

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
                self.journal.append(
                    GateResult(
                        ts=self.clock(),
                        node_id=intent.node_id,
                        gate="human",
                        passed=True,
                        findings="approved by user",
                    )
                )
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

    def _write_failure_report(self) -> Path:
        """The consolidated failure report; lives in _state/ (never committed)."""
        snapshot = Snapshot.from_events(replay(self.journal.path))
        lines = ["# Coordinator failure report", ""]
        for node_id, state in self.states.items():
            if state != NodeState.FAILED:
                continue
            node = self.graph.nodes[node_id]
            source = node.task.file if node.task is not None else "(phase review)"
            lines.append(f"## Node {node_id} — {source}")
            lines.append("")
            node_snapshot = snapshot.nodes.get(node_id)
            if node_snapshot is not None:
                lines.append("| attempt | worker | session id | attempt dir |")
                lines.append("|---|---|---|---|")
                for attempt in node_snapshot.attempts:
                    lines.append(
                        f"| {attempt.attempt_index} | {attempt.worker_registration} "
                        f"| {attempt.session_id or '-'} | {attempt.attempt_dir} |"
                    )
                lines.append("")
                failed_gates = [gate for gate in node_snapshot.gates if gate.passed is False]
                if failed_gates:
                    lines.append("Gate findings:")
                    for gate in failed_gates:
                        lines.append(f"- [{gate.gate}] {gate.findings or '(no findings)'}")
                    lines.append("")
                session_ids = [a.session_id for a in node_snapshot.attempts if a.session_id]
                if session_ids:
                    lines.append(f"Diagnose an attempt with: `claude --resume {session_ids[-1]}`")
                    lines.append("")
        report_path = state_dir(self.plan_dir) / "failure_report.md"
        report_path.write_text("\n".join(lines) + "\n")
        return report_path

    def _save_snapshot(self) -> None:
        save_snapshot(Snapshot.from_events(replay(self.journal.path)), self.plan_dir)
