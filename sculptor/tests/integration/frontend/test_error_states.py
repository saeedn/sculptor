"""Tests for how a terminal agent surfaces a failing command.

A terminal agent has no chat surface and no chat-style ERROR task state: a
command that exits non-zero is not a wedge. The genuine surviving behavior is:

1. The failure surfaces in the agent's terminal output (the runner's child
   inherits the PTY, so its stderr/stdout is visible in the xterm buffer).
2. The agent settles back to a calm (read/unread) tab dot after the failing
   command — a non-zero exit must not leave the agent stuck "running".
3. The agent stays usable: a follow-up command runs and completes normally.
4. A failure that fires while the user is on another workspace does not raise a
   stuck attention/error banner in the workspace peek — the agent returns to
   idle once the command finishes.

These re-express the old chat-agent api_error/crash error-command states against
the terminal agent (the only surviving agent kind).
"""

import re

from playwright.sync_api import expect

from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import release_fake_agent_wait
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import navigate_to_add_workspace_page
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

_CALM = re.compile(r"^(read|unread)$")


@user_story("to see a failing command surface in the agent terminal but keep using the agent")
def test_command_failure_surfaces_in_terminal_and_agent_stays_usable(
    sculptor_instance_: SculptorInstance,
) -> None:
    """A non-zero-exit command surfaces its error in the terminal output, the
    tab dot settles calm (the agent is not wedged), and a follow-up command
    still runs — the terminal-agent analog of the old "API error: agent stays
    running" behavior."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Command Error WS")
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first
    expect(terminal_tab).to_be_visible()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    # Drive the agent to fail: emit a recognizable marker on stderr, then exit
    # non-zero. The runner swallows the exit code (check=False) — a failing
    # command must not crash the agent program.
    send_fake_agent_command_and_wait(
        agents_dir,
        bash("echo COMMAND-ERROR-MARKER 1>&2; exit 1"),
    )

    # The error is visible in the agent's terminal output.
    wait_for_xterm_substring(page, "COMMAND-ERROR-MARKER")

    # The failure did not wedge the agent: the tab dot is calm, not "running".
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    # The agent stays usable: a follow-up command runs and completes.
    send_fake_agent_command_and_wait(agents_dir, bash("echo RECOVERY-AFTER-ERROR"))
    wait_for_xterm_substring(page, "RECOVERY-AFTER-ERROR")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)


@user_story("to notice a terminal agent's command finish from another workspace without a stuck banner")
def test_command_failure_settles_to_idle_in_workspace_peek(
    sculptor_instance_: SculptorInstance,
) -> None:
    """When a command fails while the user is on a different workspace, the
    workspace peek shows the agent busy while it runs and settles to idle (no
    stuck attention banner) once it finishes — a non-zero exit is not a
    persistent error state for a terminal agent."""
    page = sculptor_instance_.page
    layout = PlaywrightProjectLayoutPage(page=page)
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Peek Error WS")
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first

    # Hold the agent busy on a failing command: fail, then block on a sentinel so
    # the busy → idle transition is observable deterministically.
    send_fake_agent_command(
        agents_dir,
        multi_step([bash("echo PEEK-ERROR-MARKER 1>&2; exit 1"), wait_for_file("hold.sentinel")]),
    )
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")

    # Navigate away and peek: the agent is still running (held on the sentinel),
    # so the peek surfaces the working state, not an error.
    navigate_to_add_workspace_page(page)
    workspace_tab = layout.get_workspace_tabs().first
    workspace_tab.hover()
    peek = layout.get_workspace_peek_popover()
    expect(peek).to_be_visible()
    expect(peek.get_header()).to_contain_text("Peek Error WS")

    # Release the wait → the command finishes → the agent settles calm. There is
    # no persistent error banner: a non-zero exit does not wedge a terminal agent.
    release_fake_agent_wait(agents_dir, "hold.sentinel")
    page.mouse.move(0, 0)
    workspace_tab.click()
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)
