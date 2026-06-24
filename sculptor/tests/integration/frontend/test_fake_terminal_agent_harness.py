"""End-to-end proof of the fake terminal-agent harness.

This is the canonical example every Phase 7 REWRITE task copies: register the
fake terminal agent, launch it as an agent, drive it through the side-effecting
DSL (write_file + bash), and assert the workspace/diff viewer reflects the
change while the tab dot tracks busy → idle.
"""

import re

from playwright.sync_api import expect

from sculptor.testing.elements.file_tree import get_changes_tree
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import release_fake_agent_wait
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

_CALM = re.compile(r"^(read|unread)$")


@user_story("to drive a fake terminal agent through the side-effecting DSL and see its changes")
def test_fake_terminal_agent_drives_diff_and_tab_dot(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Fake Harness WS")
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first
    expect(terminal_tab).to_be_visible()

    # Fresh agent, no command yet: calm neutral dot.
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    # write_file then block on a sentinel: the agent stays busy (running dot) and
    # the written file shows up in the diff before we release it.
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [write_file("harness_file.txt", "from the fake terminal agent"), wait_for_file("release.sentinel")]
        ),
    )
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")

    task_page.activate_changes_panel()
    changes_tree = get_changes_tree(page)
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="harness_file.txt")).to_be_visible()

    # Release the wait → the command finishes → the dot settles calm.
    release_fake_agent_wait(agents_dir, "release.sentinel")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)

    # A second command via bash mutates the workspace again; the diff updates.
    send_fake_agent_command(agents_dir, bash("echo second > second_file.txt"))
    expect(changes_tree.get_tree_rows().filter(has_text="second_file.txt")).to_be_visible()
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)
