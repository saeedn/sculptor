"""Integration tests for many-file changesets in the Changes tab.

These tests used to exercise the auto-collapse behaviour of the experimental
Review All combined-diff view (files start collapsed past a threshold). The
Review All button and its combined-diff entry point were removed, so that
specific behaviour has no surviving production entry point. What survives — and
is asserted here — is that the Changes tab lists every changed file regardless
of how many there are, driven via the fake terminal agent.
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to see every file listed in the Changes tab for a large changeset")
def test_many_files_all_listed_in_changes_tab(sculptor_instance_: SculptorInstance) -> None:
    """A changeset with more than five files lists all of them in the Changes tab."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(
        agents_dir,
        multi_step([write_file(f"file_{i}.py", f"v = {i}\n") for i in range(1, 8)]),
    )

    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_tree = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree).to_be_visible()
    tree_rows = changes_tree.get_tree_rows()
    for i in range(1, 8):
        expect(tree_rows.filter(has_text=f"file_{i}.py")).to_be_visible()


@user_story("to see every file listed in the Changes tab for a small changeset")
def test_few_files_all_listed_in_changes_tab(sculptor_instance_: SculptorInstance) -> None:
    """A changeset with a handful of files lists all of them in the Changes tab."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(
        agents_dir,
        multi_step([write_file(f"small_{i}.py", f"v = {i}\n") for i in range(1, 4)]),
    )

    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_tree = task_page.get_changes_panel().get_changes_tree()
    expect(changes_tree).to_be_visible()
    tree_rows = changes_tree.get_tree_rows()
    for i in range(1, 4):
        expect(tree_rows.filter(has_text=f"small_{i}.py")).to_be_visible()
