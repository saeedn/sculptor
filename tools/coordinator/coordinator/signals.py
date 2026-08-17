"""Parsing of an attempt's hook-signal journal (signals.jsonl).

Leaf module: the launcher polls signals live; the scheduler inspects
them at resume time to recognize attempts that completed under a dead
coordinator. Neither path parses the worker's screen — files only.
"""

import json
from pathlib import Path


class SignalReader:
    """Incremental reader of an attempt's signals.jsonl.

    Remembers the file offset and only consumes newline-terminated
    lines, so a partially-written final line is picked up on the next
    poll. Extracts session_id / transcript_path from the first payload
    carrying them and tracks the latest last_assistant_message.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._offset = 0
        self.events: list[dict] = []
        self.session_id: str | None = None
        self.transcript_path: str | None = None
        self.last_assistant_message: str | None = None

    def poll(self) -> list[dict]:
        if not self.path.is_file():
            return []
        with open(self.path, "rb") as f:
            f.seek(self._offset)
            chunk = f.read()
        complete, separator, _partial = chunk.rpartition(b"\n")
        if not separator:
            return []
        self._offset += len(complete) + 1
        new_events: list[dict] = []
        for raw_line in complete.split(b"\n"):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except ValueError:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                if self.session_id is None and payload.get("session_id"):
                    self.session_id = payload["session_id"]
                if self.transcript_path is None and payload.get("transcript_path"):
                    self.transcript_path = payload["transcript_path"]
                if payload.get("last_assistant_message"):
                    self.last_assistant_message = payload["last_assistant_message"]
            self.events.append(event)
            new_events.append(event)
        return new_events


def is_stop(event: dict) -> bool:
    return event.get("event") == "Stop"


def pending_background_tasks(event: dict) -> list[dict]:
    """The background tasks still running when this Stop fired.

    A worker cannot wait by ending its turn — the session exits and the
    tasks die with it — so a Stop carrying running tasks is an abandoned
    turn, not a finished one.
    """
    payload = event.get("payload")
    if not is_stop(event) or not isinstance(payload, dict):
        return []
    tasks = payload.get("background_tasks")
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict) and task.get("status") == "running"]


def is_clean_stop(event: dict) -> bool:
    """A Stop that ended the turn with no background work left running."""
    return is_stop(event) and not pending_background_tasks(event)


def describe_background_tasks(tasks: list[dict]) -> str:
    """One-line summary of abandoned tasks, for the retry context."""
    described = ", ".join(
        f"{task.get('id', '?')} ({' '.join(str(task.get('description') or task.get('command') or '?').split())})"
        for task in tasks
    )
    return f"{len(tasks)} background task(s) still running when the turn ended: {described}"


def read_completed_signals(signals_path: Path) -> SignalReader | None:
    """The parsed signals of an attempt that reached a clean Stop, else None.

    Lets a resumed coordinator recognize that a mid-flight worker actually
    finished its turn (the Stop is on disk even though the coordinator that
    spawned it died before consuming it). A Stop that abandoned background
    tasks does not count — that attempt has to be re-run.
    """
    reader = SignalReader(signals_path)
    events = reader.poll()
    if any(is_clean_stop(event) for event in events):
        return reader
    return None


def is_waiting(event: dict) -> bool:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return False
    if event.get("event") == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        return True
    if event.get("event") == "Notification" and payload.get("notification_type") == "idle_prompt":
        return True
    return False
