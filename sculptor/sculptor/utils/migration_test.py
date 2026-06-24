from pathlib import Path
from unittest.mock import patch

import pytest

from sculptor.utils.build import get_sculptor_folder
from sculptor.utils.migration import _FORMAT_VERSION
from sculptor.utils.migration import _PRE_SLIM_BACKUP_DIRNAME
from sculptor.utils.migration import ensure_sculptor_folder_ready


@pytest.fixture(autouse=True)
def _clear_sculptor_folder_cache():
    get_sculptor_folder.cache_clear()
    yield
    get_sculptor_folder.cache_clear()


def test_fresh_install_creates_internal_workspaces_and_format_version(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()
    assert (sculptor_path / ".format_version").is_file()
    assert (sculptor_path / ".format_version").read_text().strip() == _FORMAT_VERSION


def test_normal_startup_returns_without_side_effects(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    sculptor_path.mkdir()
    (sculptor_path / ".format_version").write_text(f"{_FORMAT_VERSION}\n")

    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    # Should not have created internal/ or workspaces/
    assert not (sculptor_path / "internal").exists()
    assert not (sculptor_path / "workspaces").exists()


def test_existing_folder_without_format_version_bootstraps(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    sculptor_path.mkdir()
    # Folder exists but no .format_version — should bootstrap, not error
    (sculptor_path / "some_existing_file.txt").write_text("data")

    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()
    assert (sculptor_path / ".format_version").is_file()
    assert (sculptor_path / ".format_version").read_text().strip() == _FORMAT_VERSION
    # Existing file should still be there
    assert (sculptor_path / "some_existing_file.txt").is_file()


def test_pre_slim_db_is_moved_aside_and_fresh_start(tmp_path: Path) -> None:
    """A pre-slim data dir (older marker + a DB) is discarded before open.

    The slim release removed enum values that a pre-slim DB still references, so
    the guard must move the pre-slim DB aside and re-bootstrap a fresh data dir
    rather than letting the app open the old DB and crash on deserialization. A
    dummy DB file is sufficient — the guard runs before any deserialization.
    """
    sculptor_path = tmp_path / ".sculptor"
    internal = sculptor_path / "internal"
    internal.mkdir(parents=True)
    workspaces = sculptor_path / "workspaces"
    workspaces.mkdir()
    # Seed a pre-slim layout: an older marker, a (dummy) DB, and a workspace dir.
    (sculptor_path / ".format_version").write_text("1\n")
    db_path = internal / "database.db"
    db_path.write_bytes(b"pre-slim sqlite bytes that must never be opened")
    (workspaces / "some-workspace").mkdir()

    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        # Must not raise — the guard runs before any deserialization.
        ensure_sculptor_folder_ready()

    # A fresh data dir was bootstrapped with the new marker.
    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()
    assert (sculptor_path / ".format_version").read_text().strip() == _FORMAT_VERSION

    # The pre-slim DB was moved aside (not destroyed) and is NOT in the fresh dir.
    assert not (sculptor_path / "internal" / "database.db").exists()
    backup = sculptor_path / _PRE_SLIM_BACKUP_DIRNAME
    assert (backup / "internal" / "database.db").is_file()
    assert (backup / "internal" / "database.db").read_bytes().startswith(b"pre-slim")
    assert (backup / "workspaces" / "some-workspace").is_dir()
