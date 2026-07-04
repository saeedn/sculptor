"""Orchestration for ``coordinator run``: manifest -> DAG -> scheduler -> workers.

Deliberately free of any TUI imports — the plain-text progress path
must never pay Textual's startup cost.
"""

import os
import threading
import time
from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict

from coordinator.dag import build_graph
from coordinator.executor import PlanExecutor
from coordinator.executor import RunPausedError
from coordinator.gates import is_tree_clean
from coordinator.gates import porcelain_status
from coordinator.journal import CommitRecorded
from coordinator.journal import Event
from coordinator.journal import Journal
from coordinator.journal import ReviewHandoff
from coordinator.journal import RunPaused
from coordinator.journal import Snapshot
from coordinator.journal import load_snapshot
from coordinator.journal import replay
from coordinator.journal import save_snapshot
from coordinator.launcher import reap_recorded_pid
from coordinator.manifest import ManifestError
from coordinator.manifest import PlanManifest
from coordinator.manifest import load_manifest
from coordinator.registrations import WorkerRegistration
from coordinator.registrations import load_registrations
from coordinator.registrations import resolve_worker
from coordinator.review_spawn import handoff_review
from coordinator.scheduler import NodeState
from coordinator.scheduler import RunStatus
from coordinator.scheduler import Scheduler
from coordinator.sculpt_signals import Signaler
from coordinator.sculpt_signals import detect_signaler
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.statedir import new_run_id
from coordinator.statedir import read_run_id
from coordinator.statedir import state_dir

# Directory names never descended into when scanning for plans: VCS and
# dependency trees, plus _state (fake-worker attempt dirs can contain
# whole git repos of their own).
_PRUNED_DIR_NAMES = frozenset({".git", "node_modules", "_state", ".venv"})

# Run outcomes that should raise the tab's attention indicator.
_WAITING_STATUSES = frozenset({"waiting-human", "paused", "failed"})


class RunError(Exception):
    pass


class _SignalingJournal(Journal):
    """Journal wrapper signaling Sculptor on observed events.

    `files-changed` after EVERY task commit is what keeps Sculptor's
    diff viewer live during long runs.
    """

    def __init__(self, path: Path, signaler: Signaler) -> None:
        super().__init__(path)
        self.signaler = signaler

    def append(self, event: Event) -> None:
        super().append(event)
        if isinstance(event, CommitRecorded):
            self.signaler.files_changed()


def _validate_workers(manifest: PlanManifest, registrations: dict[str, WorkerRegistration]) -> None:
    problems: list[str] = []
    for phase in manifest.phases:
        for task in phase.tasks:
            try:
                resolve_worker(manifest, task, registrations)
            except ManifestError as e:
                problems.extend(e.problems)
            if task.escalation_worker is not None and task.escalation_worker not in registrations:
                problems.append(f"task {task.id}: unknown escalation worker registration {task.escalation_worker!r}")
    escalation = manifest.defaults.escalation_worker
    if escalation is not None and escalation not in registrations:
        problems.append(f"defaults.escalation_worker: unknown worker registration {escalation!r}")
    reviewer = manifest.defaults.reviewer
    if reviewer is not None and reviewer not in registrations:
        problems.append(f"defaults.reviewer: unknown worker registration {reviewer!r}")
    if problems:
        raise ManifestError(problems)


def execute_plan(
    plan_dir: Path,
    *,
    resume: bool = False,
    repo_root: Path | None = None,
    timeout_seconds: float = 1800.0,
    poll_interval: float = 0.5,
    kill_grace_seconds: float = 10.0,
    trust_home: Path | None = None,
    progress: Callable[[str], None] | None = None,
    clock: Callable[[], float] = time.time,
) -> RunStatus:
    """Run (or resume) a plan; returns the final run status."""
    plan_dir = plan_dir.resolve()
    cwd = (repo_root if repo_root is not None else Path.cwd()).resolve()
    manifest = load_manifest(plan_dir)
    registrations = load_registrations(cwd)
    _validate_workers(manifest, registrations)
    graph = build_graph(manifest)

    if not resume:
        # A fresh run over existing state would reuse attempt dirs — the
        # stale signals.jsonl files would satisfy the new workers' Stop
        # detection instantly — and interleave two runs in one journal.
        # Sculptor tab restarts re-issue the launch command, so this is a
        # routine event: continue the recorded run instead of refusing.
        existing_journal = journal_path(plan_dir)
        if existing_journal.is_file() and existing_journal.stat().st_size > 0:
            resume = True
            if progress is not None:
                progress(
                    f"existing run state found ({read_run_id(plan_dir) or 'unknown run id'}) — resuming. "
                    + f"Delete {state_dir(plan_dir)} to start the plan over."
                )
    if not resume and not is_tree_clean(cwd):
        raise RunError(
            f"refusing to start: the working tree at {cwd} is dirty. "
            + f"Commit or stash these changes first:\n{porcelain_status(cwd)}"
        )

    ensure_state_dir(plan_dir)
    signaler = detect_signaler()
    journal = _SignalingJournal(journal_path(plan_dir), signaler)
    run_id = read_run_id(plan_dir) if resume else new_run_id()
    executor = PlanExecutor(
        plan_dir,
        manifest,
        registrations,
        journal,
        cwd,
        timeout_seconds=timeout_seconds,
        poll_interval=poll_interval,
        kill_grace_seconds=kill_grace_seconds,
        trust_home=trust_home,
        clock=clock,
    )

    def on_transition(node_id: str, old_state: str, new_state: str, reason: str | None) -> None:
        if progress is not None:
            suffix = f" ({reason})" if reason else ""
            progress(f"{node_id}: {old_state} -> {new_state}{suffix}")

    if resume:
        scheduler = Scheduler.load(
            plan_dir, manifest, graph, journal, executor, reap_recorded_pid, clock, on_transition
        )
    else:
        scheduler = Scheduler(
            plan_dir,
            manifest,
            graph,
            journal,
            executor,
            reap_recorded_pid,
            clock,
            on_transition,
            run_id=run_id,
        )
    if run_id is not None:
        signaler.session_id(run_id)
    signaler.busy()
    try:
        status: RunStatus = scheduler.run()
    except RunPausedError as e:
        # The executor already journaled the run-paused event.
        save_snapshot(Snapshot.from_events(replay(journal.path)), plan_dir)
        signaler.waiting()
        if progress is not None:
            progress(f"run paused: {e}")
        return "paused"
    if status == "completed" and all(state == NodeState.PASSED for state in scheduler.states.values()):
        # Fully successful (nothing skipped or failed): hand the feature
        # to the Review agent. Never fatal to the completed run, and never
        # repeated — resuming an already-completed run must not spawn a
        # second Review agent.
        if not any(isinstance(event, ReviewHandoff) for event in replay(journal.path)):
            agent_id = handoff_review(plan_dir, manifest, out=progress if progress is not None else print)
            journal.append(ReviewHandoff(ts=clock(), agent_id=agent_id))
            save_snapshot(Snapshot.from_events(replay(journal.path)), plan_dir)
    if status in _WAITING_STATUSES:
        signaler.waiting()
    else:
        signaler.idle()
    if progress is not None:
        if status == "failed":
            paused_events = [event for event in replay(journal.path) if isinstance(event, RunPaused)]
            if paused_events and paused_events[-1].resume_hint:
                progress(paused_events[-1].resume_hint)
        progress(f"run finished: {status}")
    return status


def iter_plan_dirs(root: Path) -> Iterator[Path]:
    """Every directory under ``root`` containing a plan.yaml (pruned walk)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _PRUNED_DIR_NAMES]
        if "plan.yaml" in filenames:
            yield Path(dirpath)


def find_plan_by_run_id(root: Path, run_id: str) -> Path:
    """The plan directory whose recorded run id matches (the resume path)."""
    for plan_dir in iter_plan_dirs(root):
        if read_run_id(plan_dir) == run_id:
            return plan_dir
    raise RunError(f"no plan with run id {run_id!r} found under {root}")


class IncompletePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_dir: Path
    run_id: str | None
    completed: int
    total: int


def find_incomplete_plans(root: Path) -> list[IncompletePlan]:
    """Plans under ``root`` with started-but-unfinished runs (the picker's list)."""
    incomplete: list[IncompletePlan] = []
    for plan_dir in iter_plan_dirs(root):
        if not journal_path(plan_dir).is_file():
            continue
        try:
            graph = build_graph(load_manifest(plan_dir))
        except ManifestError:
            continue
        snapshot = load_snapshot(plan_dir)
        completed = sum(1 for node in snapshot.nodes.values() if node.state in ("passed", "skipped"))
        total = len(graph.nodes)
        if completed >= total and snapshot.run_status != "paused":
            continue
        incomplete.append(IncompletePlan(plan_dir=plan_dir, run_id=snapshot.run_id, completed=completed, total=total))
    return incomplete


def start_run_in_thread(
    plan_dir: Path,
    on_done: Callable[[RunStatus | None, BaseException | None], None],
    **kwargs,
) -> threading.Thread:
    """Run :func:`execute_plan` in a background thread (the TUI's run mode).

    The journal/snapshot files are the only communication channel with
    the caller; ``on_done`` (called from the thread) reports the final
    status or the exception — a crashed run must surface, never die
    silently.
    """

    def target() -> None:
        try:
            status = execute_plan(plan_dir, **kwargs)
        except BaseException as e:
            on_done(None, e)
            return
        on_done(status, None)

    thread = threading.Thread(target=target, daemon=True, name="coordinator-run")
    thread.start()
    return thread
