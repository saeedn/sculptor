import shutil
from pathlib import Path

from loguru import logger

from sculptor.utils import build as build_utils

# Bumped to "2" for the slim release, which removed schema a pre-slim DB still
# references, so opening one would crash on deserialization.
# An older on-disk marker triggers the fresh-start guard below, which moves the
# pre-slim data aside before the app ever opens the DB.
_FORMAT_VERSION = "2"
_FORMAT_VERSION_FILENAME = ".format_version"
_PRE_SLIM_BACKUP_DIRNAME = "pre-slim-backup"


def _bootstrap_sculptor_folder(sculptor_path: Path) -> None:
    """Ensure the sculptor folder has the expected structure and version marker."""
    logger.info("Bootstrapping Sculptor folder at {}", sculptor_path)
    (sculptor_path / "internal").mkdir(parents=True, exist_ok=True)
    (sculptor_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (sculptor_path / _FORMAT_VERSION_FILENAME).write_text(f"{_FORMAT_VERSION}\n")


def _move_aside_pre_slim_data(sculptor_path: Path) -> None:
    """Move a pre-slim data dir aside so the slimmed app never opens its DB.

    The slim release hard-removed enum values (workspace strategies, agent
    types) that a pre-slim DB still references, so opening such a DB would crash
    during deserialization. Rather than destroy the user's data, move the
    pre-slim DB and workspace checkouts into a backup directory inside the
    sculptor folder, then re-bootstrap a fresh data dir.
    """
    backup_root = sculptor_path / _PRE_SLIM_BACKUP_DIRNAME
    # If a previous failed upgrade already created a backup, don't clobber it —
    # move into a uniquely-suffixed sibling instead.
    if backup_root.exists():
        suffix = 1
        while (sculptor_path / f"{_PRE_SLIM_BACKUP_DIRNAME}-{suffix}").exists():
            suffix += 1
        backup_root = sculptor_path / f"{_PRE_SLIM_BACKUP_DIRNAME}-{suffix}"
    backup_root.mkdir(parents=True, exist_ok=True)
    logger.warning(
        "Pre-slim Sculptor data detected at {}; moving it aside to {} and starting fresh",
        sculptor_path,
        backup_root,
    )
    for name in ("internal", "workspaces"):
        source = sculptor_path / name
        if source.exists():
            shutil.move(str(source), str(backup_root / name))


def ensure_sculptor_folder_ready() -> None:
    """Ensure the Sculptor data folder is in the expected format.

    Behavior by on-disk ``.format_version`` marker:

    * Marker present and equal to the current version: nothing to do.
    * Marker missing: fresh-install (or marker-less dev/test) bootstrap.
    * Marker present but older than the current version: clean break — move the
      pre-slim data aside and re-bootstrap a fresh data dir before the app opens
      the DB. This satisfies the "must not crash on legacy rows" requirement by
      never deserializing a pre-slim DB.
    """
    sculptor_path = build_utils.get_sculptor_folder()
    marker_path = sculptor_path / _FORMAT_VERSION_FILENAME

    if not marker_path.is_file():
        _bootstrap_sculptor_folder(sculptor_path)
        return

    on_disk_version = marker_path.read_text().strip()
    if on_disk_version == _FORMAT_VERSION:
        return

    # Older marker (or otherwise mismatched): discard/replace the pre-slim DB.
    _move_aside_pre_slim_data(sculptor_path)
    marker_path.unlink(missing_ok=True)
    _bootstrap_sculptor_folder(sculptor_path)
