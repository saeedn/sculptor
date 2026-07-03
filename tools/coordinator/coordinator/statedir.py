"""Layout helpers for the coordinator's on-disk state.

Everything lives under ``<plan-folder>/_state/`` — next to the plan it
executes, identical inside and outside Sculptor. The directory
self-writes a ``.gitignore`` containing ``*`` so run state never
pollutes the repo.
"""

import re
import secrets
import time
from pathlib import Path

STATE_DIR_NAME = "_state"

_UNSAFE_NODE_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def state_dir(plan_dir: Path) -> Path:
    return plan_dir / STATE_DIR_NAME


def journal_path(plan_dir: Path) -> Path:
    return state_dir(plan_dir) / "journal.jsonl"


def snapshot_path(plan_dir: Path) -> Path:
    return state_dir(plan_dir) / "state.json"


def run_id_path(plan_dir: Path) -> Path:
    return state_dir(plan_dir) / "run_id"


def ensure_state_dir(plan_dir: Path) -> Path:
    directory = state_dir(plan_dir)
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    return directory


def sanitize_node_id(node_id: str) -> str:
    return _UNSAFE_NODE_ID_CHARS.sub("_", node_id)


def attempt_dir(plan_dir: Path, node_id: str, attempt_index: int) -> Path:
    return state_dir(plan_dir) / "attempts" / sanitize_node_id(node_id) / str(attempt_index)


def new_run_id() -> str:
    """A fresh run id, e.g. ``run-20260701-153012-a1b2c3``.

    Stays within ``[A-Za-z0-9._-]{1,128}`` — the backend's terminal
    session-id charset — because the run id doubles as the Sculptor
    session id when the coordinator runs inside a workspace.
    """
    return f"run-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def write_run_id(plan_dir: Path, run_id: str) -> None:
    run_id_path(plan_dir).write_text(run_id + "\n")


def read_run_id(plan_dir: Path) -> str | None:
    path = run_id_path(plan_dir)
    if not path.is_file():
        return None
    content = path.read_text().strip()
    return content or None
