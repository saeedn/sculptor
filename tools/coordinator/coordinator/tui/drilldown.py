"""Node detail screens: attempt history, transcripts, and human approval."""

import os
from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.screen import Screen
from textual.widgets import DataTable
from textual.widgets import Footer
from textual.widgets import Static

from coordinator.journal import ControlIntentName
from coordinator.journal import NodeSnapshot

_TAIL_LINES = 200
_DIFF_TAIL_BYTES = 64 * 1024


def tail_text(path: Path, max_lines: int = _TAIL_LINES, max_bytes: int = _DIFF_TAIL_BYTES) -> str:
    """The tail of a possibly-large file — never load multi-MB files whole."""
    if not path.is_file():
        return f"(file not found: {path})"
    with open(path, "rb") as f:
        size = f.seek(0, os.SEEK_END)
        truncated = size > max_bytes
        f.seek(max(0, size - max_bytes))
        data = f.read()
    text = data.decode(errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        truncated = True
    prefix = f"[... showing the tail of {path} ...]\n" if truncated else ""
    return prefix + "\n".join(lines)


class TextScreen(ModalScreen):
    """A scrollable read-only text view (transcripts, reports, diffs)."""

    BINDINGS = [("escape", "dismiss", "Back")]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:
        yield Static(self.title_text, id="text-title")
        yield VerticalScroll(Static(self.body_text))
        yield Footer()


class ConfirmScreen(ModalScreen[bool]):
    """y/n confirmation for destructive controls."""

    BINDINGS = [("y", "confirm", "Yes"), ("n", "cancel", "No"), ("escape", "cancel", "No")]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        yield Static(f"{self.question}  [y/n]", id="confirm-question")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NodeDetailScreen(Screen):
    """Drill-down for one node: attempts, gates, commits, paths, approval."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("o", "open_transcript", "Transcript tail"),
        ("d", "open_diff", "Diff"),
        ("a", "approve", "Approve"),
        ("t", "retry", "Retry"),
    ]

    def __init__(
        self,
        node_id: str,
        state: str,
        node_snapshot: NodeSnapshot | None,
        on_intent: Callable[[ControlIntentName, str], None],
    ) -> None:
        super().__init__()
        self.node_id = node_id
        self.state = state
        self.node_snapshot = node_snapshot
        self.on_intent = on_intent

    def compose(self) -> ComposeResult:
        yield Static(f"node {self.node_id} — {self.state}", id="detail-title")
        yield DataTable(id="attempts")
        yield VerticalScroll(Static(self._details_text(), id="detail-body"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for column in ("attempt", "worker", "last signal", "session id", "pid"):
            table.add_column(column, key=column)
        if self.node_snapshot is not None:
            for attempt in self.node_snapshot.attempts:
                table.add_row(
                    str(attempt.attempt_index),
                    attempt.worker_registration,
                    attempt.signals[-1] if attempt.signals else "-",
                    attempt.session_id or "-",
                    str(attempt.pid) if attempt.pid is not None else "-",
                    key=str(attempt.attempt_index),
                )

    def _latest_attempt_dir(self) -> Path | None:
        if self.node_snapshot is None or not self.node_snapshot.attempts:
            return None
        return Path(self.node_snapshot.attempts[-1].attempt_dir)

    def _details_text(self) -> str:
        lines: list[str] = []
        if self.node_snapshot is not None:
            failed_gates = [g for g in self.node_snapshot.gates if g.passed is not None]
            if failed_gates:
                lines.append("Gate results:")
                for gate in failed_gates:
                    verdict = "pass" if gate.passed else "FAIL"
                    lines.append(f"  [{gate.gate}] {verdict}: {gate.findings or '(no findings)'}")
                lines.append("")
            if self.node_snapshot.commits:
                lines.append("Commits: " + ", ".join(c[:12] for c in self.node_snapshot.commits))
                lines.append("")
            latest = self.node_snapshot.attempts[-1] if self.node_snapshot.attempts else None
            if latest is not None:
                lines.append(f"Attempt dir: {latest.attempt_dir}")
                lines.append(f"Signals: {latest.attempt_dir}/signals.jsonl")
                if latest.transcript_path:
                    lines.append(f"Transcript: {latest.transcript_path}")
                if latest.session_id:
                    lines.append(f"Diagnose with: claude --resume {latest.session_id}")
                lines.append("")
        if self.state == "waiting-human":
            lines.append("WAITING FOR HUMAN APPROVAL — press 'd' to view the diff, 'a' to approve, 't' to retry.")
        return "\n".join(lines) or "(no attempts yet)"

    def action_open_transcript(self) -> None:
        if self.node_snapshot is None or not self.node_snapshot.attempts:
            self.notify("no attempts yet", severity="warning")
            return
        transcript = self.node_snapshot.attempts[-1].transcript_path
        if not transcript:
            self.notify("no transcript recorded for the latest attempt", severity="warning")
            return
        self.app.push_screen(TextScreen(f"transcript tail — {self.node_id}", tail_text(Path(transcript))))

    def action_open_diff(self) -> None:
        attempt_directory = self._latest_attempt_dir()
        if attempt_directory is None:
            self.notify("no attempts yet", severity="warning")
            return
        diff_path = attempt_directory / "human_review.patch"
        self.app.push_screen(TextScreen(f"diff under review — {self.node_id}", tail_text(diff_path)))

    def action_approve(self) -> None:
        if self.state != "waiting-human":
            self.notify("node is not waiting for approval", severity="warning")
            return
        self.on_intent("approve", self.node_id)
        self.app.pop_screen()

    def action_retry(self) -> None:
        self.on_intent("retry", self.node_id)
        self.app.pop_screen()
