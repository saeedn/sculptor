"""Regression test: Task status should not show ERROR after restart.

Bug: When Sculptor restarts in the middle of an agent turn, the task status
shows ERROR instead of BUILDING/RUNNING/READY.

Root causes:
1. During graceful shutdown, multiple exceptions (AgentPaused + background process
   failures) are collected into a ConcurrencyExceptionGroup. The exception handler
   only unwraps single-exception groups, so multi-exception groups fall through to
   AgentTaskFailure, making the task FAILED instead of QUEUED.
2. RequestStoppedAgentMessage (emitted when the agent receives SIGTERM during
   shutdown) is a subclass of PersistentRequestCompleteAgentMessage. The status
   computation in CodingAgentTaskView.status counts it as a completed request,
   making the task appear READY instead of RUNNING while re-processing.

Re-expressed against the fake terminal agent: a ``wait_for_file`` command holds
the agent busy (signal busy → RUNNING) across the restart, replacing the old
long-running-sleep vehicle.
"""

import re

from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import register_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story
from sculptor.web.derived import TaskStatus

SECONDS_MS = 1000
# Visibility gate for the post-restart page. Generous because in this test
# the Phase 2 backend is also restoring a mid-turn task, which competes
# with the workspace-snapshot WebSocket push that the workspace tab
# depends on; under CI load the snapshot can land well after a few
# seconds (SCU-570).
_RESTART_VISIBILITY_TIMEOUT_MS = 60 * SECONDS_MS
_BUILD_TIMEOUT_MS = 90 * SECONDS_MS

_TERMINAL_AGENT_TAB_NAME = f"{DEFAULT_DISPLAY_NAME} 1"

# Sentinel the agent blocks on (resolved inside the commands dir). It is never
# created, so the agent stays busy right up until the backend is torn down.
_HOLD_SENTINEL = "hold-busy.sentinel"

_NON_ERROR_STATUS = re.compile(
    f"^({re.escape(TaskStatus.BUILDING)}|{re.escape(TaskStatus.RUNNING)}|{re.escape(TaskStatus.READY)}|{re.escape(TaskStatus.WAITING)})$"
)


def _launch_busy_terminal_agent(instance: SculptorInstance) -> None:
    """Create a workspace, launch the fake terminal agent, and park it busy.

    Registers the fake terminal agent once (the TOML persists across the
    restart so the resume relaunch can find it), selects it, then sends a
    ``wait_for_file`` command on a sentinel that is never created — so the
    agent signals ``busy`` (RUNNING) and stays there until the backend dies.
    """
    page = instance.page
    agents_dir = instance.sculptor_folder / "terminal_agents"

    start_task_and_wait_for_ready(page, prompt="Say hi to me")
    register_fake_terminal_agent(agents_dir)

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    agent_tab_bar.open_agent_type_menu()
    registered_item = agent_tab_bar.get_agent_type_menu_item_registered("fake-terminal-agent")
    expect(registered_item).to_be_visible()
    registered_item.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()
    wait_for_xterm_substring(page, "FAKE-TERMINAL-AGENT-READY")

    send_fake_agent_command(agents_dir, wait_for_file(_HOLD_SENTINEL))
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
    expect(terminal_tab).to_have_attribute("data-status", TaskStatus.RUNNING, timeout=_BUILD_TIMEOUT_MS)


@user_story("to see correct task status after restarting Sculptor mid-turn")
def test_task_status_shows_running_after_restart(sculptor_instance_factory_: SculptorInstanceFactory) -> None:
    """Task status should not be ERROR after restarting mid-agent-turn.

    Steps:
    1. Launch a terminal agent and hold it busy on a ``wait_for_file`` sentinel.
    2. Wait for the agent tab to report RUNNING.
    3. Shut down Sculptor (exit context), which sends SIGTERM to the agent.
    4. Restart Sculptor and navigate to the workspace.
    5. Verify the task status is not ERROR (should be BUILDING, RUNNING, or READY).
    """
    # Phase 1: Start a long-running (parked-busy) turn and shut down mid-turn.
    with sculptor_instance_factory_.spawn_instance() as instance:
        _launch_busy_terminal_agent(instance)

    # Exiting the context sends SIGTERM to the entire process group. The fake
    # runner dies while blocked on the sentinel, leaving the turn in-flight; the
    # wrapper emits a RequestStoppedAgentMessage and the task should be finalized
    # as QUEUED (not FAILED, which would surface as ERROR).

    # Phase 2: Restart and verify the task is not in ERROR state.
    with sculptor_instance_factory_.spawn_instance() as instance:
        # Navigate to the workspace (click on the persisted workspace tab).
        layout = PlaywrightProjectLayoutPage(instance.page)
        workspace_tab = layout.get_workspace_tabs().first
        expect(workspace_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
        workspace_tab.click()

        # After restart, the task should show BUILDING (re-acquiring environment),
        # RUNNING (resumed and re-blocked on the sentinel), or READY (idle). If the
        # shutdown failed to produce QUEUED (task ended up FAILED instead), the
        # status would be ERROR.
        agent_tab_bar = PlaywrightAgentTabBarElement(instance.page)
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
        expect(terminal_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
        expect(terminal_tab).to_have_attribute("data-status", _NON_ERROR_STATUS, timeout=_BUILD_TIMEOUT_MS)
