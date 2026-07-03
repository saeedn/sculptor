"""Shared fake-worker fixtures: scripted sys.executable workers, not Claude."""

import subprocess
import sys
from pathlib import Path
from typing import Literal

from coordinator.registrations import WorkerRegistration

# Shared prologue for fake workers: argv[1] is the attempt dir; emit()
# appends hook-shaped events to this attempt's signals.jsonl.
FAKE_PROLOGUE = """\
import json, os, pathlib, signal, sys, time
attempt_dir = pathlib.Path(sys.argv[1])
signals = attempt_dir / "signals.jsonl"
def emit(event, payload=None):
    with open(signals, "a") as f:
        f.write(json.dumps({"event": event, "ts": time.time(), "payload": payload}) + "\\n")
"""

STOP_THEN_SLEEP = (
    FAKE_PROLOGUE
    + """
emit("SessionStart", {"session_id": "fake-sess", "transcript_path": "/tmp/fake-transcript.jsonl"})
print("fake worker output")
sys.stdout.flush()
emit("Stop", {"session_id": "fake-sess", "last_assistant_message": "SUCCESS: did the thing"})
time.sleep(60)
"""
)

EXIT_WITHOUT_STOP = (
    FAKE_PROLOGUE
    + """
emit("SessionStart", {"session_id": "fake-sess"})
sys.exit(0)
"""
)

ASK_QUESTION_THEN_SLEEP = (
    FAKE_PROLOGUE
    + """
emit("SessionStart", {"session_id": "fake-sess"})
emit("PreToolUse", {"tool_name": "AskUserQuestion", "session_id": "fake-sess"})
time.sleep(60)
"""
)

IGNORE_SIGTERM = (
    FAKE_PROLOGUE
    + """
signal.signal(signal.SIGTERM, signal.SIG_IGN)
emit("Stop", {"session_id": "fake-sess"})
time.sleep(60)
"""
)

ECHO_ENV = (
    FAKE_PROLOGUE
    + """
keys = ["SCULPT_API_PORT", "SCULPTOR_FOLDER", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "AI_AGENT", "EXTRA_VAR"]
emit("Stop", {"session_id": "fake-sess", "env": {k: os.environ.get(k) for k in keys}})
"""
)

SLEEP_FOREVER = FAKE_PROLOGUE + "\ntime.sleep(60)\n"

# A well-behaved task worker: writes a file named after its node id
# (the attempt dir's parent is the sanitized node id), commits it in
# the repo it was launched in (its cwd), then signals Stop and exits.
COMMIT_THEN_STOP = (
    FAKE_PROLOGUE
    + """
import subprocess
node = attempt_dir.parent.name
emit("SessionStart", {"session_id": "fake-" + node, "transcript_path": "/tmp/fake-" + node + ".jsonl"})
with open("file_" + node + ".txt", "w") as f:
    f.write("content from " + node + "\\n")
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-q", "-m", "fake commit for " + node], check=True)
emit("Stop", {"session_id": "fake-" + node, "last_assistant_message": "SUCCESS: committed " + node})
"""
)

# Signals Stop without committing anything — trips the missing-commit check.
STOP_WITHOUT_COMMIT = (
    FAKE_PROLOGUE
    + """
emit("SessionStart", {"session_id": "fake-sess"})
emit("Stop", {"session_id": "fake-sess"})
"""
)

# Leaves an uncommitted file behind — trips the dirty-tree-after-task check.
DIRTY_THEN_STOP = (
    FAKE_PROLOGUE
    + """
node = attempt_dir.parent.name
with open("dirty_" + node + ".txt", "w") as f:
    f.write("uncommitted\\n")
emit("Stop", {"session_id": "fake-sess"})
"""
)


def make_registration(
    script: Path, mode: Literal["print", "interactive"], env: dict[str, str] | None = None
) -> WorkerRegistration:
    return WorkerRegistration(
        name="fake",
        display_name="Fake worker",
        mode=mode,
        command=[sys.executable, str(script), "{attempt_dir}", "{prompt}"],
        env=env or {},
    )


def write_registration_yaml(directory: Path, name: str, script: Path, mode: str = "print") -> None:
    """Write a fake-worker registration file for layered discovery."""
    directory.mkdir(parents=True, exist_ok=True)
    command_lines = "\n".join(
        f'  - "{element}"' for element in (sys.executable, str(script), "{attempt_dir}", "{prompt}")
    )
    (directory / f"{name}.yaml").write_text(
        f"display_name: Fake worker {name}\nmode: {mode}\ncommand:\n{command_lines}\n"
    )


def make_git_repo(path: Path) -> Path:
    """A fresh git repo with an identity configured and one initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "fake@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Fake Worker"], check=True)
    (path / "README.md").write_text("test repo\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True)
    return path


def repo_commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", message], check=True)
