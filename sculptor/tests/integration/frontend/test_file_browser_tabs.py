"""Integration tests for File Browser tab switching.

Tests verify that clicking between All, Changes, and History tabs renders
the correct content in each tab.
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to switch between All, Changes, and History tabs and see correct content")
def test_tab_switching_shows_correct_content(sculptor_instance_: SculptorInstance) -> None:
    """Clicking each tab should display the appropriate content.

    - All tab: shows the file tree with both committed.py and uncommitted.py
    - Changes tab: shows only uncommitted.py
    - History tab: shows commit history with "Add committed.py"
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)

    # Create a feature branch, write a file, and commit it so we have content in
    # all three tabs: the file tree (All), uncommitted changes (Changes), and
    # commit history (History).
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature"),
                write_file("committed.py", "x = 1\n"),
                bash("git add -A && git commit -m 'Add committed.py'"),
                write_file("uncommitted.py", "y = 2\n"),
            ]
        ),
    )

    task_page.activate_file_browser()
    file_browser = task_page.get_file_browser()

    all_tab = file_browser.get_tab_all()
    history_tab = file_browser.get_tab_history()

    # -- All tab: file tree should show both files --
    expect(all_tab).to_be_visible()
    all_tab.click()
    expect(file_browser).to_contain_text("committed.py")
    expect(file_browser).to_contain_text("uncommitted.py")

    # -- Changes tab (Uncommitted scope): only uncommitted.py --
    task_page.activate_changes_panel(scope="uncommitted")
    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()

    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(1)
    expect(tree_rows.first).to_contain_text("uncommitted.py")

    # -- History tab: shows the commit --
    history_tab.click()
    history_panel = file_browser.get_history_panel()
    expect(history_panel).to_be_visible()
    expect(history_panel).to_contain_text("Add committed.py")

    # -- Switch back to All tab: file tree still works --
    all_tab.click()
    expect(file_browser).to_contain_text("committed.py")
    expect(file_browser).to_contain_text("uncommitted.py")
