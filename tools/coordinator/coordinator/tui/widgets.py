"""Rendering helpers for the coordinator dashboard.

Everything here derives display values from the :class:`Snapshot` — the
TUI is a view over the on-disk state, never a private model of truth.
"""

import time

from rich.text import Text

from coordinator.dag import Node
from coordinator.dag import TASK_NODE
from coordinator.journal import NodeSnapshot
from coordinator.journal import Snapshot
from coordinator.ladder import attempt_plan
from coordinator.manifest import PlanManifest

_STATE_STYLES = {
    "pending": "dim",
    "running": "bold yellow",
    "gate-checking": "yellow",
    "passed": "green",
    "failed": "bold red",
    "waiting-human": "bold magenta",
    "skipped": "dim cyan",
}

TABLE_COLUMNS = ("state", "phase", "name", "attempts", "worker", "activity")


def node_phase_label(node: Node) -> str:
    if node.phase is None:
        return "-"
    return str(node.phase.name)


def node_name_label(node: Node) -> str:
    if node.kind != TASK_NODE or node.task is None:
        return "phase review"
    stem = node.task.file
    return stem[:-3] if stem.endswith(".md") else stem


def state_cell(state: str) -> Text:
    return Text(state, style=_STATE_STYLES.get(state, ""))


def attempts_cell(node: Node, node_snapshot: NodeSnapshot | None, manifest: PlanManifest) -> str:
    budget = attempt_plan(node.task, manifest.defaults)
    total = budget.base_count + (1 if budget.escalation_worker is not None else 0)
    used = len(node_snapshot.attempts) if node_snapshot is not None else 0
    return f"{used}/{total}"


def worker_cell(node_snapshot: NodeSnapshot | None) -> str:
    if node_snapshot is None or not node_snapshot.attempts:
        return "-"
    return node_snapshot.attempts[-1].worker_registration


def activity_cell(node_snapshot: NodeSnapshot | None, now: float | None = None) -> str:
    if node_snapshot is None or not node_snapshot.attempts:
        return "-"
    attempt = node_snapshot.attempts[-1]
    if not attempt.signals:
        return "(no signals yet)"
    label = attempt.signals[-1]
    if attempt.last_signal_ts is None:
        return label
    age = max(0, int((now if now is not None else time.time()) - attempt.last_signal_ts))
    return f"{label} ({age}s ago)"


def progress_summary(snapshot: Snapshot, total_nodes: int) -> str:
    passed = sum(1 for node in snapshot.nodes.values() if node.state in ("passed", "skipped"))
    return f"{passed}/{total_nodes} passed"


def run_state_label(snapshot: Snapshot, total_nodes: int) -> str:
    states = {node.state for node in snapshot.nodes.values()}
    if snapshot.run_status == "paused":
        return f"paused ({snapshot.pause_reason or 'unknown'})"
    if "waiting-human" in states:
        return "waiting for human"
    terminal = sum(1 for node in snapshot.nodes.values() if node.state in ("passed", "skipped"))
    if total_nodes and terminal == total_nodes:
        return "complete"
    if "failed" in states:
        return "failing"
    return "running"
