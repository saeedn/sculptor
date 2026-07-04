"""The real Executor: attempt prep + launcher + gates, bound for the scheduler.

Owns the execution-detail journaling the scheduler deliberately does
not do: the post-spawn ``attempt-started`` (real pid, merged into the
scheduler's write-ahead record by the snapshot), every
``signal-observed``, ``gate-started``/``gate-result``, and
``commit-recorded``.

Also enforces the dirty-tree discipline between tasks: a surprise diff
(the user edited mid-run) pauses the run with a clear report instead of
folding user edits into a task's commit.
"""

import time
from collections.abc import Callable
from pathlib import Path

from coordinator.attempt import PreparedAttempt
from coordinator.attempt import prepare_attempt
from coordinator.dag import Node
from coordinator.dag import PHASE_REVIEW_NODE
from coordinator.gates import GATE_AGENTIC
from coordinator.gates import GATE_HUMAN
from coordinator.gates import GATE_MECHANICAL
from coordinator.gates import GATE_PHASE_REVIEW
from coordinator.gates import commits_since
from coordinator.gates import head_commit
from coordinator.gates import is_tree_clean
from coordinator.gates import porcelain_status
from coordinator.gates import restore_clean_tree
from coordinator.gates import run_mechanical_gate
from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import ControlIntent
from coordinator.journal import GateResult
from coordinator.journal import GateStarted
from coordinator.journal import Journal
from coordinator.journal import RunPaused
from coordinator.journal import SignalObserved
from coordinator.journal import complete_line_count
from coordinator.journal import replay
from coordinator.launcher import launch_attempt
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec
from coordinator.ratelimit import classify_attempt
from coordinator.registrations import WorkerRegistration
from coordinator.registrations import resolve_worker
from coordinator.review import VerdictError
from coordinator.review import build_review_diff
from coordinator.review import format_findings
from coordinator.review import parse_verdict
from coordinator.review import prepare_review_attempt
from coordinator.scheduler import AttemptResult
from coordinator.scheduler import GateOutcome
from coordinator.statedir import attempt_dir
from coordinator.trust import ensure_trusted

_LIFECYCLE_FINDINGS = {
    "exited-without-stop": "worker process exited without a Stop signal",
    "waiting": "worker went waiting for user input (AskUserQuestion or idle prompt)",
    "timeout": "worker attempt timed out",
    "killed": "worker attempt was killed",
}


class RunPausedError(Exception):
    """Raised to stop the run after a run-paused event was journaled."""


class PlanExecutor:
    """Executes attempts and gates for one plan run."""

    def __init__(
        self,
        plan_dir: Path,
        manifest: PlanManifest,
        registrations: dict[str, WorkerRegistration],
        journal: Journal,
        cwd: Path,
        *,
        timeout_seconds: float = 1800.0,
        poll_interval: float = 0.5,
        kill_grace_seconds: float = 10.0,
        trust_home: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.plan_dir = plan_dir
        self.manifest = manifest
        self.registrations = registrations
        self.journal = journal
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.kill_grace_seconds = kill_grace_seconds
        self.trust_home = trust_home
        self.clock = clock
        self._prepared: dict[str, tuple[int, PreparedAttempt | None, str]] = {}
        # Abort intents appended after this run started kill the in-flight
        # worker via the launcher's poll loop (never os.kill from a UI).
        self._journal_position_at_start = complete_line_count(journal.path)

    def _abort_requested(self) -> bool:
        events = list(replay(self.journal.path))
        return any(
            isinstance(event, ControlIntent) and event.intent == "abort"
            for event in events[self._journal_position_at_start :]
        )

    def _journal_callbacks(
        self,
        node_id: str,
        attempt_index: int,
        worker_registration: str,
        attempt_directory: Path,
        base_commit: str | None = None,
    ) -> tuple[Callable[[int], None], Callable[[dict], None]]:
        """The (on_spawn, on_signal) pair that journals one attempt's lifecycle."""

        def on_spawn(pid: int) -> None:
            self.journal.append(
                AttemptStarted(
                    ts=self.clock(),
                    node_id=node_id,
                    attempt_index=attempt_index,
                    worker_registration=worker_registration,
                    pid=pid,
                    attempt_dir=str(attempt_directory),
                    base_commit=base_commit,
                )
            )

        def on_signal(event: dict) -> None:
            payload = event.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            self.journal.append(
                SignalObserved(
                    ts=self.clock(),
                    node_id=node_id,
                    attempt_index=attempt_index,
                    event=event.get("event", "unknown"),
                    session_id=payload.get("session_id"),
                    transcript_path=payload.get("transcript_path"),
                )
            )

        return on_spawn, on_signal

    def run_attempt(
        self,
        node: Node,
        attempt_index: int,
        seed_context: str | None,
        registration_override: str | None = None,
    ) -> AttemptResult:
        if node.kind == PHASE_REVIEW_NODE:
            # Phase reviews run no implementer worker; the reviewer runs
            # in run_gates. Remember the attempt index for its dir.
            self._prepared[node.node_id] = (attempt_index, None, head_commit(self.cwd))
            return AttemptResult(is_ok=True, status="completed")
        if not is_tree_clean(self.cwd):
            status = porcelain_status(self.cwd)
            self.journal.append(
                RunPaused(
                    ts=self.clock(),
                    reason="dirty-tree",
                    resume_hint="the working tree changed outside a task; commit or stash the edits, then resume",
                )
            )
            raise RunPausedError(f"working tree dirty before task {node.node_id}:\n{status}")

        assert node.task is not None
        worker_name = registration_override or resolve_worker(self.manifest, node.task, self.registrations)
        registration = self.registrations[worker_name]
        process_doc_path = (
            self.plan_dir / self.manifest.defaults.process_doc
            if self.manifest.defaults.process_doc is not None
            else None
        )
        prepared = prepare_attempt(
            plan_dir=self.plan_dir,
            node=node,
            attempt_index=attempt_index,
            task_file=self.plan_dir / node.task.file,
            process_doc_path=process_doc_path,
            seed_context=seed_context,
        )
        if registration.mode == "interactive":
            ensure_trusted(self.cwd, home=self.trust_home)
        base_commit = head_commit(self.cwd)
        self._prepared[node.node_id] = (attempt_index, prepared, base_commit)
        on_spawn, on_signal = self._journal_callbacks(
            node.node_id, attempt_index, worker_name, prepared.attempt_dir, base_commit=base_commit
        )
        return launch_attempt(
            registration,
            prepared,
            self.cwd,
            timeout_seconds=self.timeout_seconds,
            poll_interval=self.poll_interval,
            kill_grace_seconds=self.kill_grace_seconds,
            on_signal=on_signal,
            on_spawn=on_spawn,
            should_abort=self._abort_requested,
        )

    def restore_attempt(self, node: Node, attempt_index: int, attempt_directory: Path, base_commit: str) -> None:
        """Rebind gate state to a completed attempt from a previous coordinator.

        The attempt directory already holds everything a gate reads; only
        the in-memory ``_prepared`` entry needs rebuilding.
        """
        context_file = attempt_directory / "context.md"
        prompt_file = attempt_directory / "prompt.txt"
        prepared = PreparedAttempt(
            attempt_dir=attempt_directory,
            hooks_file=attempt_directory / "hooks.json",
            prompt=prompt_file.read_text() if prompt_file.is_file() else "",
            signals_path=attempt_directory / "signals.jsonl",
            process_doc=attempt_directory / "process.md",
            context_file=context_file if context_file.is_file() else None,
        )
        self._prepared[node.node_id] = (attempt_index, prepared, base_commit)

    def _phase_commits(self, node: Node) -> list[str]:
        assert node.phase is not None
        phase_task_ids = {task.id for task in node.phase.tasks}
        return [
            event.commit
            for event in replay(self.journal.path)
            if isinstance(event, CommitRecorded) and event.node_id in phase_task_ids
        ]

    def _wait_for_human(self, node: Node, attempt_directory: Path, commits: list[str]) -> GateOutcome:
        """Write the scope diff for presentation and hand the node to a human."""
        attempt_directory.mkdir(parents=True, exist_ok=True)
        diff_path = attempt_directory / "human_review.patch"
        diff_path.write_text(build_review_diff(self.cwd, commits))
        self.journal.append(GateStarted(ts=self.clock(), node_id=node.node_id, gate=GATE_HUMAN))
        return GateOutcome(
            gate=GATE_HUMAN,
            passed=False,
            waiting_human=True,
            findings=f"waiting for human approval; diff: {diff_path}",
        )

    def run_gates(self, node: Node, result: AttemptResult) -> GateOutcome:
        if node.kind == PHASE_REVIEW_NODE:
            attempt_index, _, _ = self._prepared[node.node_id]
            if node.review == "human":
                return self._wait_for_human(
                    node,
                    attempt_dir(self.plan_dir, node.node_id, attempt_index),
                    self._phase_commits(node),
                )
            return self._run_agentic(
                node,
                scope_tasks=list(node.phase.tasks) if node.phase is not None else [],
                commits=self._phase_commits(node),
                review_node_id=node.node_id,
                attempt_index=attempt_index,
                gate_kind=GATE_PHASE_REVIEW,
            )

        if result.status != "completed":
            findings = _LIFECYCLE_FINDINGS.get(str(result.status), f"worker attempt ended with {result.status}")
            outcome = GateOutcome(gate=GATE_MECHANICAL, passed=False, findings=findings)
            self._journal_gate(node, outcome)
            return outcome

        assert node.task is not None
        attempt_index, prepared, base_commit = self._prepared[node.node_id]
        assert prepared is not None
        gate_names = node.task.gates if node.task.gates is not None else [GATE_MECHANICAL]
        # The human gate runs LAST, after every automated gate passed.
        human_requested = GATE_HUMAN in gate_names
        gate_names = [name for name in gate_names if name != GATE_HUMAN]
        for gate_name in gate_names:
            if gate_name == GATE_MECHANICAL:
                self.journal.append(GateStarted(ts=self.clock(), node_id=node.node_id, gate=GATE_MECHANICAL))
                outcome = run_mechanical_gate(
                    self.cwd,
                    node,
                    prepared.attempt_dir,
                    self.manifest.defaults.verification,
                    expect_commit=not node.task.no_change,
                    base_commit=base_commit,
                )
                self.journal.append(
                    GateResult(
                        ts=self.clock(),
                        node_id=node.node_id,
                        gate=GATE_MECHANICAL,
                        passed=outcome.passed,
                        findings=outcome.findings,
                    )
                )
                if not outcome.passed:
                    return outcome
            elif gate_name == GATE_AGENTIC:
                outcome = self._run_agentic(
                    node,
                    scope_tasks=[node.task],
                    commits=commits_since(self.cwd, base_commit),
                    review_node_id=f"{node.node_id}.review",
                    attempt_index=attempt_index,
                    gate_kind=GATE_AGENTIC,
                )
                if not outcome.passed:
                    return outcome
            else:
                # Unknown gate name (manifest validation should prevent
                # this); journal the skip loudly rather than silently passing.
                self.journal.append(
                    GateResult(
                        ts=self.clock(),
                        node_id=node.node_id,
                        gate=gate_name,
                        passed=True,
                        findings=f"gate {gate_name!r} not implemented yet; skipped",
                    )
                )
        # Record the task's commits before any human wait — the work is
        # already in git either way.
        commits = commits_since(self.cwd, base_commit)
        for commit in commits:
            self.journal.append(CommitRecorded(ts=self.clock(), node_id=node.node_id, commit=commit))
        if human_requested:
            return self._wait_for_human(node, prepared.attempt_dir, commits)
        return GateOutcome(gate=GATE_MECHANICAL, passed=True)

    def _run_agentic(
        self,
        node: Node,
        scope_tasks: list[TaskSpec],
        commits: list[str],
        review_node_id: str,
        attempt_index: int,
        gate_kind: str,
    ) -> GateOutcome:
        """Launch a fresh reviewer worker and gate on its verdict (fail-closed)."""
        self.journal.append(GateStarted(ts=self.clock(), node_id=node.node_id, gate=gate_kind))
        reviewer_name = self.manifest.defaults.reviewer
        if reviewer_name is None:
            task_worker = node.task.worker if node.task is not None else None
            reviewer_name = task_worker or self.manifest.defaults.worker
        registration = self.registrations[reviewer_name]

        task_files = [self.plan_dir / task.file for task in scope_tasks]
        diff_text = build_review_diff(self.cwd, commits)
        review = prepare_review_attempt(self.plan_dir, review_node_id, attempt_index, task_files, diff_text)
        if registration.mode == "interactive":
            ensure_trusted(self.cwd, home=self.trust_home)
        head_before = head_commit(self.cwd)
        on_spawn, on_signal = self._journal_callbacks(
            review_node_id, attempt_index, reviewer_name, review.prepared.attempt_dir
        )
        result = launch_attempt(
            registration,
            review.prepared,
            self.cwd,
            timeout_seconds=self.timeout_seconds,
            poll_interval=self.poll_interval,
            kill_grace_seconds=self.kill_grace_seconds,
            on_signal=on_signal,
            on_spawn=on_spawn,
            should_abort=self._abort_requested,
        )

        if head_commit(self.cwd) != head_before:
            outcome = GateOutcome(
                gate=gate_kind, passed=False, findings="reviewer modified the repository (HEAD moved); review is void"
            )
        elif not is_tree_clean(self.cwd):
            # The tree was clean when the reviewer started, so this is the
            # reviewer's doing. Restore it — otherwise the dirt would later
            # pause the run blamed on "the user edited mid-run".
            restore_clean_tree(self.cwd)
            outcome = GateOutcome(
                gate=gate_kind,
                passed=False,
                findings="reviewer left uncommitted changes in the working tree (now restored); review is void",
            )
        elif result.status != "completed":
            rate_limit = classify_attempt(result, review.prepared.attempt_dir)
            outcome = GateOutcome(
                gate=gate_kind,
                passed=False,
                findings=f"reviewer attempt {result.status}",
                rate_limited=rate_limit is not None,
                rate_limit_hint=rate_limit.resume_hint if rate_limit is not None else None,
            )
        else:
            try:
                verdict = parse_verdict(review.verdict_path)
            except VerdictError as e:
                # Fail CLOSED: a reviewer that rambles without writing a
                # valid verdict must not pass the gate.
                outcome = GateOutcome(
                    gate=gate_kind, passed=False, findings=f"reviewer produced no valid verdict: {e}"
                )
            else:
                findings_text = f"{format_findings(verdict)}\nverdict: {review.verdict_path}"
                outcome = GateOutcome(
                    gate=gate_kind,
                    passed=not verdict.blocks(),
                    findings=findings_text,
                    findings_list=tuple(verdict.findings),
                )
        self.journal.append(
            GateResult(
                ts=self.clock(),
                node_id=node.node_id,
                gate=gate_kind,
                passed=outcome.passed,
                findings=outcome.findings,
            )
        )
        return outcome

    def _journal_gate(self, node: Node, outcome: GateOutcome) -> None:
        self.journal.append(GateStarted(ts=self.clock(), node_id=node.node_id, gate=outcome.gate))
        self.journal.append(
            GateResult(
                ts=self.clock(),
                node_id=node.node_id,
                gate=outcome.gate,
                passed=outcome.passed,
                findings=outcome.findings,
            )
        )
