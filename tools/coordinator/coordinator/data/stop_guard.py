"""Refuse a Stop that would abandon still-running background tasks.

Workers run under ``claude -p``, which exits the moment the turn ends.
A worker that launches a background task and then ends its turn to await
the completion notification is waiting for something that can never
arrive: the process dies, and the launcher's kill sweeps the background
shells away with it, unfinished. This hook turns that dead end into a
correction — it vetoes the Stop, which holds the session open, and tells
the worker to drain its tasks inside the turn it already has.

Usage (as a Stop hook command):
``python3 stop_guard.py <blocks_path> [max_blocks]``. Reads the hook
payload JSON from stdin and, when ``background_tasks`` still holds a
running entry, prints ``{"decision": "block", "reason": ...}`` — the
Stop-hook contract for "keep going". ``blocks_path`` holds the number of
blocks already issued for this attempt; once ``max_blocks`` is spent the
Stop is allowed through, so a task that never finishes ends the attempt
instead of looping forever (the launcher then reads the same
``background_tasks`` and fails the attempt).

Stdlib-only: this file is copied into each attempt directory and run by
whatever ``python3`` is on the worker's PATH. It fails OPEN — every
error path exits 0 with no output, so a broken guard can never wedge a
worker.
"""

import json
import sys

# A worker rarely settles into a proper foreground wait on the first
# refusal — it tends to poll once, stop again, and only then block
# properly — so the budget has to absorb several rounds without ending
# the attempt. It is a backstop against an unfinishable task, not a
# tight leash; the launcher's attempt timeout is the real ceiling.
DEFAULT_MAX_BLOCKS = 12

# Task descriptions are whole shell commands; keep the reason readable.
_DESCRIPTION_CAP = 200


def running_tasks(payload: dict) -> list[dict]:
    tasks = payload.get("background_tasks")
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict) and task.get("status") == "running"]


def describe(task: dict) -> str:
    text = task.get("description") or task.get("command") or "(no description)"
    text = " ".join(str(text).split())
    if len(text) > _DESCRIPTION_CAP:
        text = text[:_DESCRIPTION_CAP] + "..."
    return f"- {task.get('id', '?')}: {text}"


def block_reason(tasks: list[dict], blocks_left: int) -> str:
    listing = "\n".join(describe(task) for task in tasks)
    explanation = " ".join(
        [
            "This session is non-interactive, so ending your turn does not wait for that",
            "work — it ends the session. This hook is holding the session open for you, and",
            f"it will do so {blocks_left} more time(s). After that the session exits, any",
            "unfinished task is killed with it, and the attempt is failed and retried from",
            "scratch. So wait inside this turn: block in the foreground until each task is",
            "genuinely done (a foreground command, or a loop that only returns once the work",
            "has finished), read its output, act on the result, and only then end your turn.",
        ]
    )
    return f"You ended your turn with {len(tasks)} background task(s) still running:\n{listing}\n\n{explanation}"


def spend_block(blocks_path: str, max_blocks: int) -> int:
    """Record one block against this attempt's budget; returns blocks left after it (-1 when spent)."""
    try:
        with open(blocks_path) as f:
            spent = int(f.read().strip() or 0)
    except (OSError, ValueError):
        spent = 0
    if spent >= max_blocks:
        return -1
    with open(blocks_path, "w") as f:
        f.write(str(spent + 1))
    return max_blocks - spent - 1


def main() -> None:
    try:
        blocks_path = sys.argv[1] if len(sys.argv) > 1 else None
        max_blocks = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX_BLOCKS
        payload = json.loads(sys.stdin.read() or "{}")
        tasks = running_tasks(payload) if isinstance(payload, dict) else []
        if not tasks or blocks_path is None:
            sys.exit(0)
        blocks_left = spend_block(blocks_path, max_blocks)
        if blocks_left >= 0:
            json.dump({"decision": "block", "reason": block_reason(tasks, blocks_left)}, sys.stdout)
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
