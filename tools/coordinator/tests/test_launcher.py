import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import psutil
import pytest

from coordinator.attempt import prepare_attempt
from coordinator.dag import Node
from coordinator.launcher import SignalReader
from coordinator.launcher import launch_attempt
from coordinator.launcher import reap_recorded_pid
from coordinator.launcher import scrub_env
from coordinator.signals import read_completed_signals
from tests.fakes import ASK_QUESTION_THEN_SLEEP
from tests.fakes import ECHO_ENV
from tests.fakes import EXIT_WITHOUT_STOP
from tests.fakes import IGNORE_SIGTERM
from tests.fakes import SLEEP_FOREVER
from tests.fakes import STOP_ON_SIGTERM
from tests.fakes import STOP_THEN_SLEEP
from tests.fakes import make_registration


def prepare(tmp_path: Path):
    task_file = tmp_path / "task.md"
    task_file.write_text("# Task\n")
    node = Node(node_id="1.1", kind="task", deps=frozenset())
    return prepare_attempt(tmp_path, node, 0, task_file, None, None)


def launch(tmp_path: Path, script_body: str, mode: Literal["print", "interactive"], env: dict | None = None, **kwargs):
    script = tmp_path / "fake_worker.py"
    script.write_text(script_body)
    prepared = prepare(tmp_path)
    registration = make_registration(script, mode, env)
    kwargs.setdefault("timeout_seconds", 15.0)
    kwargs.setdefault("poll_interval", 0.05)
    kwargs.setdefault("kill_grace_seconds", 1.0)
    return prepared, launch_attempt(registration, prepared, tmp_path, **kwargs)


def assert_process_gone(pid: int) -> None:
    assert not psutil.pid_exists(pid)


@pytest.mark.parametrize("mode", ["print", "interactive"])
def test_stop_completes_and_kills(tmp_path: Path, mode: Literal["print", "interactive"]) -> None:
    prepared, result = launch(tmp_path, STOP_THEN_SLEEP, mode)
    assert result.status == "completed"
    assert result.is_ok
    assert result.session_id == "fake-sess"
    assert result.transcript_path == "/tmp/fake-transcript.jsonl"
    assert result.last_assistant_message == "SUCCESS: did the thing"
    assert "Stop" in result.signals
    assert result.pid is not None
    assert_process_gone(result.pid)
    if mode == "interactive":
        pty_output = (prepared.attempt_dir / "pty_output.raw").read_bytes()
        assert b"fake worker output" in pty_output
        assert result.bytes_drained is not None and result.bytes_drained > 0
    else:
        assert b"fake worker output" in (prepared.attempt_dir / "stdout.log").read_bytes()


@pytest.mark.parametrize("mode", ["print", "interactive"])
def test_exit_without_stop_fails(tmp_path: Path, mode: Literal["print", "interactive"]) -> None:
    _, result = launch(tmp_path, EXIT_WITHOUT_STOP, mode)
    assert result.status == "exited-without-stop"
    assert not result.is_ok
    assert result.session_id == "fake-sess"


@pytest.mark.parametrize("mode", ["print", "interactive"])
def test_waiting_signal_fails_attempt(tmp_path: Path, mode: Literal["print", "interactive"]) -> None:
    _, result = launch(tmp_path, ASK_QUESTION_THEN_SLEEP, mode)
    assert result.status == "waiting"
    assert not result.is_ok
    assert result.pid is not None
    assert_process_gone(result.pid)


def test_stop_after_abort_does_not_flip_the_verdict(tmp_path: Path) -> None:
    script = tmp_path / "fake_worker.py"
    script.write_text(STOP_ON_SIGTERM)
    prepared = prepare(tmp_path)
    registration = make_registration(script, "print", None)

    def should_abort() -> bool:
        # Abort once the worker is up (its SIGTERM handler is installed
        # before it emits SessionStart), so the Stop it emits on TERM
        # reliably lands after the kill decision.
        return prepared.signals_path.is_file() and "SessionStart" in prepared.signals_path.read_text()

    result = launch_attempt(
        registration,
        prepared,
        tmp_path,
        timeout_seconds=15.0,
        poll_interval=0.05,
        kill_grace_seconds=2.0,
        should_abort=should_abort,
    )
    assert result.status == "killed"
    assert not result.is_ok
    # The late Stop was still recorded — it just doesn't change the verdict.
    assert "Stop" in result.signals


def test_worker_is_reaped_when_a_callback_raises(tmp_path: Path) -> None:
    script = tmp_path / "fake_worker.py"
    script.write_text(SLEEP_FOREVER)
    prepared = prepare(tmp_path)
    registration = make_registration(script, "print", None)
    seen_pid: list[int] = []

    def on_spawn(pid: int) -> None:
        seen_pid.append(pid)
        raise RuntimeError("journal write failed")

    with pytest.raises(RuntimeError):
        launch_attempt(
            registration,
            prepared,
            tmp_path,
            timeout_seconds=15.0,
            poll_interval=0.05,
            kill_grace_seconds=1.0,
            on_spawn=on_spawn,
        )
    assert seen_pid
    assert_process_gone(seen_pid[0])


def test_sigterm_immune_worker_gets_sigkilled(tmp_path: Path) -> None:
    _, result = launch(tmp_path, IGNORE_SIGTERM, "print", kill_grace_seconds=0.5)
    assert result.status == "completed"
    assert result.pid is not None
    assert_process_gone(result.pid)
    # SIGKILL shows up as -9.
    assert result.exit_code == -9


@pytest.mark.parametrize("mode", ["print", "interactive"])
def test_timeout(tmp_path: Path, mode: Literal["print", "interactive"]) -> None:
    _, result = launch(tmp_path, SLEEP_FOREVER, mode, timeout_seconds=0.5)
    assert result.status == "timeout"
    assert not result.is_ok
    assert result.pid is not None
    assert_process_gone(result.pid)


def test_env_scrubbed_and_registration_env_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCULPT_API_PORT", "1234")
    monkeypatch.setenv("SCULPTOR_FOLDER", "/x")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("AI_AGENT", "yes")
    _, result = launch(tmp_path, ECHO_ENV, "print", env={"EXTRA_VAR": "from-registration"})
    assert result.status == "completed"
    signals_file = tmp_path / "_state" / "attempts" / "1.1" / "0" / "signals.jsonl"
    events = [json.loads(line) for line in signals_file.read_text().splitlines()]
    child_env = next(e["payload"]["env"] for e in events if e["event"] == "Stop")
    assert child_env["SCULPT_API_PORT"] is None
    assert child_env["SCULPTOR_FOLDER"] is None
    assert child_env["CLAUDECODE"] is None
    assert child_env["CLAUDE_CODE_SESSION_ID"] is None
    assert child_env["AI_AGENT"] is None
    assert child_env["EXTRA_VAR"] == "from-registration"


def test_on_signal_callback_receives_events(tmp_path: Path) -> None:
    observed: list[str] = []
    _, result = launch(tmp_path, STOP_THEN_SLEEP, "print", on_signal=lambda e: observed.append(e["event"]))
    assert result.status == "completed"
    assert "SessionStart" in observed
    assert "Stop" in observed


def test_scrub_env() -> None:
    base = {
        "PATH": "/usr/bin",
        "HOME": "/home/u",
        "SCULPT_API_PORT": "1",
        "SCULPT_WORKSPACE_ID": "w",
        "SCULPTOR_FOLDER": "/s",
        "SCULPTOR_API_PORT": "2",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "x",
        "CLAUDE_CODE_CHILD_SESSION": "1",
        "CLAUDE_CONFIG_DIR": "/c",
        "AI_AGENT": "yes",
        "AI_AGENT_KIND": "keep-me",
    }
    scrubbed = scrub_env(base)
    assert scrubbed == {"PATH": "/usr/bin", "HOME": "/home/u", "AI_AGENT_KIND": "keep-me"}


def test_signal_reader_tolerates_partial_lines(tmp_path: Path) -> None:
    path = tmp_path / "signals.jsonl"
    reader = SignalReader(path)
    assert reader.poll() == []
    with open(path, "a") as f:
        f.write('{"event": "SessionStart", "ts": 1.0, "payload": {"session_id": "s"}}\n')
        f.write('{"event": "Stop", "ts": 2.0, "pay')
    events = reader.poll()
    assert [e["event"] for e in events] == ["SessionStart"]
    assert reader.session_id == "s"
    with open(path, "a") as f:
        f.write('load": null}\n')
    events = reader.poll()
    assert [e["event"] for e in events] == ["Stop"]


def spawn_session_leader(tmp_path: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=tmp_path,
        start_new_session=True,
    )


def test_reap_recorded_pid_kills_predating_session_leader(tmp_path: Path) -> None:
    proc = spawn_session_leader(tmp_path)
    try:
        # Pretend the coordinator started later than the orphan.
        reap_recorded_pid(proc.pid, our_create_time=time.time() + 3600, kill_grace_seconds=2.0)
        # psutil reaps the child inside reap_recorded_pid; only its
        # disappearance is observable here.
        assert not psutil.pid_exists(proc.pid)
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_reap_recorded_pid_refuses_younger_process(tmp_path: Path) -> None:
    proc = spawn_session_leader(tmp_path)
    try:
        # A worker recorded by a previous run cannot be younger than the
        # coordinator; a younger pid means recycling.
        reap_recorded_pid(proc.pid, our_create_time=psutil.Process(proc.pid).create_time() - 3600)
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_reap_recorded_pid_refuses_non_session_leader() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        reap_recorded_pid(proc.pid, our_create_time=time.time() + 3600)
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()


def test_reap_recorded_pid_missing_pid_is_noop() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    reap_recorded_pid(proc.pid, our_create_time=time.time() + 3600)


def test_read_completed_signals(tmp_path: Path) -> None:
    path = tmp_path / "signals.jsonl"
    assert read_completed_signals(path) is None
    path.write_text(json.dumps({"event": "SessionStart", "payload": {"session_id": "s1"}}) + "\n")
    assert read_completed_signals(path) is None
    with open(path, "a") as f:
        f.write(
            json.dumps({"event": "Stop", "payload": {"session_id": "s1", "last_assistant_message": "done"}}) + "\n"
        )
    reader = read_completed_signals(path)
    assert reader is not None
    assert reader.session_id == "s1"
    assert reader.last_assistant_message == "done"
