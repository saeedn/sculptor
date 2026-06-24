"""Test that stopping a terminal agent kills foreground subprocesses it spawned.

When the user stops a terminal agent (deleting it tears down its PTY), any
subprocess the agent spawned in the foreground (e.g. a long-running command in
its shell) must be terminated, not left running as an orphan. Closing the PTY
primary fd delivers SIGHUP to the shell's foreground process group, so the whole
descendant tree is reaped — the process-group teardown SCU-211 guards.

The fake terminal agent's ``bash`` DSL runs a real shell child in the agent's
cwd, so the spawned subprocess is a real OS process in that foreground group —
ideal for this test.

See SCU-211 (kill foreground processes on stop).
"""

import os
import signal
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _read_pid_file(pid_path: Path, page: Page, timeout: float = 15.0) -> int:
    """Wait for the PID file to appear and return the PID.

    Polls via ``page.wait_for_timeout`` (rather than ``time.sleep``) since the
    integration-test time.sleep ratchet reserves the latter for OS-process
    state polling.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid_path.exists():
            text = pid_path.read_text().strip()
            if text:
                return int(text)
        page.wait_for_timeout(100)
    raise FileNotFoundError(f"PID file {pid_path} was not created within {timeout}s")


def _is_process_alive(pid: int) -> bool:
    """Check whether a process is still running (signal 0 probe)."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_process(pid: int) -> None:
    """Best-effort kill of a leaked process."""
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


@user_story("to have foreground subprocesses killed when I stop the agent")
def test_stop_kills_foreground_subprocess(sculptor_instance_: SculptorInstance) -> None:
    """Stopping the terminal agent while it is blocked on a foreground
    subprocess must kill the subprocess, not just disconnect.

    The agent's ``bash`` turn writes the child's PID to a file, then blocks the
    turn on a long ``sleep`` (so the agent stays busy and the child is a live
    foreground process). Deleting the agent stops its PTY; closing the primary
    fd SIGHUPs the foreground process group, which must cascade to the child.

    Without process-group teardown, the orphaned subprocess survives until its
    own sleep finishes (300s). See SCU-211.
    """
    pid_path = Path(tempfile.mktemp(prefix="scu211_foreground_", suffix=".pid"))
    leaked_pid: int | None = None

    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    try:
        _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="SCU-211 WS")
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first
        expect(terminal_tab).to_be_visible()

        # The agent spawns a long-lived foreground child and records its PID,
        # then the turn blocks on the same child (sleep) — the agent stays busy
        # with a live foreground process the whole time.
        send_fake_agent_command(
            agents_dir,
            bash(f'echo $$ > "{pid_path}"; exec sleep 300'),
        )
        expect(terminal_tab).to_have_attribute("data-dot-status", "running")

        leaked_pid = _read_pid_file(pid_path, page)
        assert _is_process_alive(leaked_pid), (
            f"Subprocess (PID {leaked_pid}) should be alive immediately after writing its PID"
        )

        # Stop the agent: deleting it tears down the PTY (manager.stop()).
        agent_tab_bar.delete_agent_via_close_button(agent_tab_index=1)

        # The subprocess must die within 20s of stop. Without process-group
        # teardown the agent program is killed but the orphaned child keeps
        # running until its own 300s sleep finishes. Polled state is an OS
        # process, not the browser DOM, so use ``time.sleep``.
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline and _is_process_alive(leaked_pid):
            time.sleep(0.2)

        assert not _is_process_alive(leaked_pid), (
            f"Foreground subprocess (PID {leaked_pid}) is still alive 20s after stop — the agent program was killed but its child subprocess was orphaned. See SCU-211."
        )
    finally:
        if leaked_pid is not None:
            _kill_process(leaked_pid)
        pid_path.unlink(missing_ok=True)
