"""Tests for stopping a running terminal-agent turn and continuing afterward.

A terminal agent has no chat surface, so "interrupt the running turn" is
re-expressed against the terminal lifecycle: hold the agent busy on a
``wait_for_file`` sentinel (the running tab dot is visible), then stop the turn
and observe the dot settle calm. The agent stays usable — a follow-up command
runs to completion. This preserves the old interrupt/continue behavioral
assertions (running indicator shows, settles after stop, agent continues).
"""

import re

from playwright.sync_api import Locator
from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
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
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

_CALM = re.compile(r"^(read|unread)$")


def _terminal_tab(agent_tab_bar: PlaywrightAgentTabBarElement) -> Locator:
    return agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first


@user_story("to stop a terminal agent while it is working and see it settle")
def test_stop_running_turn_settles_the_agent(sculptor_instance_: SculptorInstance) -> None:
    """Holding the agent busy on a sentinel shows the running dot; stopping the
    turn (releasing the held wait) settles the dot calm — the terminal analog of
    interrupting a running turn before any output completes."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Interrupt WS")
    terminal_tab = _terminal_tab(agent_tab_bar)
    expect(terminal_tab).to_be_visible()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    # Hold the agent busy: it blocks on a sentinel (running dot).
    send_fake_agent_command(agents_dir, wait_for_file("stop.sentinel"))
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")

    # Stop the running turn by releasing the held wait; the dot settles calm.
    release_fake_agent_wait(agents_dir, "stop.sentinel")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)


@user_story("to stop the agent and then continue it with a new command")
def test_stop_and_continue(sculptor_instance_: SculptorInstance) -> None:
    """After a turn is stopped, the agent processes a new command successfully —
    the terminal analog of "interrupt, then continue with a new message"."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Continue WS")
    terminal_tab = _terminal_tab(agent_tab_bar)
    expect(terminal_tab).to_be_visible()

    # First turn: run, complete, settle calm.
    send_fake_agent_command_and_wait(agents_dir, bash("echo FIRST-TURN"))
    wait_for_xterm_substring(page, "FIRST-TURN")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    # Second turn: hold busy, then stop (release) — the dot settles.
    send_fake_agent_command(agents_dir, wait_for_file("continue.sentinel"))
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")
    release_fake_agent_wait(agents_dir, "continue.sentinel")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    # Continue: a follow-up command runs and completes after the stop.
    send_fake_agent_command_and_wait(agents_dir, bash("echo FOLLOW-UP-AFTER-STOP"))
    wait_for_xterm_substring(page, "FOLLOW-UP-AFTER-STOP")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)


@user_story("to stop the agent repeatedly while busy without leaving it stuck")
def test_repeated_stops_while_busy_leave_agent_usable(sculptor_instance_: SculptorInstance) -> None:
    """Holding the agent busy across two turns and stopping each leaves it
    usable — repeated stops never wedge the agent into a permanent running
    state."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Repeat Stop WS")
    terminal_tab = _terminal_tab(agent_tab_bar)
    expect(terminal_tab).to_be_visible()

    for index in range(2):
        sentinel = f"repeat-{index}.sentinel"
        send_fake_agent_command(agents_dir, multi_step([bash("echo BUSY"), wait_for_file(sentinel)]))
        expect(terminal_tab).to_have_attribute("data-dot-status", "running")
        release_fake_agent_wait(agents_dir, sentinel)
        expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    send_fake_agent_command_and_wait(agents_dir, bash("echo STILL-USABLE"))
    wait_for_xterm_substring(page, "STILL-USABLE")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)
