from pathlib import Path
from tempfile import gettempdir

import pytest

from sculptor.config.settings import SculptorSettings
from sculptor.utils.build import get_internal_folder


def test_bind_host_defaults_to_localhost() -> None:
    settings = SculptorSettings()
    assert settings.BIND_HOST == "127.0.0.1"


def test_bind_host_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCULPTOR_BIND_HOST", "0.0.0.0")
    settings = SculptorSettings()
    assert settings.BIND_HOST == "0.0.0.0"


@pytest.mark.parametrize(
    "field_name",
    ["WORKSPACE_SYNC_DIR"],
)
def test_sync_dir_default_is_stable_across_restarts(field_name: str) -> None:
    # SCU-1245: the host-side workspace_sync artifact cache holds the data that
    # repopulates the workspace diff view after a restart. If it lives under the
    # system tempdir, macOS's periodic jobs prune it (every ~3 days, sooner under
    # disk pressure), which empties that UI on restart even though the source
    # artifacts are intact in the workspace's own stable dirs. The default must
    # live somewhere that survives across restarts and is not OS-managed; we keep
    # it under internal/artifacts/ so the cache is easy to inspect and wipe.
    settings = SculptorSettings()
    sync_dir = Path(getattr(settings, field_name)).resolve()
    tempdir = Path(gettempdir()).resolve()
    artifacts_root = (get_internal_folder() / "artifacts").resolve()
    assert tempdir not in sync_dir.parents and sync_dir != tempdir, (
        f"{field_name} ({sync_dir}) must not be under the system tempdir ({tempdir}); the OS prunes it and cached UI state vanishes after restart."
    )
    assert artifacts_root in sync_dir.parents, (
        f"{field_name} ({sync_dir}) should live under {artifacts_root} so caches survive restarts and are co-located."
    )
