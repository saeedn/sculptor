"""Integration tests for workspace-scoped changes visibility.

These tests verify that the Changes tab in the File Browser shows changes
from ALL agents in a workspace, not just the currently viewed agent.

Background:
- Each workspace shares a single git repository among its agents.
- The Changes tab should reflect the state of the workspace's repo,
  regardless of which agent made the changes.

These tests create a workspace with two agents, have each agent write a
different file, and verify that both files appear in the Changes tab
for BOTH agents.
"""

from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import READY_BANNER
from sculptor.testing.fake_terminal_agent import register_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

_SECOND_REGISTRATION_ID = "fake-terminal-agent-2"


def _add_second_fake_terminal_agent(page: Page, agents_dir: Path) -> None:
    """Register and launch a second fake terminal agent in the current workspace.

    Uses a distinct registration id (and commands directory) so the two agents
    never read each other's commands.
    """
    register_fake_terminal_agent(agents_dir, registration_id=_SECOND_REGISTRATION_ID, display_name="Fake Terminal Two")
    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    agent_tab_bar.open_agent_type_menu()
    registered_item = agent_tab_bar.get_agent_type_menu_item_registered(_SECOND_REGISTRATION_ID)
    expect(registered_item).to_be_visible()
    registered_item.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()
    wait_for_xterm_substring(page, READY_BANNER)


@user_story("to see all workspace changes regardless of which agent made them")
def test_uncommitted_tab_shows_changes_from_all_agents(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Two agents in one workspace each write a file. Both files should appear
    in the Uncommitted tab for both agents.

    Steps:
    1. Create workspace with agent 1, which writes file_from_agent1.py
    2. Add agent 2 to the same workspace, which writes file_from_agent2.py
    3. View agent 2's Uncommitted tab — should show BOTH files
    4. Switch to agent 1's Uncommitted tab — should also show BOTH files
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Shared Changes WS")
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("file_from_agent1.py", "def created_by_agent1():\n    return 'agent1'\n"),
    )

    _add_second_fake_terminal_agent(page, agents_dir)
    expect(agent_tab_bar.get_agent_tabs()).to_have_count(2)
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("file_from_agent2.py", "def created_by_agent2():\n    return 'agent2'\n"),
        registration_id=_SECOND_REGISTRATION_ID,
    )

    task_page_2 = PlaywrightTaskPage(page=page)
    task_page_2.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page_2.get_file_browser().get_refresh_button().click()
    changes_tree = task_page_2.get_changes_panel().get_changes_tree()
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="file_from_agent1.py")).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="file_from_agent2.py")).to_be_visible()

    agent_tab_bar.get_agent_tabs().first.click()

    task_page.activate_changes_panel(scope="uncommitted")
    changes_tree_1 = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree_1).to_be_visible()
    expect(changes_tree_1.get_tree_rows().filter(has_text="file_from_agent1.py")).to_be_visible()
    expect(changes_tree_1.get_tree_rows().filter(has_text="file_from_agent2.py")).to_be_visible()


@user_story("to see diffs for files written by every agent in the workspace")
def test_changes_tab_shows_diffs_from_all_agents(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Two agents in one workspace each write a file. The Changes tab should
    surface both files' diffs.

    (This previously opened the experimental Review All combined modal, which
    was removed; the surviving behaviour — both files diffable from the Changes
    tab — is asserted here instead.)

    Steps:
    1. Create workspace with agent 1, which writes review_file1.py
    2. Add agent 2, which writes review_file2.py
    3. Open each file's diff from the Changes tab — both show their content
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Review Modal WS")
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("review_file1.py", "def from_agent1():\n    return 1\n"),
    )

    _add_second_fake_terminal_agent(page, agents_dir)
    expect(agent_tab_bar.get_agent_tabs()).to_have_count(2)
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("review_file2.py", "def from_agent2():\n    return 2\n"),
        registration_id=_SECOND_REGISTRATION_ID,
    )

    task_page_2 = PlaywrightTaskPage(page=page)
    task_page_2.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page_2.get_file_browser().get_refresh_button().click()
    changes_panel = task_page_2.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="review_file1.py")).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="review_file2.py")).to_be_visible()

    # Open each file's diff and verify the diff panel shows the right content.
    diff_panel = task_page_2.get_diff_panel()

    changes_tree.get_tree_rows().filter(has_text="review_file1.py").click()
    expect(diff_panel).to_be_visible()
    expect(diff_panel).to_contain_text("from_agent1")

    changes_tree.get_tree_rows().filter(has_text="review_file2.py").click()
    expect(diff_panel).to_contain_text("from_agent2")


@user_story("to see all workspace changes regardless of which agent made them")
def test_uncommitted_tab_updates_when_other_agent_modifies_files(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Agent 1 writes a file, then agent 2 writes a file. When switching back
    to agent 1, its Uncommitted tab should show the file written by agent 2.

    This specifically tests that changes made by other agents are reflected
    without requiring a page refresh or re-navigation.

    Steps:
    1. Create workspace with agent 1, which writes file_a.py
    2. Verify agent 1's Uncommitted tab shows 1 file
    3. Add agent 2, which writes file_b.py
    4. Switch back to agent 1
    5. Agent 1's Uncommitted tab should now show 2 files
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Update WS")
    send_fake_agent_command_and_wait(agents_dir, write_file("file_a.py", "a = 1\n"))

    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_tree = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="file_a.py")).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="file_b.py")).to_have_count(0)

    _add_second_fake_terminal_agent(page, agents_dir)
    expect(agent_tab_bar.get_agent_tabs()).to_have_count(2)
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("file_b.py", "b = 2\n"),
        registration_id=_SECOND_REGISTRATION_ID,
    )

    agent_tab_bar.get_agent_tabs().first.click()

    task_page.activate_changes_panel(scope="uncommitted")
    changes_tree_1 = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree_1).to_be_visible()
    # This is the key assertion: agent 1 should see agent 2's file too
    expect(changes_tree_1.get_tree_rows().filter(has_text="file_a.py")).to_be_visible()
    expect(changes_tree_1.get_tree_rows().filter(has_text="file_b.py")).to_be_visible()
