"""Test that stopping the agent kills a SIGTERM-ignoring foreground subprocess.

SCU-1340: when a terminal agent is blocked on a foreground subprocess that traps
/ ignores SIGTERM, stopping the agent must still reap that subprocess — and must
not leave the agent in a half-torn-down state. Closing the PTY primary fd
delivers SIGHUP to the foreground process group; a child that ignores SIGTERM
but not SIGHUP is reaped by that hangup (with a SIGKILL escalation on the shell
as the backstop), so a SIGTERM-only kill being a no-op is not enough to orphan
it.

The fake terminal agent's ``bash`` DSL runs a real shell child, so the
SIGTERM-immune subprocess is a real OS process in the agent's foreground process
group.

See SCU-1340.
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

# A foreground child that installs SIG_IGN for SIGTERM (so a SIGTERM-only kill is
# a no-op), records its PID, then blocks indefinitely on ``signal.pause()``. It
# leaves SIGHUP at its default action, so closing the PTY primary fd reaps it via
# the foreground-group hangup — only the post-SIGTERM escalation can take it
# down, exactly the SCU-1340 path. ``signal.pause()`` (not a wall-clock sleep)
# keeps the child alive purely until a fatal signal arrives.
_SIGTERM_IMMUNE_CHILD = """
import os, signal, sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)
open(sys.argv[1], 'w').write(str(os.getpid()))
while True:
    signal.pause()
"""


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


@user_story("to have a SIGTERM-ignoring subprocess killed by stopping the agent without leaving it stuck")
def test_stop_kills_sigterm_immune_subprocess_without_crashing(sculptor_instance_: SculptorInstance) -> None:
    """Stopping the agent while it is blocked on a SIGTERM-ignoring foreground
    subprocess must (a) reap that subprocess via the SIGHUP/SIGKILL escalation
    on the process group and (b) not leave the agent half-torn-down (the tab
    deletes cleanly).

    The child installs ``SIG_IGN`` for SIGTERM, so the SIGTERM phase of teardown
    is a no-op and only the escalation can reap it — exactly the SCU-1340 path.
    Before the fix, the orphan survived until externally killed. See SCU-1340.
    """
    pid_path = Path(tempfile.mktemp(prefix="scu1340_immune_", suffix=".pid"))
    leaked_pid: int | None = None

    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    try:
        _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="SCU-1340 WS")
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first
        expect(terminal_tab).to_be_visible()

        # The agent's turn ``exec``s a SIGTERM-immune python child in the
        # foreground (so the agent stays busy with a live, SIGTERM-ignoring
        # process). ``exec`` replaces the shell so there is no extra layer to
        # absorb the hangup.
        child_script = _SIGTERM_IMMUNE_CHILD.replace('"', '\\"')
        send_fake_agent_command(
            agents_dir,
            bash(f'exec python3 -c "{child_script}" "{pid_path}"'),
        )
        expect(terminal_tab).to_have_attribute("data-dot-status", "running")

        leaked_pid = _read_pid_file(pid_path, page)
        assert _is_process_alive(leaked_pid), (
            f"Subprocess (PID {leaked_pid}) should be alive immediately after writing its PID"
        )

        # Stop the agent: deleting it tears down the PTY (manager.stop()).
        agent_tab_bar.delete_agent_via_close_button(agent_tab_index=1)

        # The subprocess must die within 15s of stop. A SIGTERM-only kill is a
        # no-op on this child, so survival means the SIGHUP/SIGKILL escalation
        # did not reach it. Polled state is an OS process, not the browser DOM,
        # so use ``time.sleep``.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and _is_process_alive(leaked_pid):
            time.sleep(0.2)

        assert not _is_process_alive(leaked_pid), (
            f"SIGTERM-ignoring subprocess (PID {leaked_pid}) is still alive 15s after stop — the SIGHUP/SIGKILL escalation to the process group did not reach it. See SCU-1340."
        )

        # Stop is user-initiated and must not leave the agent half-torn-down: the
        # agent tab deletes cleanly, leaving only the original chat agent.
        expect(agent_tab_bar.get_agent_tabs()).to_have_count(1)
    finally:
        if leaked_pid is not None:
            _kill_process(leaked_pid)
        pid_path.unlink(missing_ok=True)
