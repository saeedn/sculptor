"""Shared fake-worker fixtures: scripted sys.executable workers, not Claude."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

from coordinator.registrations import WorkerRegistration
from coordinator.statedir import sanitize_node_id

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


# Scenario-driven fake worker: argv is [attempt_dir, scenario_dir]. The
# scenario file for this attempt is <scenario_dir>/<node>_<attempt>.json
# (node = the attempt dir's parent, i.e. the sanitized node id). A missing
# scenario file crashes with exit 3 and no signals — resume tests rely on
# this to prove a completed task is never re-run. The scenario is an
# ordered action list:
#   {"actions": [{"signal": "SessionStart"},
#                {"write": {"path": "a.txt", "content": "x"}},
#                {"commit": "message"},
#                {"verdict": {"pass": true, "findings": []}},
#                {"signal": "Stop"},
#                {"sleep": 30}],
#    "exit_code": 0}
# "waiting" emits a PreToolUse/AskUserQuestion signal; "verdict" writes
# the given JSON to <attempt_dir>/verdict.json (reviewer scenarios).
SCENARIO_WORKER = """\
import json, pathlib, subprocess, sys, time
attempt_dir = pathlib.Path(sys.argv[1])
scenario_dir = pathlib.Path(sys.argv[2])
node = attempt_dir.parent.name
attempt = attempt_dir.name
signals = attempt_dir / "signals.jsonl"
def emit(event, payload=None):
    with open(signals, "a") as f:
        f.write(json.dumps({"event": event, "ts": time.time(), "payload": payload}) + "\\n")
scenario_path = scenario_dir / (node + "_" + attempt + ".json")
if not scenario_path.exists():
    sys.exit(3)
scenario = json.loads(scenario_path.read_text())
session = "fake-" + node + "-" + attempt
for action in scenario.get("actions", []):
    if "signal" in action:
        name = action["signal"]
        if name == "waiting":
            emit("PreToolUse", {"tool_name": "AskUserQuestion", "session_id": session})
        else:
            payload = {"session_id": session, "transcript_path": "/tmp/" + session + ".jsonl"}
            if name == "Stop":
                payload["last_assistant_message"] = "SUCCESS: " + node
            emit(name, payload)
    elif "write" in action:
        pathlib.Path(action["write"]["path"]).write_text(action["write"]["content"])
    elif "commit" in action:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", action["commit"]], check=True)
    elif "verdict" in action:
        (attempt_dir / "verdict.json").write_text(json.dumps(action["verdict"]))
    elif "sleep" in action:
        time.sleep(action["sleep"])
sys.exit(scenario.get("exit_code", 0))
"""


def write_scenario(
    scenario_dir: Path, node_id: str, attempt_index: int, actions: list[dict], exit_code: int = 0
) -> None:
    scenario_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = scenario_dir / f"{sanitize_node_id(node_id)}_{attempt_index}.json"
    scenario_path.write_text(json.dumps({"actions": actions, "exit_code": exit_code}))


def pass_actions(node_id: str) -> list[dict]:
    """The standard well-behaved task: write a file, commit, Stop."""
    return [
        {"signal": "SessionStart"},
        {"write": {"path": f"file_{sanitize_node_id(node_id)}.txt", "content": f"content from {node_id}\n"}},
        {"commit": f"fake commit for {node_id}"},
        {"signal": "Stop"},
    ]


def make_scenario_registration(
    script: Path, scenario_dir: Path, mode: Literal["print", "interactive"] = "print"
) -> WorkerRegistration:
    return WorkerRegistration(
        name="fake-scenario",
        display_name="Scenario-driven fake worker",
        mode=mode,
        command=[sys.executable, str(script), "{attempt_dir}", str(scenario_dir), "{prompt}"],
    )


def write_scenario_registration_yaml(
    directory: Path, name: str, script: Path, scenario_dir: Path, mode: str = "print"
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    command_lines = "\n".join(
        f'  - "{element}"' for element in (sys.executable, str(script), "{attempt_dir}", str(scenario_dir), "{prompt}")
    )
    (directory / f"{name}.yaml").write_text(
        f"display_name: Scenario fake {name}\nmode: {mode}\ncommand:\n{command_lines}\n"
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
