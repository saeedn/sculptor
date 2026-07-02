from pathlib import Path
from unittest.mock import patch

import pytest

from sculptor.utils.build import get_sculptor_folder
from sculptor.utils.migration import ensure_sculptor_folder_ready


@pytest.fixture(autouse=True)
def _clear_sculptor_folder_cache():
    get_sculptor_folder.cache_clear()
    yield
    get_sculptor_folder.cache_clear()


def test_fresh_install_creates_internal_and_workspaces(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()


def test_idempotent_and_preserves_existing_data(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    (sculptor_path / "internal").mkdir(parents=True)
    (sculptor_path / "workspaces").mkdir()
    existing = sculptor_path / "internal" / "database.db"
    existing.write_bytes(b"data")

    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    # No error, dirs still present, existing data untouched.
    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()
    assert existing.read_bytes() == b"data"


def test_existing_folder_gets_missing_subdirs(tmp_path: Path) -> None:
    sculptor_path = tmp_path / ".sculptor"
    sculptor_path.mkdir()
    (sculptor_path / "some_existing_file.txt").write_text("data")

    with patch("sculptor.utils.build.get_sculptor_folder", return_value=sculptor_path):
        ensure_sculptor_folder_ready()

    assert (sculptor_path / "internal").is_dir()
    assert (sculptor_path / "workspaces").is_dir()
    assert (sculptor_path / "some_existing_file.txt").is_file()
