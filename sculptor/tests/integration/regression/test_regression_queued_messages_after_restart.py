"""Regression tests for restart recovery of an interrupted agent turn.

When Sculptor goes down while an agent is mid-turn, the restart must recover
the agent: the workspace and its agent come back, the interrupted turn reaches
a terminal state (no stuck RUNNING), and nothing surfaces as ERROR.

The original tests also pinned a queued-follow-up-message contract, but the
queued-message chat surface does not survive the slim-down (terminal agents
have no chat). What survives — and what these tests now pin — is the
restart-recovery contract for the two shutdown flavors:

- ``test_interrupted_turn_recovers_after_hard_kill_restart`` — SIGKILL via
  ``SculptorInstance.hard_kill()``: nothing terminal is persisted for the
  in-flight turn, so the next run takes the RESUME path (crash / OOM / power
  loss).
- ``test_interrupted_turn_recovers_after_graceful_restart`` — normal SIGTERM
  teardown (quit and reopen): the wrapper persists a killed completion for the
  in-flight turn and the run loop advances past it before exiting.

Both tests park the agent mid-turn on a ``wait_for_file`` sentinel (the
terminal-agent equivalent of the old streamed-then-paused vehicle) so the turn
is genuinely in-flight when the backend dies.

Millisecond-precise kill windows (e.g. SIGKILL between two specific
transactions) cannot be reproduced at this layer; those are pinned by backend
unit tests in ``sculptor/sculptor/tasks/handlers/run_agent/v1_test.py``.
"""

import re

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import focus_agent_terminal
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

_SECONDS_MS = 1000

# Visibility gate for the post-restart page — generous because the Phase-2
# backend is restoring a previously-running task and CI can be slow.
_RESTART_VISIBILITY_TIMEOUT_MS = 60 * _SECONDS_MS

# Window for the post-restart agent to resume the interrupted turn and settle.
_SETTLE_TIMEOUT_MS = 60 * _SECONDS_MS

_TERMINAL_AGENT_TAB_NAME = f"{DEFAULT_DISPLAY_NAME} 1"

# Sentinel the agent blocks on (resolved inside the commands dir). It is never
# created, so the agent stays busy right up until the backend is torn down.
_HOLD_SENTINEL = "hold-busy.sentinel"

_NON_ERROR_STATUS = re.compile(
    f"^({re.escape(TaskStatus.BUILDING)}|{re.escape(TaskStatus.RUNNING)}|{re.escape(TaskStatus.READY)}|{re.escape(TaskStatus.WAITING)})$"
)


def _start_paused_terminal_turn(instance: SculptorInstance) -> None:
    """Create a workspace, launch the fake terminal agent, and park it busy.

    Registers the fake terminal agent once (the TOML persists across the
    restart so the resume relaunch can find it), selects it, then sends a
    ``wait_for_file`` command on a sentinel that is never created — so the
    agent signals ``busy`` (RUNNING) and stays mid-turn until the backend dies.
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

    send_fake_agent_command(agents_dir, wait_for_file(_HOLD_SENTINEL))
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
    expect(terminal_tab).to_have_attribute("data-status", TaskStatus.RUNNING, timeout=_SETTLE_TIMEOUT_MS)


def _assert_recovered_after_restart(page: Page) -> None:
    """The post-restart contract shared by both shutdown flavors.

    The workspace and its terminal agent come back, the relaunch runs the
    rendered resume command, and the agent reaches a non-ERROR state — i.e.
    the interrupted turn was recovered, not left stuck or finalized as failed.
    """
    layout = PlaywrightProjectLayoutPage(page)
    workspace_tab = layout.get_workspace_tabs().first
    expect(workspace_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
    workspace_tab.click()

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
    expect(terminal_tab).to_be_visible(timeout=_RESTART_VISIBILITY_TIMEOUT_MS)
    terminal_tab.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    focus_agent_terminal(page)
    wait_for_xterm_substring(page, "RESUMED-fake-terminal-agent-session")
    expect(terminal_tab).to_have_attribute("data-status", _NON_ERROR_STATUS, timeout=_SETTLE_TIMEOUT_MS)


@user_story("my agent to recover after Sculptor recovers from a crash")
def test_interrupted_turn_recovers_after_hard_kill_restart(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """SIGKILL mid-turn: the restart recovers the agent via the resume path.

    The hard-kill repro: the backend dies without persisting any completion for
    the in-flight turn, so the next run takes the RESUME path.
    """
    with sculptor_instance_factory_.spawn_instance() as instance:
        _start_paused_terminal_turn(instance)
        instance.hard_kill()

    with sculptor_instance_factory_.spawn_instance() as instance:
        _assert_recovered_after_restart(instance.page)


@user_story("my agent to recover after I quit and reopen Sculptor mid-task")
def test_interrupted_turn_recovers_after_graceful_restart(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """SIGTERM mid-turn: the everyday quit-and-reopen path recovers the agent.

    Quitting Sculptor delivers SIGTERM, so the wrapper persists a killed
    completion for the in-flight turn and the run loop advances past it before
    exiting; the next run relaunches via the resume command and settles.
    """
    with sculptor_instance_factory_.spawn_instance() as instance:
        _start_paused_terminal_turn(instance)
        # Exiting the block SIGTERMs the backend, which propagates to the parked
        # fake-terminal-agent turn (killed completion persisted, no clean finish).

    with sculptor_instance_factory_.spawn_instance() as instance:
        _assert_recovered_after_restart(instance.page)
