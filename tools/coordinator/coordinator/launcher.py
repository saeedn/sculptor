"""Worker launcher: spawn, observe via signals.jsonl, kill, reap.

One fresh worker process per attempt — plain processes the coordinator
spawns and reaps itself, never Sculptor agents. Print-mode workers run
on pipes and exit by themselves; interactive-mode workers run on a
drained PTY (an undrained worker wedges at 0% CPU before processing
its prompt).

Lifecycle is observed ONLY through the hook events the attempt's
``hooks.json`` appends to ``signals.jsonl`` plus process state — never
screen parsing. ``pty_output.raw`` is captured purely for human
diagnosis and is never parsed for decisions.

Decision rules (both modes):

- ``Stop`` observed -> ``completed`` (the turn ended; gates decide
  success). ``SessionEnd`` is never used for verdicts — it fires with
  the same reason on clean exits and kills.
- A waiting signal (``PreToolUse`` with ``tool_name`` ==
  ``AskUserQuestion``, or ``Notification`` with ``notification_type``
  == ``idle_prompt``) -> ``waiting``; workers must never block on user
  input.
- Process exit without a Stop -> ``exited-without-stop``.
- Deadline hit -> ``timeout``.

Trust-dialog seeding (``trust.ensure_trusted``) is the CALLER's job for
interactive registrations — launching stays side-effect-free w.r.t.
HOME.
"""

import fcntl
import json
import os
import signal
import struct
import subprocess
import termios
import threading
import time
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path

import psutil

from coordinator.attempt import PreparedAttempt
from coordinator.registrations import WorkerRegistration
from coordinator.registrations import render
from coordinator.scheduler import AttemptResult
from coordinator.scheduler import AttemptStatus

_PTY_COLUMNS = 200
_PTY_ROWS = 50

SignalCallback = Callable[[dict], None]


def scrub_env(base: Mapping[str, str]) -> dict[str, str]:
    """Drop Sculptor/Claude ambient env from the child environment.

    Inherited ``CLAUDE*`` vars silently suppress transcript persistence
    (a child claude thinks it is a nested session); inherited
    ``SCULPT_*`` would signal the wrong Sculptor agent. A coordinator
    started from inside any claude session must behave identically to
    one started from a plain shell.
    """
    return {
        key: value
        for key, value in base.items()
        if not key.startswith(("SCULPT_", "SCULPTOR_", "CLAUDE")) and key != "AI_AGENT"
    }


class SignalReader:
    """Incremental reader of an attempt's signals.jsonl.

    Remembers the file offset and only consumes newline-terminated
    lines, so a partially-written final line is picked up on the next
    poll. Extracts session_id / transcript_path from the first payload
    carrying them and tracks the latest last_assistant_message.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._offset = 0
        self.events: list[dict] = []
        self.session_id: str | None = None
        self.transcript_path: str | None = None
        self.last_assistant_message: str | None = None

    def poll(self) -> list[dict]:
        if not self.path.is_file():
            return []
        with open(self.path, "rb") as f:
            f.seek(self._offset)
            chunk = f.read()
        complete, separator, _partial = chunk.rpartition(b"\n")
        if not separator:
            return []
        self._offset += len(complete) + 1
        new_events: list[dict] = []
        for raw_line in complete.split(b"\n"):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except ValueError:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                if self.session_id is None and payload.get("session_id"):
                    self.session_id = payload["session_id"]
                if self.transcript_path is None and payload.get("transcript_path"):
                    self.transcript_path = payload["transcript_path"]
                if payload.get("last_assistant_message"):
                    self.last_assistant_message = payload["last_assistant_message"]
            self.events.append(event)
            new_events.append(event)
        return new_events


def _is_stop(event: dict) -> bool:
    return event.get("event") == "Stop"


def _is_waiting(event: dict) -> bool:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return False
    if event.get("event") == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        return True
    if event.get("event") == "Notification" and payload.get("notification_type") == "idle_prompt":
        return True
    return False


def _set_pty_window_size(fd: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", _PTY_ROWS, _PTY_COLUMNS, 0, 0))


def _drain_pty(master_fd: int, output_path: Path, byte_counter: list[int]) -> None:
    with open(output_path, "wb") as out:
        while True:
            try:
                data = os.read(master_fd, 65536)
            except OSError:
                # EIO means the child side closed — PTY EOF on macOS/Linux.
                break
            if not data:
                break
            out.write(data)
            out.flush()
            byte_counter[0] += len(data)


def _terminate_child(proc: subprocess.Popen, kill_grace_seconds: float) -> None:
    """SIGTERM the child's process group, escalating to SIGKILL.

    Wedged PTY workers survive SIGTERM — the escalation is mandatory.
    Always reaps the child (no zombies).
    """
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        proc.wait()
        return
    try:
        proc.wait(timeout=kill_grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def kill_process_group(pid: int, kill_grace_seconds: float = 10.0) -> None:
    """SIGTERM -> SIGKILL a process group we do not own as a child."""
    try:
        process = psutil.Process(pid)
        os.killpg(pid, signal.SIGTERM)
        try:
            process.wait(timeout=kill_grace_seconds)
        except psutil.TimeoutExpired:
            os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, psutil.NoSuchProcess):
        pass


def reap_recorded_pid(pid: int, our_create_time: float | None = None, kill_grace_seconds: float = 10.0) -> None:
    """Resume-time orphan reaper for a PID recorded in the journal.

    Guard order matters — a recycled pid must never be signalled:
    1. the pid exists;
    2. it is a session leader (workers are spawned with
       start_new_session=True; a recycled pid is almost never one);
    3. it predates this coordinator process (a worker from a previous
       run cannot be younger than the current coordinator).
    ``our_create_time`` overrides the reference time for tests.
    """
    try:
        if not psutil.pid_exists(pid):
            return
        if os.getpgid(pid) != pid:
            return
        process = psutil.Process(pid)
        reference = our_create_time if our_create_time is not None else psutil.Process().create_time()
        if process.create_time() >= reference:
            return
        os.killpg(pid, signal.SIGTERM)
        try:
            process.wait(timeout=kill_grace_seconds)
        except psutil.TimeoutExpired:
            os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, psutil.NoSuchProcess):
        pass
    except PermissionError:
        # macOS raises this for foreign processes — treat as "not ours".
        pass


def launch_attempt(
    registration: WorkerRegistration,
    prepared: PreparedAttempt,
    cwd: Path,
    *,
    timeout_seconds: float = 1800.0,
    poll_interval: float = 0.5,
    kill_grace_seconds: float = 10.0,
    on_signal: SignalCallback | None = None,
) -> AttemptResult:
    """Run one prepared attempt to a verdict; always reaps the process."""
    argv, registration_env = render(
        registration,
        prompt=prepared.prompt,
        settings_file=str(prepared.hooks_file.resolve()),
        attempt_dir=str(prepared.attempt_dir.resolve()),
        cwd=str(cwd.resolve()),
    )
    env = scrub_env(os.environ)
    env.update(registration_env)
    reader = SignalReader(prepared.signals_path)
    byte_counter = [0]
    drain_thread: threading.Thread | None = None
    master_fd: int | None = None

    if registration.mode == "print":
        stdout_file = open(prepared.attempt_dir / "stdout.log", "wb")
        stderr_file = open(prepared.attempt_dir / "stderr.log", "wb")
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=str(cwd),
                env=env,
                start_new_session=True,
            )
        finally:
            stdout_file.close()
            stderr_file.close()
    else:
        master_fd, slave_fd = os.openpty()
        _set_pty_window_size(slave_fd)
        proc = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(cwd),
            env=env,
            start_new_session=True,
        )
        # Close the slave in the parent immediately, or the drain thread
        # never sees EOF when the child exits.
        os.close(slave_fd)
        drain_thread = threading.Thread(
            target=_drain_pty,
            args=(master_fd, prepared.attempt_dir / "pty_output.raw", byte_counter),
            daemon=True,
        )
        drain_thread.start()

    status: AttemptStatus | None = None
    deadline = time.monotonic() + timeout_seconds

    def consume(events: list[dict]) -> None:
        nonlocal status
        for event in events:
            if on_signal is not None:
                on_signal(event)
            if _is_stop(event):
                status = "completed"
            elif _is_waiting(event) and status is None:
                status = "waiting"

    while status is None:
        consume(reader.poll())
        if status is not None:
            break
        if proc.poll() is not None:
            # Final sweep: signals may have landed right at exit.
            consume(reader.poll())
            if status is None:
                status = "exited-without-stop"
            break
        if time.monotonic() >= deadline:
            status = "timeout"
            break
        time.sleep(poll_interval)

    if status == "completed" and registration.mode == "print" and proc.poll() is None:
        # Print-mode workers exit by themselves shortly after Stop; give
        # them the grace window before forcing the issue.
        try:
            proc.wait(timeout=kill_grace_seconds)
        except subprocess.TimeoutExpired:
            pass
    _terminate_child(proc, kill_grace_seconds)

    if drain_thread is not None:
        drain_thread.join(timeout=5.0)
    if master_fd is not None:
        os.close(master_fd)
    consume(reader.poll())

    ok = status == "completed"
    return AttemptResult(
        ok=ok,
        status=status,
        error=None if ok else f"attempt {status}",
        pid=proc.pid,
        session_id=reader.session_id,
        transcript_path=reader.transcript_path,
        last_assistant_message=reader.last_assistant_message,
        signals=tuple(event.get("event", "unknown") for event in reader.events),
        exit_code=proc.returncode,
        bytes_drained=byte_counter[0] if registration.mode == "interactive" else None,
    )
