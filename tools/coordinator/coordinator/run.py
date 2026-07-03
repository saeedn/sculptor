"""Orchestration for ``coordinator run``: manifest -> DAG -> scheduler -> workers.

Deliberately free of any TUI imports — the plain-text progress path
must never pay Textual's startup cost (phase 6 layers the TUI on top).
"""

import time
from collections.abc import Callable
from pathlib import Path

from coordinator.dag import build_graph
from coordinator.executor import PlanExecutor
from coordinator.executor import RunPausedError
from coordinator.gates import is_tree_clean
from coordinator.gates import porcelain_status
from coordinator.journal import Journal
from coordinator.journal import Snapshot
from coordinator.journal import replay
from coordinator.journal import save_snapshot
from coordinator.launcher import reap_recorded_pid
from coordinator.manifest import ManifestError
from coordinator.manifest import PlanManifest
from coordinator.manifest import load_manifest
from coordinator.registrations import WorkerRegistration
from coordinator.registrations import load_registrations
from coordinator.registrations import resolve_worker
from coordinator.scheduler import RunStatus
from coordinator.scheduler import Scheduler
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path


class RunError(Exception):
    pass


def _validate_workers(manifest: PlanManifest, registrations: dict[str, WorkerRegistration]) -> None:
    problems: list[str] = []
    for phase in manifest.phases:
        for task in phase.tasks:
            try:
                resolve_worker(manifest, task, registrations)
            except ManifestError as e:
                problems.extend(e.problems)
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

    if not resume and not is_tree_clean(cwd):
        raise RunError(
            f"refusing to start: the working tree at {cwd} is dirty. "
            f"Commit or stash these changes first:\n{porcelain_status(cwd)}"
        )

    ensure_state_dir(plan_dir)
    journal = Journal(journal_path(plan_dir))
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

    factory = Scheduler.load if resume else Scheduler
    scheduler = factory(
        plan_dir,
        manifest,
        graph,
        journal,
        executor,
        reap_recorded_pid,
        clock,
        on_transition,
    )
    try:
        status: RunStatus = scheduler.run()
    except RunPausedError as e:
        # The executor already journaled the run-paused event.
        save_snapshot(Snapshot.from_events(replay(journal.path)), plan_dir)
        if progress is not None:
            progress(f"run paused: {e}")
        return "paused"
    if progress is not None:
        progress(f"run finished: {status}")
    return status
