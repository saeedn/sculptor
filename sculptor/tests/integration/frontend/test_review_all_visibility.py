"""Integration tests asserting the experimental Review All button is gone.

The Review All combined-diff button was removed from the File Browser. These
tests confirm the button no longer renders in the panel header, while the
surviving diff behaviour (uncommitted and committed changes showing in the
Changes tab) still works, driven via terminal git ops.
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

# The Review All button used this test id; it must never render now.
_REVIEW_ALL_BTN_TESTID = "CHANGES_REVIEW_ALL_BTN"


@user_story("to not see a Review All button when there are uncommitted changes")
def test_no_review_all_button_with_uncommitted_changes(sculptor_instance_: SculptorInstance) -> None:
    """The removed Review All button must not appear even with uncommitted changes."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    task_page.activate_file_browser()
    file_browser = task_page.get_file_browser()
    expect(file_browser).to_be_visible()

    # The uncommitted change still surfaces in the Changes tab.
    task_page.activate_changes_panel(scope="uncommitted")
    file_browser.get_refresh_button().click()
    changes_tree = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree.get_tree_rows().filter(has_text="hello.py")).to_be_visible()

    # But the Review All button is gone.
    expect(file_browser.get_by_test_id(_REVIEW_ALL_BTN_TESTID)).to_have_count(0)


@user_story("to not see a Review All button when the branch has commits only")
def test_no_review_all_button_with_commits_only(sculptor_instance_: SculptorInstance) -> None:
    """The removed Review All button must not appear when all changes are committed."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature"),
                write_file("committed.py", "x = 1\n"),
                bash("git add -A && git commit -m 'Add committed.py'"),
            ]
        ),
    )

    task_page.activate_file_browser()
    file_browser = task_page.get_file_browser()
    expect(file_browser).to_be_visible()

    # The committed change still surfaces in the Changes tab (All scope).
    task_page.activate_changes_panel(scope="all")
    file_browser.get_refresh_button().click()
    changes_tree = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree.get_tree_rows().filter(has_text="committed.py")).to_be_visible()

    # But the Review All button is gone.
    expect(file_browser.get_by_test_id(_REVIEW_ALL_BTN_TESTID)).to_have_count(0)


@user_story("to not see a Review All button on a fresh workspace with no changes")
def test_no_review_all_button_with_no_changes(sculptor_instance_: SculptorInstance) -> None:
    """The removed Review All button must not appear on a fresh workspace either."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Start the project repo from main so the workspace clone has zero divergence.
    sculptor_instance_.repo.repo.run_command(["git", "checkout", "main"])

    task_page, _ = start_fake_terminal_agent(page, agents_dir)

    task_page.activate_file_browser()
    file_browser = task_page.get_file_browser()
    expect(file_browser).to_be_visible()

    expect(file_browser.get_by_test_id(_REVIEW_ALL_BTN_TESTID)).to_have_count(0)
