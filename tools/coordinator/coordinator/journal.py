"""Append-only execution journal (source of truth) and derived snapshot.

``journal.jsonl`` is write-ahead: every state transition is appended —
flushed and fsynced — BEFORE it takes effect elsewhere, so a killed
coordinator resumes from disk. ``state.json`` is a derived, disposable
snapshot: loading prefers it but verifies its recorded journal line
count against the actual journal, rebuilding by replay on mismatch.
The journal is never rewritten in place.

This module owns the whole event vocabulary; the scheduler and the TUI
share these models rather than scattering string-typed event names.
"""

import json
import os
import sys
import tempfile
import time
from collections.abc import Iterable
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationError

from coordinator.statedir import journal_path
from coordinator.statedir import snapshot_path

JOURNAL_SCHEMA_VERSION = 1

ControlIntentName = Literal["pause", "resume", "retry", "skip", "approve", "abort"]


class JournalError(Exception):
    pass


class RunStarted(BaseModel):
    type: Literal["run-started"] = "run-started"
    ts: float = Field(default_factory=time.time)
    schema_version: int = JOURNAL_SCHEMA_VERSION
    run_id: str
    plan_dir: str
    manifest_hash: str


class TaskStateChanged(BaseModel):
    type: Literal["task-state-changed"] = "task-state-changed"
    ts: float = Field(default_factory=time.time)
    node_id: str
    old_state: str
    new_state: str
    reason: str | None = None


class AttemptStarted(BaseModel):
    type: Literal["attempt-started"] = "attempt-started"
    ts: float = Field(default_factory=time.time)
    node_id: str
    attempt_index: int
    worker_registration: str
    pid: int | None = None
    attempt_dir: str


class SignalObserved(BaseModel):
    type: Literal["signal-observed"] = "signal-observed"
    ts: float = Field(default_factory=time.time)
    node_id: str
    attempt_index: int
    event: str
    session_id: str | None = None
    transcript_path: str | None = None


class GateStarted(BaseModel):
    type: Literal["gate-started"] = "gate-started"
    ts: float = Field(default_factory=time.time)
    node_id: str
    gate: str


class GateResult(BaseModel):
    type: Literal["gate-result"] = "gate-result"
    ts: float = Field(default_factory=time.time)
    node_id: str
    gate: str
    passed: bool
    findings: str | None = None


class CommitRecorded(BaseModel):
    type: Literal["commit-recorded"] = "commit-recorded"
    ts: float = Field(default_factory=time.time)
    node_id: str
    commit: str


class ControlIntent(BaseModel):
    type: Literal["control-intent"] = "control-intent"
    ts: float = Field(default_factory=time.time)
    intent: ControlIntentName
    node_id: str | None = None


class RunPaused(BaseModel):
    type: Literal["run-paused"] = "run-paused"
    ts: float = Field(default_factory=time.time)
    reason: str
    resume_hint: str | None = None


class IntentsConsumed(BaseModel):
    """Marks every control intent before journal position ``position`` as consumed.

    Appended by the scheduler before it acts on a batch of intents, so a
    replay never re-applies them.
    """

    type: Literal["intents-consumed"] = "intents-consumed"
    ts: float = Field(default_factory=time.time)
    position: int


class ReviewHandoff(BaseModel):
    """The end-of-run Review handoff: spawned agent id, or None for the printed fallback."""

    type: Literal["review-handoff"] = "review-handoff"
    ts: float = Field(default_factory=time.time)
    agent_id: str | None = None


Event = Annotated[
    RunStarted
    | TaskStateChanged
    | AttemptStarted
    | SignalObserved
    | GateStarted
    | GateResult
    | CommitRecorded
    | ControlIntent
    | RunPaused
    | IntentsConsumed
    | ReviewHandoff,
    Field(discriminator="type"),
]

_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


class Journal:
    """Append-only JSONL event log with write-ahead durability."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event: Event) -> None:
        line = json.dumps(event.model_dump(), separators=(",", ":"))
        self._discard_truncated_final_line()
        with open(self.path, "a") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _discard_truncated_final_line(self) -> None:
        """Drop a crash-truncated final chunk before appending.

        Appending straight after an unterminated chunk would fuse the two
        into one newline-terminated garbage line that every later
        ``replay`` rejects as corruption. ``replay`` already ignores the
        unterminated chunk, so truncating it away loses nothing.
        """
        try:
            f = open(self.path, "rb+")
        except FileNotFoundError:
            return
        with f:
            size = f.seek(0, os.SEEK_END)
            if size == 0:
                return
            f.seek(size - 1)
            if f.read(1) == b"\n":
                return
            f.seek(0)
            data = f.read()
            f.truncate(data.rfind(b"\n") + 1)


def replay(path: Path) -> Iterator[Event]:
    """Yield every complete event in the journal.

    Only newline-terminated lines count as complete: a crash mid-append
    leaves an unterminated final chunk, which is skipped with a warning.
    A terminated line that fails to parse — including an unknown event
    type — is corruption (the journal is coordinator-private) and raises
    :class:`JournalError`.
    """
    if not path.is_file():
        return
    text = path.read_text()
    complete, _, truncated = text.rpartition("\n")
    if truncated:
        print(f"warning: ignoring truncated final journal line in {path}", file=sys.stderr)
    if not complete:
        return
    for line_number, line in enumerate(complete.split("\n"), start=1):
        try:
            yield _EVENT_ADAPTER.validate_json(line)
        except ValidationError as e:
            raise JournalError(f"{path}:{line_number}: invalid journal event: {e}")


def complete_line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return path.read_text().count("\n")


class AttemptRecord(BaseModel):
    attempt_index: int
    worker_registration: str
    pid: int | None = None
    attempt_dir: str
    session_id: str | None = None
    transcript_path: str | None = None
    signals: list[str] = []
    last_signal_ts: float | None = None


class GateRecord(BaseModel):
    gate: str
    # None while the gate is running; set by the gate-result event.
    passed: bool | None = None
    findings: str | None = None


class NodeSnapshot(BaseModel):
    node_id: str
    state: str = "pending"
    attempts: list[AttemptRecord] = []
    gates: list[GateRecord] = []
    commits: list[str] = []


class Snapshot(BaseModel):
    """Current run state folded from the journal; the TUI renders from this."""

    schema_version: int = JOURNAL_SCHEMA_VERSION
    run_id: str | None = None
    plan_dir: str | None = None
    manifest_hash: str | None = None
    run_status: str = "running"
    pause_reason: str | None = None
    resume_hint: str | None = None
    journal_line_count: int = 0
    nodes: dict[str, NodeSnapshot] = {}
    intents: list[ControlIntent] = []
    # Journal position up to which control intents are consumed.
    intents_consumed: int = 0
    # Agent id spawned by the Review handoff (None until it happens, and
    # for the printed fallback).
    review_agent_id: str | None = None

    @classmethod
    def from_events(cls, events: Iterable[Event]) -> "Snapshot":
        snapshot = cls()
        for event in events:
            snapshot._apply(event)
            snapshot.journal_line_count += 1
        return snapshot

    def _node(self, node_id: str) -> NodeSnapshot:
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeSnapshot(node_id=node_id)
        return self.nodes[node_id]

    def _apply(self, event: Event) -> None:
        if isinstance(event, RunStarted):
            self.run_id = event.run_id
            self.plan_dir = event.plan_dir
            self.manifest_hash = event.manifest_hash
            self.run_status = "running"
            self.pause_reason = None
            self.resume_hint = None
        elif isinstance(event, TaskStateChanged):
            self._node(event.node_id).state = event.new_state
        elif isinstance(event, AttemptStarted):
            node = self._node(event.node_id)
            for attempt in node.attempts:
                # The scheduler journals the attempt write-ahead (pid
                # unknown); the executor re-journals it post-spawn with
                # the real pid. Merge rather than duplicate.
                if attempt.attempt_index == event.attempt_index:
                    if event.pid is not None:
                        attempt.pid = event.pid
                    attempt.worker_registration = event.worker_registration
                    attempt.attempt_dir = event.attempt_dir
                    break
            else:
                node.attempts.append(
                    AttemptRecord(
                        attempt_index=event.attempt_index,
                        worker_registration=event.worker_registration,
                        pid=event.pid,
                        attempt_dir=event.attempt_dir,
                    )
                )
        elif isinstance(event, SignalObserved):
            node = self._node(event.node_id)
            for attempt in node.attempts:
                if attempt.attempt_index == event.attempt_index:
                    attempt.signals.append(event.event)
                    attempt.last_signal_ts = event.ts
                    if event.session_id is not None:
                        attempt.session_id = event.session_id
                    if event.transcript_path is not None:
                        attempt.transcript_path = event.transcript_path
        elif isinstance(event, GateStarted):
            self._node(event.node_id).gates.append(GateRecord(gate=event.gate))
        elif isinstance(event, GateResult):
            node = self._node(event.node_id)
            for gate in reversed(node.gates):
                if gate.gate == event.gate and gate.passed is None:
                    gate.passed = event.passed
                    gate.findings = event.findings
                    break
            else:
                node.gates.append(GateRecord(gate=event.gate, passed=event.passed, findings=event.findings))
        elif isinstance(event, CommitRecorded):
            self._node(event.node_id).commits.append(event.commit)
        elif isinstance(event, ControlIntent):
            self.intents.append(event)
            if event.intent == "resume":
                self.run_status = "running"
                self.pause_reason = None
                self.resume_hint = None
        elif isinstance(event, RunPaused):
            self.run_status = "paused"
            self.pause_reason = event.reason
            self.resume_hint = event.resume_hint
        elif isinstance(event, IntentsConsumed):
            self.intents_consumed = max(self.intents_consumed, event.position)
        elif isinstance(event, ReviewHandoff):
            self.review_agent_id = event.agent_id


def save_snapshot(snapshot: Snapshot, plan_dir: Path) -> None:
    # Atomic replace: the TUI re-reads this file on a timer and must
    # never see a half-written snapshot.
    target = snapshot_path(plan_dir)
    fd, temp_path = tempfile.mkstemp(dir=target.parent, prefix=".state.json.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(snapshot.model_dump_json(indent=2) + "\n")
        os.replace(temp_path, target)
    except BaseException:
        os.unlink(temp_path)
        raise


def load_snapshot(plan_dir: Path) -> Snapshot:
    """Load the snapshot, rebuilding from the journal when stale or missing.

    A snapshot whose recorded journal line count does not match the
    actual journal is discarded and rebuilt by replay (the journal is
    the source of truth). The rebuilt snapshot is persisted.
    """
    journal_file = journal_path(plan_dir)
    actual_count = complete_line_count(journal_file)
    snapshot_file = snapshot_path(plan_dir)
    if snapshot_file.is_file():
        try:
            snapshot = Snapshot.model_validate_json(snapshot_file.read_text())
        except ValidationError:
            snapshot = None
        if snapshot is not None and snapshot.journal_line_count == actual_count:
            return snapshot
    snapshot = Snapshot.from_events(replay(journal_file))
    save_snapshot(snapshot, plan_dir)
    return snapshot
