"""Minimum-interface conformance suite for the terminal agent.

The terminal agent is the only surviving agent kind (the Claude/pi chat
harnesses are removed in the slim-down). It must satisfy two invariants,
re-expressed against the terminal surface (there is no chat surface):

- Turn-boundary signalling: a command runs as one busy → idle turn (the tab dot
  goes running while busy and settles calm when the turn ends) and its output
  reaches the terminal.
- Structured failure surfacing: a command that fails (non-zero exit, output on
  stderr) surfaces in the terminal output rather than being silently dropped,
  and the turn still completes (the agent settles calm — a failure is not a
  wedge).
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


@user_story("to see the terminal agent round-trip a turn (command runs, output appears, turn ends)")
def test_turn_boundary_signalling(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(
        page, agents_dir, workspace_name="Conformance: turn boundary"
    )
    terminal_tab = _terminal_tab(agent_tab_bar)
    expect(terminal_tab).to_be_visible()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    # While the turn is in flight (held on a sentinel) the dot is running.
    send_fake_agent_command(
        agents_dir,
        multi_step([bash("echo TURN-OK-91827"), wait_for_file("turn.sentinel")]),
    )
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")

    # The command's output reached the terminal during the turn.
    wait_for_xterm_substring(page, "TURN-OK-91827")

    # Releasing the sentinel ends the turn: the dot settles calm.
    release_fake_agent_wait(agents_dir, "turn.sentinel")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)


@user_story("to see a structured failure surface (not a silent drop) when the agent command errors")
def test_structured_failure_reporting(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    _task_page, agent_tab_bar = start_fake_terminal_agent(
        page, agents_dir, workspace_name="Conformance: failure reporting"
    )
    terminal_tab = _terminal_tab(agent_tab_bar)
    expect(terminal_tab).to_be_visible()

    # A failing command surfaces in the terminal output, not silently dropped.
    send_fake_agent_command_and_wait(agents_dir, bash("echo FAIL-OK-66341 1>&2; exit 1"))
    wait_for_xterm_substring(page, "FAIL-OK-66341")

    # The turn still completed: a non-zero exit settles calm, not stuck running.
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)
