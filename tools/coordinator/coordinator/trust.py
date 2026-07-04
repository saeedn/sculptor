"""Trust-dialog pre-seeding for interactive workers.

An interactive Claude Code session launched in a fresh cwd hits a
workspace trust dialog that fires ZERO hooks and hangs forever —
invisible to a hooks-only coordinator. The bypass is to merge
``projects["<abs cwd>"] = {"hasTrustDialogAccepted": true,
"projectOnboardingSeenCount": 1}`` into ``~/.claude.json`` BEFORE
launch. Claude Code rewrites that file constantly, so the update is
atomic (temp file in the same directory + ``os.replace``) and never
clobbers unrelated keys. There is no file lock: a write racing Claude's
own rewrite has a small window where one side's update is lost, which
is acceptable — the caller re-seeds before every interactive launch.

Print mode (``claude -p``) skips the dialog by design and does not need
this.
"""

import json
import os
import tempfile
from pathlib import Path


class TrustError(Exception):
    """Raised when ``~/.claude.json`` cannot be safely updated."""


def claude_config_path(home: Path | None = None) -> Path:
    return (home if home is not None else Path.home()) / ".claude.json"


def ensure_trusted(cwd: Path, home: Path | None = None) -> None:
    """Merge the trust entry for ``cwd`` into ``~/.claude.json`` atomically.

    ``home`` overrides the home directory (for tests). Raises
    :class:`TrustError` on an unparseable config — silently replacing it
    would destroy the user's Claude state.
    """
    config_path = claude_config_path(home)
    data: dict = {}
    if config_path.is_file():
        text = config_path.read_text()
        if text.strip():
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise TrustError(f"{config_path} is not valid JSON; refusing to overwrite it: {e}") from e
    projects = data.setdefault("projects", {})
    entry = projects.setdefault(str(cwd.resolve()), {})
    if entry.get("hasTrustDialogAccepted") is True:
        return
    entry["hasTrustDialogAccepted"] = True
    entry.setdefault("projectOnboardingSeenCount", 1)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=config_path.parent, prefix=".claude.json.")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, config_path)
    except BaseException:
        os.unlink(temp_path)
        raise
