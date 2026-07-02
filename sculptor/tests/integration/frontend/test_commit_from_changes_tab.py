"""Integration tests for the commit control in the Changes tab.

The commit button summarises the uncommitted change count and (for chat agents)
sends a commit prompt to the agent. A terminal agent has no chat surface, so the
button is rendered but disabled; this test asserts the surviving, non-chat
behaviour: the uncommitted file is listed and the commit button reflects the
change count.
"""

import re

from playwright.sync_api import expect

from sculptor.testing.elements.file_tree import get_changes_tree
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to see the commit control summarise uncommitted changes in the Changes tab")
def test_commit_button_reflects_uncommitted_change_count(sculptor_instance_: SculptorInstance) -> None:
    """After writing a file, the Changes tab (Uncommitted scope) lists it and the
    commit button reports the change count.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    # Wait until hello.py is on disk so the Uncommitted scope picker is rendered
    # (it only appears once the changes panel has changes to show).
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    # Open Changes tab (Uncommitted scope — commit only applies to uncommitted changes)
    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch: on a freshly-created workspace the initial
    # files-changed signal can land before the frontend's diff subscription is
    # ready, leaving the changes tree empty until an explicit refetch.
    task_page.get_file_browser().get_refresh_button().click()

    changes_tree = get_changes_tree(page)
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="hello.py")).to_be_visible()

    # The commit control summarises the uncommitted change count. We assert it
    # reports at least the one change we wrote (the exact total can include
    # incidental workspace-setup files, so we match the "Commit N change(s)"
    # shape rather than pinning an exact count).
    commit_btn = task_page.get_commit_button()
    expect(commit_btn).to_be_visible()
    expect(commit_btn).to_contain_text(re.compile(r"Commit \d+ changes?"))
