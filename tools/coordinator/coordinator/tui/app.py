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
from coordinator.journal import ControlIntent
from coordinator.journal import ControlIntentName
from coordinator.journal import Journal
from coordinator.journal import Snapshot
from coordinator.journal import complete_line_count
from coordinator.journal import load_snapshot
from coordinator.manifest import PlanManifest
from coordinator.manifest import load_manifest
from coordinator.run import RunStatus
from coordinator.run import start_run_in_thread
from coordinator.statedir import journal_path
from coordinator.statedir import state_dir
from coordinator.tui.drilldown import ConfirmScreen
from coordinator.tui.drilldown import NodeDetailScreen
from coordinator.tui.drilldown import TextScreen
from coordinator.tui.drilldown import tail_text
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
_SNAPSHOT_RETRY_DELAY_SECONDS = 0.05


class StateReader:
    """Re-reads the snapshot, no-oping when the journal hasn't grown.

    Persistent read failures (e.g. a corrupt journal) are surfaced via
    ``last_error`` so the dashboard reports them instead of silently
    freezing on the last good state.
    """

    def __init__(self, plan_dir: Path) -> None:
        self.plan_dir = plan_dir
        self._last_size = -1
        self.last_error: str | None = None

    def read(self) -> Snapshot | None:
        path = journal_path(self.plan_dir)
        size = path.stat().st_size if path.is_file() else 0
        if size == self._last_size:
            return None
        self._last_size = size
        try:
            snapshot = load_snapshot(self.plan_dir)
        except Exception:
            # A mid-write race; retry once before giving up on this tick.
            time.sleep(_SNAPSHOT_RETRY_DELAY_SECONDS)
            try:
                snapshot = load_snapshot(self.plan_dir)
            except Exception as e:
                self._last_size = -1
                self.last_error = f"state unreadable: {e}"
                return None
        self.last_error = None
        return snapshot


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
    BINDINGS = [
        ("q", "quit_if_idle", "Quit (when idle)"),
        ("p", "pause", "Pause"),
        ("r", "resume", "Resume"),
        ("t", "retry_selected", "Retry task"),
        ("s", "skip_selected", "Skip task"),
        ("a", "approve_selected", "Approve"),
        ("A", "abort_run", "Abort run"),
        ("f", "show_failure_report", "Failure report"),
        ("enter", "open_details", "Details"),
    ]

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
        # (label, journal position when appended): shown as "requested"
        # until the scheduler's consumed position passes them.
        self._requested_intents: list[tuple[str, int]] = []

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
        if self.reader.last_error is not None:
            parts.append(self.reader.last_error)
        if self.run_error is not None:
            parts.append(f"RUN CRASHED: {self.run_error}")
        elif not self._run_active() and self.final_status not in (None, "completed"):
            run_id = snapshot.run_id if snapshot is not None else None
            parts.append(
                f"run stopped — controls are recorded and apply on `coordinator resume {run_id or '<run-id>'}`"
            )
        consumed = snapshot.intents_consumed if snapshot is not None else 0
        pending = [label for label, position in self._requested_intents if position >= consumed]
        if pending:
            parts.append(f"requested: {', '.join(pending)}")
        self.status_text = "  •  ".join(parts)
        status.update(self.status_text)

    # -- Controls: every control APPENDS a control-intent to the journal;
    # the TUI never mutates scheduler state directly (REQ-UX-4). The
    # scheduler picks intents up at the top of its loop, so run-level
    # pause latency is one node step.

    def _run_active(self) -> bool:
        return self._run_thread is not None and self._run_thread.is_alive()

    def _append_intent(self, intent: ControlIntentName, node_id: str | None = None) -> None:
        position = complete_line_count(journal_path(self.plan_dir))
        Journal(journal_path(self.plan_dir)).append(ControlIntent(intent=intent, node_id=node_id))
        label = intent if node_id is None else f"{intent} {node_id}"
        self._requested_intents.append((label, position))
        if self._run_active():
            self.notify(f"{label} requested")
        else:
            self.notify(f"{label} recorded — takes effect when the run is resumed")
        self._update_status_bar()

    def _selected_node_id(self) -> str | None:
        table = self.query_one(DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value)

    def _node_state(self, node_id: str) -> str:
        if self._last_snapshot is not None and node_id in self._last_snapshot.nodes:
            return self._last_snapshot.nodes[node_id].state
        return "pending"

    def action_pause(self) -> None:
        self._append_intent("pause")

    def action_resume(self) -> None:
        self._append_intent("resume")

    def action_retry_selected(self) -> None:
        node_id = self._selected_node_id()
        if node_id is not None:
            self._append_intent("retry", node_id)

    def action_skip_selected(self) -> None:
        node_id = self._selected_node_id()
        if node_id is None:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._append_intent("skip", node_id)

        self.push_screen(ConfirmScreen(f"Skip node {node_id}? Dependents will run as if it passed."), on_confirm)

    def action_approve_selected(self) -> None:
        node_id = self._selected_node_id()
        if node_id is None:
            return
        if self._node_state(node_id) != "waiting-human":
            self.notify(f"{node_id} is not waiting for approval", severity="warning")
            return
        self._append_intent("approve", node_id)

    def action_abort_run(self) -> None:
        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._append_intent("abort")

        self.push_screen(ConfirmScreen("Abort the run? The in-flight worker will be killed."), on_confirm)

    def action_open_details(self) -> None:
        node_id = self._selected_node_id()
        if node_id is None:
            return
        node_snapshot = self._last_snapshot.nodes.get(node_id) if self._last_snapshot is not None else None
        self.push_screen(NodeDetailScreen(node_id, self._node_state(node_id), node_snapshot, self._append_intent))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_open_details()

    def action_show_failure_report(self) -> None:
        report_path = state_dir(self.plan_dir) / "failure_report.md"
        if not report_path.is_file():
            self.notify("no failure report for this run", severity="warning")
            return
        self.push_screen(TextScreen("failure report", tail_text(report_path)))

    def action_quit_if_idle(self) -> None:
        if self._run_thread is not None and self._run_thread.is_alive():
            self.bell()
            self.notify("run still in progress — pause or wait before quitting", severity="warning")
            return
        self.exit(self.final_status)
