import os
import stat
from pathlib import Path

import pytest

from coordinator.sculpt_signals import NullSignaler
from coordinator.sculpt_signals import SculptSignaler
from coordinator.sculpt_signals import detect_signaler


def make_fake_sculpt(tmp_path: Path, exit_code: int = 0) -> tuple[Path, Path]:
    """A fake `sculpt` on-disk logging its argv; returns (bin_dir, log_path)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_path = tmp_path / "sculpt_calls.log"
    script = bin_dir / "sculpt"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{log_path}"\nexit {exit_code}\n')
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir, log_path


def use_fake_sculpt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int = 0, agent_id: str | None = "tsk_fake"
) -> Path:
    bin_dir, log_path = make_fake_sculpt(tmp_path, exit_code)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    if agent_id is not None:
        monkeypatch.setenv("SCULPT_AGENT_ID", agent_id)
    return log_path


def test_detect_requires_sculpt_and_agent_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Neither present.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("SCULPT_AGENT_ID", raising=False)
    assert isinstance(detect_signaler(), NullSignaler)
    # sculpt present, no agent id.
    bin_dir, _ = make_fake_sculpt(tmp_path)
    monkeypatch.setenv("PATH", str(bin_dir))
    assert isinstance(detect_signaler(), NullSignaler)
    # Agent id set, no sculpt.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("SCULPT_AGENT_ID", "tsk_fake")
    assert isinstance(detect_signaler(), NullSignaler)
    # Both present.
    monkeypatch.setenv("PATH", str(bin_dir))
    assert isinstance(detect_signaler(), SculptSignaler)


def test_signals_invoke_sculpt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = use_fake_sculpt(tmp_path, monkeypatch)
    signaler = detect_signaler()
    assert isinstance(signaler, SculptSignaler)
    signaler.session_id("run-abc")
    signaler.busy()
    signaler.files_changed()
    signaler.waiting()
    signaler.idle()
    assert log_path.read_text().splitlines() == [
        "signal session-id run-abc",
        "signal busy",
        "signal files-changed",
        "signal waiting",
        "signal idle",
    ]


def test_signal_failure_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_fake_sculpt(tmp_path, monkeypatch, exit_code=1)
    signaler = detect_signaler()
    assert isinstance(signaler, SculptSignaler)
    signaler.busy()
    assert "sculpt signal busy failed" in capsys.readouterr().err


def test_null_signaler_is_inert() -> None:
    signaler = NullSignaler()
    signaler.busy()
    signaler.idle()
    signaler.waiting()
    signaler.files_changed()
    signaler.session_id("run-x")
