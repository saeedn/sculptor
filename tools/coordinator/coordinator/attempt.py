"""Attempt preparation: everything a worker needs on disk before launch.

Each attempt gets its own directory (``attempt_dir`` from
``statedir.py``) containing:

- ``hooks.json`` — the Claude Code settings file: trust/permission
  bypass plus hooks that append every lifecycle event to this attempt's
  ``signals.jsonl``. Hooks are the ONLY way the coordinator observes a
  worker — never screen parsing.
- ``append_signal.py`` — the stdin-to-JSONL helper the hooks invoke,
  copied from package data so attempt dirs are self-contained (they
  survive package upgrades and keep every input on disk for diagnosis).
- ``prompt.txt`` — the one-line bootstrap prompt pointing the worker at
  the task file, process doc, and retry context.
- ``process.md`` — the per-task process document (the manifest's
  ``defaults.process_doc`` override when set, else the built-in copy).
- ``context.md`` — retry context from prior failed attempts, when any.
- ``signals.jsonl`` — appended by the hooks at runtime; one file per
  attempt so signal attribution is trivial.

All paths written into ``hooks.json`` and the prompt are absolute: the
worker's cwd is the repo, not the attempt dir.
"""

import json
import shlex
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from coordinator.dag import Node
from coordinator.statedir import attempt_dir

# Hook events that matter for lifecycle observation (spike-verified on
# Claude Code 2.1.200). Stop is the "turn finished" signal — SessionEnd
# fires with the same reason for clean exits and SIGTERM kills.
_HOOK_EVENTS: tuple[tuple[str, str | None], ...] = (
    ("SessionStart", None),
    ("UserPromptSubmit", None),
    ("Stop", None),
    ("SessionEnd", None),
    ("Notification", None),
    ("PreToolUse", "AskUserQuestion"),
)


@dataclass(frozen=True)
class PreparedAttempt:
    attempt_dir: Path
    hooks_file: Path
    prompt: str
    signals_path: Path
    process_doc: Path
    context_file: Path | None


def _hooks_settings(helper: Path, signals_path: Path) -> dict:
    hooks: dict[str, list[dict]] = {}
    for event, matcher in _HOOK_EVENTS:
        # `|| true` so a failing hook never breaks the worker session.
        command = f"python3 {shlex.quote(str(helper))} {event} {shlex.quote(str(signals_path))} || true"
        entry: dict = {"hooks": [{"type": "command", "command": command}]}
        if matcher is not None:
            entry["matcher"] = matcher
        hooks[event] = [entry]
    return {"skipDangerousModePermissionPrompt": True, "hooks": hooks}


def builtin_data_text(filename: str) -> str:
    return (resources.files("coordinator") / "data" / filename).read_text()


def write_hooks_fragment(directory: Path) -> tuple[Path, Path]:
    """Write hooks.json + the copied signal helper; returns (hooks_file, signals_path)."""
    helper = directory / "append_signal.py"
    helper.write_text(builtin_data_text("append_signal.py"))
    signals_path = directory / "signals.jsonl"
    hooks_file = directory / "hooks.json"
    hooks_file.write_text(json.dumps(_hooks_settings(helper.resolve(), signals_path.resolve()), indent=2) + "\n")
    return hooks_file, signals_path


def prepare_attempt(
    plan_dir: Path,
    node: Node,
    attempt_index: int,
    task_file: Path,
    process_doc_path: Path | None,
    seed_context: str | None,
) -> PreparedAttempt:
    """Create and populate the attempt directory; returns its key paths."""
    directory = attempt_dir(plan_dir, node.node_id, attempt_index)
    directory.mkdir(parents=True, exist_ok=True)

    hooks_file, signals_path = write_hooks_fragment(directory)

    process_doc = directory / "process.md"
    if process_doc_path is not None:
        process_doc.write_text(process_doc_path.read_text())
    else:
        process_doc.write_text(builtin_data_text("implement_task.md"))

    context_file: Path | None = None
    if seed_context is not None:
        context_file = directory / "context.md"
        context_file.write_text(seed_context)

    prompt = (
        f"Read and execute exactly one task: {task_file.resolve()}. "
        f"Follow the process at {process_doc.resolve()}. "
        f"Your retry context, if any, is at {context_file.resolve() if context_file is not None else 'none'}. "
        "Work autonomously; never wait for user input; when the task is complete, stop."
    )
    (directory / "prompt.txt").write_text(prompt + "\n")

    return PreparedAttempt(
        attempt_dir=directory,
        hooks_file=hooks_file,
        prompt=prompt,
        signals_path=signals_path,
        process_doc=process_doc,
        context_file=context_file,
    )
