"""The coordinator's Textual dashboard.

A live view over the on-disk execution state (REQ-UX-4): the scheduler
runs in a background thread with the journal as the only communication
channel, and the app re-reads the snapshot on a timer — the dashboard
shows exactly what a resumed coordinator would see. Works in a plain
PTY: keyboard only, no mouse required.
"""

import threading
import time
from pathlib import Path

from textual.app import App
from textual.app import ComposeResult
from textual.widgets import DataTable
from textual.widgets import Footer
from textual.widgets import Static

from coordinator.dag import Graph
from coordinator.dag import build_graph
from coordinator.dag import topological_order
from coordinator.journal import Snapshot
from coordinator.journal import load_snapshot
from coordinator.manifest import PlanManifest
from coordinator.manifest import load_manifest
from coordinator.run import RunStatus
from coordinator.run import start_run_in_thread
from coordinator.statedir import journal_path
from coordinator.tui.widgets import TABLE_COLUMNS
from coordinator.tui.widgets import activity_cell
from coordinator.tui.widgets import attempts_cell
from coordinator.tui.widgets import node_name_label
from coordinator.tui.widgets import node_phase_label
from coordinator.tui.widgets import progress_summary
from coordinator.tui.widgets import run_state_label
from coordinator.tui.widgets import state_cell
from coordinator.tui.widgets import worker_cell

_REFRESH_INTERVAL_SECONDS = 0.5


class StateReader:
    """Re-reads the snapshot, no-oping when the journal hasn't grown."""

    def __init__(self, plan_dir: Path) -> None:
        self.plan_dir = plan_dir
        self._last_size = -1

    def read(self) -> Snapshot | None:
        path = journal_path(self.plan_dir)
        size = path.stat().st_size if path.is_file() else 0
        if size == self._last_size:
            return None
        self._last_size = size
        try:
            return load_snapshot(self.plan_dir)
        except Exception:
            # A mid-write race; retry once before giving up on this tick.
            time.sleep(0.05)
            try:
                return load_snapshot(self.plan_dir)
            except Exception:
                self._last_size = -1
                return None


class CoordinatorApp(App):
    """Full-tab dashboard for one plan run."""

    TITLE = "coordinator"
    CSS = """
    #status {
        dock: top;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    DataTable {
        height: 1fr;
    }
    """
    BINDINGS = [("q", "quit_if_idle", "Quit (when idle)")]

    def __init__(
        self,
        plan_dir: Path,
        resume: bool = False,
        start_run: bool = True,
        **execute_kwargs,
    ) -> None:
        super().__init__()
        self.plan_dir = plan_dir.resolve()
        self.resume = resume
        self.start_run = start_run
        self.execute_kwargs = execute_kwargs
        self.manifest: PlanManifest = load_manifest(self.plan_dir)
        self.graph: Graph = build_graph(self.manifest)
        self.node_order: list[str] = topological_order(self.graph)
        self.reader = StateReader(self.plan_dir)
        self.final_status: RunStatus | None = None
        self.run_error: BaseException | None = None
        self._run_thread: threading.Thread | None = None
        self._last_snapshot: Snapshot | None = None
        self.status_text = ""

    def compose(self) -> ComposeResult:
        yield Static(id="status")
        yield DataTable(id="tasks")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_column("node", key="node")
        for column in TABLE_COLUMNS:
            table.add_column(column, key=column)
        for node_id in self.node_order:
            node = self.graph.nodes[node_id]
            table.add_row(
                node_id,
                state_cell("pending"),
                node_phase_label(node),
                node_name_label(node),
                attempts_cell(node, None, self.manifest),
                worker_cell(None),
                activity_cell(None),
                key=node_id,
            )
        if self.start_run:
            self._run_thread = start_run_in_thread(
                self.plan_dir, self._on_run_done, resume=self.resume, **self.execute_kwargs
            )
        self.set_interval(_REFRESH_INTERVAL_SECONDS, self.refresh_state)
        self.refresh_state()

    def _on_run_done(self, status: RunStatus | None, error: BaseException | None) -> None:
        # Called from the run thread; plain attribute writes read by the
        # UI thread's next timer tick.
        self.final_status = status
        self.run_error = error

    def refresh_state(self) -> None:
        snapshot = self.reader.read()
        if snapshot is not None:
            self._last_snapshot = snapshot
            self._update_table(snapshot)
        self._update_status_bar()

    def _update_table(self, snapshot: Snapshot) -> None:
        table = self.query_one(DataTable)
        for node_id in self.node_order:
            node = self.graph.nodes[node_id]
            node_snapshot = snapshot.nodes.get(node_id)
            state = node_snapshot.state if node_snapshot is not None else "pending"
            table.update_cell(node_id, "state", state_cell(state), update_width=True)
            table.update_cell(node_id, "attempts", attempts_cell(node, node_snapshot, self.manifest))
            table.update_cell(node_id, "worker", worker_cell(node_snapshot), update_width=True)
            table.update_cell(node_id, "activity", activity_cell(node_snapshot), update_width=True)

    def _update_status_bar(self) -> None:
        status = self.query_one("#status", Static)
        snapshot = self._last_snapshot
        parts = [f"plan: {self.plan_dir}"]
        if snapshot is not None:
            parts.append(f"run: {snapshot.run_id or '-'}")
            if self.final_status is not None:
                parts.append(f"state: {self.final_status}")
            else:
                parts.append(f"state: {run_state_label(snapshot, len(self.node_order))}")
            parts.append(progress_summary(snapshot, len(self.node_order)))
        elif self.final_status is not None:
            parts.append(f"state: {self.final_status}")
        if self.run_error is not None:
            parts.append(f"RUN CRASHED: {self.run_error}")
        self.status_text = "  •  ".join(parts)
        status.update(self.status_text)

    def action_quit_if_idle(self) -> None:
        if self._run_thread is not None and self._run_thread.is_alive():
            self.bell()
            self.notify("run still in progress — pause or wait before quitting", severity="warning")
            return
        self.exit(self.final_status)
