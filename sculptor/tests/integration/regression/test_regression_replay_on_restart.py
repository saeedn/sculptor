"""Regression test for "agent auto-replays prompt after restart" bugs.

When Sculptor restarts after the agent was in certain mid-turn states, the
user's prompt could silently get re-delivered on the next agent run — making
the agent appear to auto-start working on a prompt the user did not just send.
This test pins the desired behavior end-to-end: after a restart, the agent must
settle back to an idle (READY) state rather than getting stuck mid-turn.

Re-expressed against the fake terminal agent: the chat / AUQ replay vehicles
(the long-running-sleep prompt and the ask-user-question prompt) are gone with
the rich chat surface, so the surviving contract is the registered-agent resume
path — after a restart the agent relaunches via its resume command and settles
to READY, not stuck RUNNING.

Other replay paths (disabled-resume FIXME; save/state-update race; post-answer
interrupted-completion reconciliation) require triggers that
``SculptorInstanceFactory`` cannot reproduce — SIGKILL between two specific
transactions, or shutdown timed inside a millisecond-scale window. Those bugs
are covered by backend unit tests in
``sculptor/sculptor/tasks/handlers/run_agent/v1_test.py``.
"""

from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import focus_agent_terminal
from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import register_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story
from sculptor.web.derived import TaskStatus

_SECONDS_MS = 1000

# Visibility gate for the post-restart page — generous because the Phase-2
# backend is restoring a previously-running task and CI can be slow.
_RESTART_VISIBILITY_TIMEOUT_MS = 60 * _SECONDS_MS

# Window we give the post-restart agent to settle into ``READY``. Has to be
# larger than the BUILDING phase (env acquisition) plus the resumed runner's
# brief re-run of any un-marked command, but a stuck replay would never settle.
_SETTLE_TIMEOUT_MS = 60 * _SECONDS_MS

_TERMINAL_AGENT_TAB_NAME = f"{DEFAULT_DISPLAY_NAME} 1"


def _launch_and_complete_terminal_turn(instance: SculptorInstance) -> None:
    """Create a workspace, launch the fake terminal agent, run a command to idle.

    Registers the fake terminal agent once (the TOML persists across the
    restart so the resume relaunch can find it), selects it, then runs a
    ``write_file`` command to completion — leaving the agent idle (READY)
    before the restart.
    """
    page = instance.page
    agents_dir = instance.sculptor_folder / "terminal_agents"

    start_task_and_wait_for_ready(page)
    register_fake_terminal_agent(agents_dir)

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    agent_tab_bar.open_agent_type_menu()
    registered_item = agent_tab_bar.get_agent_type_menu_item_registered("fake-terminal-agent")
    expect(registered_item).to_be_visible()
    registered_item.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()
    focus_agent_terminal(page)
    wait_for_xterm_substring(page, "FAKE-TERMINAL-AGENT-READY")

    send_fake_agent_command_and_wait(agents_dir, write_file("replay_marker.txt", "done"))
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
    expect(terminal_tab).to_have_attribute("data-status", TaskStatus.READY, timeout=_SETTLE_TIMEOUT_MS)


@user_story("not have my interrupted prompt silently re-run after Sculptor restarts")
def test_terminal_agent_settles_ready_after_restart(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """After a restart the resumed agent must settle to READY, not stuck mid-turn.

    A stuck replay (the original bug class) would keep the agent RUNNING
    forever; this test asserts it reaches READY within a generous window.
    """
    with sculptor_instance_factory_.spawn_instance() as instance:
        _launch_and_complete_terminal_turn(instance)

    with sculptor_instance_factory_.spawn_instance() as instance:
        layout = PlaywrightProjectLayoutPage(instance.page)
        workspace_tab = layout.get_workspace_tabs().first
        expect(workspace_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
        workspace_tab.click()

        agent_tab_bar = PlaywrightAgentTabBarElement(instance.page)
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
        expect(terminal_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
        terminal_tab.click()
        expect(get_agent_terminal_panel(instance.page)).to_be_visible()

        # The relaunch ran the rendered resume command (no fresh prompt replay)
        # and the agent settles back to idle.
        focus_agent_terminal(instance.page)
        wait_for_xterm_substring(instance.page, "RESUMED-fake-terminal-agent-session")
        expect(terminal_tab).to_have_attribute("data-status", TaskStatus.READY, timeout=_SETTLE_TIMEOUT_MS)
