import json
from pathlib import Path

import pytest

from coordinator.trust import TrustError
from coordinator.trust import claude_config_path
from coordinator.trust import ensure_trusted


def read_config(home: Path) -> dict:
    return json.loads((home / ".claude.json").read_text())


def test_creates_config_when_missing(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    ensure_trusted(cwd, home=tmp_path)
    config = read_config(tmp_path)
    entry = config["projects"][str(cwd.resolve())]
    assert entry["hasTrustDialogAccepted"] is True
    assert entry["projectOnboardingSeenCount"] == 1


def test_preserves_unrelated_keys(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    existing = {
        "oauthAccount": {"email": "user@example.com"},
        "numStartups": 42,
        "projects": {"/other/repo": {"hasTrustDialogAccepted": True, "history": ["x"]}},
    }
    claude_config_path(tmp_path).write_text(json.dumps(existing))
    ensure_trusted(cwd, home=tmp_path)
    config = read_config(tmp_path)
    assert config["oauthAccount"] == {"email": "user@example.com"}
    assert config["numStartups"] == 42
    assert config["projects"]["/other/repo"] == {"hasTrustDialogAccepted": True, "history": ["x"]}
    assert config["projects"][str(cwd.resolve())]["hasTrustDialogAccepted"] is True


def test_preserves_existing_project_entry_keys(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    existing = {"projects": {str(cwd.resolve()): {"history": ["old"], "projectOnboardingSeenCount": 7}}}
    claude_config_path(tmp_path).write_text(json.dumps(existing))
    ensure_trusted(cwd, home=tmp_path)
    entry = read_config(tmp_path)["projects"][str(cwd.resolve())]
    assert entry["history"] == ["old"]
    assert entry["projectOnboardingSeenCount"] == 7
    assert entry["hasTrustDialogAccepted"] is True


def test_idempotent(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    ensure_trusted(cwd, home=tmp_path)
    first = read_config(tmp_path)
    ensure_trusted(cwd, home=tmp_path)
    assert read_config(tmp_path) == first


def test_no_temp_files_left_behind(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    ensure_trusted(cwd, home=tmp_path)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".claude.json.")]
    assert leftovers == []


def test_unparseable_config_refused(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    cwd.mkdir()
    claude_config_path(tmp_path).write_text("{corrupt json")
    with pytest.raises(TrustError):
        ensure_trusted(cwd, home=tmp_path)
    # The corrupt file is left untouched rather than clobbered.
    assert claude_config_path(tmp_path).read_text() == "{corrupt json"
