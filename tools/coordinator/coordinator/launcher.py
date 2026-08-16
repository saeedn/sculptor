"""Worker launcher: spawn, observe via signals.jsonl, kill, reap.

One fresh worker process per attempt — plain processes the coordinator
spawns and reaps itself, never Sculptor agents. Workers run headless
(``claude -p``) on pipes and exit by themselves once their turn ends.

Lifecycle is observed ONLY through the hook events the attempt's
``hooks.json`` appends to ``signals.jsonl`` plus process state — never
screen parsing.

Decision rules:

- A clean ``Stop`` -> ``completed`` (the turn ended; gates decide
  success). ``SessionEnd`` is never used for verdicts — it fires with
  the same reason on clean exits and kills.
- A ``Stop`` carrying still-running ``background_tasks`` is NOT a
  finished turn: the session is about to exit and take that work with
  it. The attempt's Stop guard hook pushes the worker back to drain it,
  so the launcher keeps waiting; if the worker exits anyway the verdict
  is ``stopped-with-pending-background``.
- A waiting signal (``PreToolUse`` with ``tool_name`` ==
  ``AskUserQuestion``, or ``Notification`` with ``notification_type``
  == ``idle_prompt``) -> ``waiting``; workers must never block on user
  input.
- Process exit without a Stop -> ``exited-without-stop``.
- Deadline hit -> ``timeout``.
"""

import os
import signal
import subprocess
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
from coordinator.signals import SignalReader
from coordinator.signals import describe_background_tasks
from coordinator.signals import is_stop
from coordinator.signals import is_waiting
from coordinator.signals import pending_background_tasks

# How long one attempt may run before the launcher kills it. Generous by
# design: a task whose verification runs a real end-to-end suite can
# legitimately spend well over an hour, and a timeout kill lands
# mid-tool-call, discarding the work with no commit. Override per plan
# or per task (``attempt_timeout_minutes``) or per run (``--timeout-minutes``).
DEFAULT_ATTEMPT_TIMEOUT_SECONDS = 120 * 60.0

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


def _terminate_child(proc: subprocess.Popen, kill_grace_seconds: float) -> None:
    """SIGTERM the child's process group, escalating to SIGKILL.

    A worker can ignore or outlive SIGTERM — the escalation is mandatory.
    Always reaps the child (no zombies).
    """
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        # ProcessLookupError: the group is gone. PermissionError: macOS
        # raises EPERM when the child exited between poll() and killpg
        # (a zombie group). Either way there is nothing left to signal.
        proc.wait()
        return
    try:
        proc.wait(timeout=kill_grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
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
    timeout_seconds: float = DEFAULT_ATTEMPT_TIMEOUT_SECONDS,
    poll_interval: float = 0.5,
    kill_grace_seconds: float = 10.0,
    on_signal: SignalCallback | None = None,
    on_spawn: Callable[[int], None] | None = None,
    should_abort: Callable[[], bool] | None = None,
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

    status: AttemptStatus | None = None
    pending_background: list[dict] = []
    deadline = time.monotonic() + timeout_seconds

    def consume(events: list[dict]) -> None:
        nonlocal status, pending_background
        for event in events:
            if on_signal is not None:
                on_signal(event)
            if is_stop(event):
                running = pending_background_tasks(event)
                if running:
                    # The turn ended on work that is still in flight. The
                    # Stop guard hook is pushing the worker back to drain
                    # it, so keep waiting — only a Stop with nothing left
                    # running means this attempt is finished.
                    pending_background = running
                    continue
                pending_background = []
                # A Stop may override "waiting" (the turn finished after all)
                # but never a kill/timeout verdict already handed down.
                if status in (None, "waiting"):
                    status = "completed"
            elif is_waiting(event) and status is None:
                status = "waiting"

    try:
        if on_spawn is not None:
            on_spawn(proc.pid)

        while status is None:
            consume(reader.poll())
            if status is not None:
                break
            if proc.poll() is not None:
                # Final sweep: signals may have landed right at exit.
                consume(reader.poll())
                if status is None:
                    # A worker that stopped on running background tasks and
                    # then exited spent its guard budget without draining
                    # them; name that rather than the generic exit.
                    status = "stopped-with-pending-background" if pending_background else "exited-without-stop"
                break
            if time.monotonic() >= deadline:
                status = "timeout"
                break
            if should_abort is not None and should_abort():
                status = "killed"
                break
            time.sleep(poll_interval)

        if status == "completed" and proc.poll() is None:
            # Workers exit by themselves shortly after Stop; give them the
            # grace window before forcing the issue.
            try:
                proc.wait(timeout=kill_grace_seconds)
            except subprocess.TimeoutExpired:
                pass
    finally:
        # Cleanup must run even when a callback raises — the worker
        # process must never outlive the call.
        _terminate_child(proc, kill_grace_seconds)
    consume(reader.poll())

    is_ok = status == "completed"
    error = None if is_ok else f"attempt {status}"
    if status == "stopped-with-pending-background":
        error = f"{error}: {describe_background_tasks(pending_background)}"
    return AttemptResult(
        is_ok=is_ok,
        status=status,
        error=error,
        pid=proc.pid,
        session_id=reader.session_id,
        transcript_path=reader.transcript_path,
        last_assistant_message=reader.last_assistant_message,
        signals=tuple(event.get("event", "unknown") for event in reader.events),
        exit_code=proc.returncode,
    )
