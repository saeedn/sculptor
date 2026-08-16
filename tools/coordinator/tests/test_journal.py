import re
import subprocess
from pathlib import Path

import pytest
from loguru import logger

from coordinator.journal import AttemptStarted
from coordinator.journal import CommitRecorded
from coordinator.journal import ControlIntent
from coordinator.journal import GateResult
from coordinator.journal import GateStarted
from coordinator.journal import Journal
from coordinator.journal import JournalError
from coordinator.journal import RunPaused
from coordinator.journal import RunStarted
from coordinator.journal import SignalObserved
from coordinator.journal import Snapshot
from coordinator.journal import TaskStateChanged
from coordinator.journal import load_snapshot
from coordinator.journal import replay
from coordinator.journal import save_snapshot
from coordinator.statedir import attempt_dir
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path
from coordinator.statedir import new_run_id
from coordinator.statedir import read_run_id
from coordinator.statedir import sanitize_node_id
from coordinator.statedir import write_run_id


def make_events() -> list:
    return [
        RunStarted(run_id="run-1", plan_dir="/plan", manifest_hash="abc"),
        TaskStateChanged(node_id="1.1", old_state="pending", new_state="running"),
        AttemptStarted(node_id="1.1", attempt_index=0, worker_registration="claude", pid=42, attempt_dir="/a/0"),
        SignalObserved(node_id="1.1", attempt_index=0, event="session-start", session_id="sess-1"),
        SignalObserved(node_id="1.1", attempt_index=0, event="stop", transcript_path="/t.jsonl"),
        GateStarted(node_id="1.1", gate="mechanical"),
        GateResult(node_id="1.1", gate="mechanical", passed=True),
        CommitRecorded(node_id="1.1", commit="deadbeef"),
        TaskStateChanged(node_id="1.1", old_state="running", new_state="completed"),
        ControlIntent(intent="pause"),
        RunPaused(reason="rate-limit", resume_hint="wait an hour"),
    ]


def test_append_replay_round_trip(tmp_path: Path) -> None:
    state_dir = ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    events = make_events()
    for event in events:
        journal.append(event)
    replayed = list(replay(journal_path(tmp_path)))
    assert replayed == events
    assert state_dir.is_dir()


def test_replay_missing_journal_yields_nothing(tmp_path: Path) -> None:
    assert list(replay(tmp_path / "journal.jsonl")) == []


def test_replay_tolerates_truncated_final_line(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    events = make_events()[:3]
    for event in events:
        journal.append(event)
    with open(journal_path(tmp_path), "a") as f:
        f.write('{"type": "task-state-changed", "ts": 1.0, "node')
    warnings: list[str] = []
    handler_id = logger.add(warnings.append, format="{message}", level="WARNING")
    try:
        replayed = list(replay(journal_path(tmp_path)))
    finally:
        logger.remove(handler_id)
    assert replayed == events
    assert any("truncated" in message for message in warnings)


def test_append_after_truncated_final_line_discards_the_chunk(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    events = make_events()[:3]
    for event in events:
        journal.append(event)
    with open(journal_path(tmp_path), "a") as f:
        f.write('{"type": "task-state-changed", "ts": 1.0, "node')
    resumed = make_events()[3]
    journal.append(resumed)
    # The truncated chunk is gone and the journal replays cleanly.
    assert list(replay(journal_path(tmp_path))) == events + [resumed]


def test_replay_rejects_unknown_event_type(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal_path(tmp_path).write_text('{"type": "mystery-event", "ts": 1.0}\n')
    with pytest.raises(JournalError):
        list(replay(journal_path(tmp_path)))


def test_replay_rejects_corrupt_complete_line(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal_path(tmp_path).write_text("not json at all\n")
    with pytest.raises(JournalError):
        list(replay(journal_path(tmp_path)))


def test_snapshot_fold() -> None:
    snapshot = Snapshot.from_events(make_events())
    assert snapshot.run_id == "run-1"
    assert snapshot.manifest_hash == "abc"
    assert snapshot.journal_line_count == len(make_events())
    node = snapshot.nodes["1.1"]
    assert node.state == "completed"
    assert len(node.attempts) == 1
    attempt = node.attempts[0]
    assert attempt.session_id == "sess-1"
    assert attempt.transcript_path == "/t.jsonl"
    assert attempt.signals == ["session-start", "stop"]
    assert node.gates[0].gate == "mechanical"
    assert node.gates[0].passed is True
    assert node.commits == ["deadbeef"]
    assert snapshot.run_status == "paused"
    assert snapshot.pause_reason == "rate-limit"
    assert snapshot.resume_hint == "wait an hour"
    assert [intent.intent for intent in snapshot.intents] == ["pause"]


def test_resume_intent_clears_pause() -> None:
    events = make_events() + [ControlIntent(intent="resume")]
    snapshot = Snapshot.from_events(events)
    assert snapshot.run_status == "running"
    assert snapshot.pause_reason is None


def test_attempt_history_ordering() -> None:
    events = [
        AttemptStarted(node_id="a", attempt_index=0, worker_registration="w", attempt_dir="/0"),
        AttemptStarted(node_id="a", attempt_index=1, worker_registration="w2", attempt_dir="/1"),
        SignalObserved(node_id="a", attempt_index=1, event="session-start", session_id="s2"),
    ]
    snapshot = Snapshot.from_events(events)
    attempts = snapshot.nodes["a"].attempts
    assert [a.attempt_index for a in attempts] == [0, 1]
    assert attempts[0].session_id is None
    assert attempts[1].session_id == "s2"


def test_load_snapshot_prefers_fresh_snapshot(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    for event in make_events():
        journal.append(event)
    snapshot = Snapshot.from_events(replay(journal_path(tmp_path)))
    save_snapshot(snapshot, tmp_path)
    assert load_snapshot(tmp_path) == snapshot


def test_load_snapshot_rebuilds_on_mismatch(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    journal = Journal(journal_path(tmp_path))
    for event in make_events():
        journal.append(event)
    stale = Snapshot(run_id="stale", journal_line_count=1)
    save_snapshot(stale, tmp_path)
    loaded = load_snapshot(tmp_path)
    assert loaded.run_id == "run-1"
    assert loaded.journal_line_count == len(make_events())
    # The rebuilt snapshot is persisted.
    assert load_snapshot(tmp_path) == loaded


def test_gitignore_written_once(tmp_path: Path) -> None:
    state_dir = ensure_state_dir(tmp_path)
    gitignore = state_dir / ".gitignore"
    assert gitignore.read_text() == "*\n"
    gitignore.write_text("custom\n")
    ensure_state_dir(tmp_path)
    assert gitignore.read_text() == "custom\n"


def test_gitignore_hides_state_from_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    state_dir = ensure_state_dir(tmp_path)
    (state_dir / "journal.jsonl").write_text("{}\n")
    status = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"], check=True, capture_output=True, text=True
    ).stdout
    assert "_state" not in status


def test_attempt_dir_sanitizes_node_id(tmp_path: Path) -> None:
    path = attempt_dir(tmp_path, "phase-review:1", 2)
    assert path.parent.name.startswith("phase-review_1-")
    assert path.name == "2"
    assert path.parent.parent == tmp_path / "_state" / "attempts"


def test_sanitize_node_id() -> None:
    assert sanitize_node_id("1.2") == "1.2"
    sanitized = sanitize_node_id("a/b c:d")
    assert sanitized.startswith("a_b_c_d-")
    # Distinct unsafe ids never collide onto one attempt dir.
    assert sanitize_node_id("a:b") != sanitize_node_id("a_b")
    assert sanitize_node_id("a:b") == sanitize_node_id("a:b")


def test_new_run_id_charset() -> None:
    run_id = new_run_id()
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id)
    assert run_id.startswith("run-")


def test_run_id_file_round_trip(tmp_path: Path) -> None:
    ensure_state_dir(tmp_path)
    assert read_run_id(tmp_path) is None
    write_run_id(tmp_path, "run-x")
    assert read_run_id(tmp_path) == "run-x"
