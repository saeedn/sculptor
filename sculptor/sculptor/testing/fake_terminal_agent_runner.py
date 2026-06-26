"""Standalone runner program for the fake terminal-agent test harness.

This file is the *program* a fake registered terminal agent launches (see
``fake_terminal_agent.py`` for the harness that registers it). It is launched
by the registration's ``launch_command`` as a job in the agent's login shell,
exactly like the bundled ``claude-code`` registration launches the real Claude
TUI.

It is deliberately **pure stdlib** — it must run under whatever ``python3`` is
on PATH inside an agent's shell, with NO dependency on the ``sculptor`` package
(in particular none on ``agents/default/claude_code_sdk/``, ``agents/pi_agent/``,
or ``agents/hello_agent/``, all of which are removed in later slim-down phases).
The only external program it invokes is the ``sculpt`` CLI (already on PATH
inside agent terminals), which it uses to report busy/idle/files-changed and a
session id — the same lifecycle signals a real registration emits.

How it is driven: the test drops JSON command files into a *commands
directory*; this runner polls that directory, signals ``busy``, executes the
side-effecting command, signals ``files-changed`` after each mutation and
``idle`` when the command finishes. It understands only a small side-effecting
DSL (write_file / edit_file / bash / multi_step / wait_for_file / sleep) — there
is NO chat surface (no JSONL, tool pills, MCP, or ask-user-question), because no
surviving integration test needs one.
"""

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

# Filenames the runner treats specially inside the commands directory.
QUIT_SENTINEL_NAME = "__quit__"
DONE_SUFFIX = ".done"

_POLL_INTERVAL_SECONDS = 0.05
_DEFAULT_WAIT_TIMEOUT_SECONDS = 120.0


def _signal(event: str, *extra: str) -> None:
    """Invoke the real ``sculpt signal`` CLI; failures are swallowed.

    Mirrors the bundled hooks' ``sculpt signal <event> || true`` — a signal is
    best-effort telemetry and must never crash the agent's program.
    """
    subprocess.run(["sculpt", "signal", event, *extra], check=False)  # noqa: S607


def _resolve(cwd: Path, path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else cwd / candidate


def _wait_for_file(target: Path, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not target.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"wait_for_file timed out after {timeout_seconds}s waiting for {target}")
        time.sleep(_POLL_INTERVAL_SECONDS)


def execute_command(
    command: dict,
    cwd: Path,
    on_files_changed: Callable[[], None] | None = None,
    sentinel_dir: Path | None = None,
) -> None:
    """Execute one side-effecting DSL command against ``cwd``.

    ``on_files_changed`` (when given) is called after every leaf operation that
    mutates the workspace, so the runner can emit a ``files-changed`` signal at
    the exact point the diff should refresh — including between the steps of a
    ``multi_step`` that ends by blocking on ``wait_for_file``. Kept free of any
    ``sculpt`` dependency so it can be unit-tested directly.

    ``wait_for_file`` sentinels resolve against ``sentinel_dir`` (the commands
    directory the runner shares with the test) rather than ``cwd``, so a test
    can release a wait without knowing the agent's workspace path; it defaults
    to ``cwd`` when unset. File-mutating ops always resolve against ``cwd``.
    """
    op = command["op"]
    if sentinel_dir is None:
        sentinel_dir = cwd
    if op == "write_file":
        full_path = _resolve(cwd, command["file_path"])
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(command["content"])
        _notify(on_files_changed)
    elif op == "edit_file":
        full_path = _resolve(cwd, command["file_path"])
        content = full_path.read_text()
        old_string = command["old_string"]
        if old_string not in content:
            raise RuntimeError(f"edit_file: old_string not found in {command['file_path']}")
        full_path.write_text(content.replace(old_string, command["new_string"], 1))
        _notify(on_files_changed)
    elif op == "bash":
        subprocess.run(command["command"], shell=True, cwd=cwd, check=False)  # noqa: S602
        _notify(on_files_changed)
    elif op == "sleep":
        time.sleep(float(command.get("seconds", 1)))
    elif op == "wait_for_file":
        timeout_seconds = float(command.get("timeout_seconds", _DEFAULT_WAIT_TIMEOUT_SECONDS))
        _wait_for_file(_resolve(sentinel_dir, command["path"]), timeout_seconds)
    elif op == "multi_step":
        for step in command["steps"]:
            execute_command(step, cwd, on_files_changed, sentinel_dir)
    else:
        raise ValueError(f"unknown fake-terminal-agent command op: {op!r}")


def _notify(on_files_changed: Callable[[], None] | None) -> None:
    if on_files_changed is not None:
        on_files_changed()


def _next_command_file(commands_dir: Path, processed: set[str]) -> Path | None:
    """Return the next unprocessed ``*.json`` command file in name order."""
    for path in sorted(commands_dir.glob("*.json")):
        if path.name not in processed:
            return path
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fake terminal-agent runner.")
    parser.add_argument("--commands-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--banner", default="FAKE-TERMINAL-AGENT-READY")
    args = parser.parse_args(argv)

    commands_dir = Path(args.commands_dir)
    commands_dir.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd()

    # Banner first so the test can wait on it; then report the session id (for
    # resume) and settle to idle so the tab dot starts calm.
    print(args.banner, flush=True)
    _signal("session-id", args.session_id)
    # `_signal` blocks until the `sculpt signal` subprocess exits, i.e. until
    # the session-id POST returned (and was persisted). Printing this marker
    # afterward gives tests a terminal-output gate that proves the session id
    # reached the backend before they tear the instance down — the dot settling
    # to idle alone does NOT guarantee it (the dot can read read/unread for
    # other reasons, racing teardown against session-id persistence).
    print(f"SESSION-REPORTED-{args.session_id}", flush=True)
    _signal("idle")

    processed: set[str] = set()
    while True:
        if (commands_dir / QUIT_SENTINEL_NAME).exists():
            break
        command_file = _next_command_file(commands_dir, processed)
        if command_file is None:
            time.sleep(_POLL_INTERVAL_SECONDS)
            continue
        processed.add(command_file.name)
        _signal("busy")
        try:
            command = json.loads(command_file.read_text())
            execute_command(command, cwd, on_files_changed=lambda: _signal("files-changed"), sentinel_dir=commands_dir)
        finally:
            (command_file.with_suffix(command_file.suffix + DONE_SUFFIX)).write_text("ok")
            _signal("idle")

    print("FAKE-TERMINAL-AGENT-EXITED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
