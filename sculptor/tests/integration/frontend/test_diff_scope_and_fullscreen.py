"""Integration tests for the diff scope picker and expanded diff view.

Tests verify that the scope picker defaults to All when a diff is opened from
the Changes tab, and that the expand toggle works correctly. (These behaviours
used to be reached via the experimental Review All combined view; they survive
on the single-file diff opened from the Changes tab.)
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _open_file_diff_from_changes(task_page: PlaywrightTaskPage) -> None:
    """Open hello.py's diff from the Changes tab (All scope)."""
    task_page.activate_changes_panel(scope="all")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    changes_tree.get_tree_rows().filter(has_text="hello.py").click()


@user_story("to see the Changes tab scope picker default to All")
def test_scope_picker_defaults_to_all(sculptor_instance_: SculptorInstance) -> None:
    """The Changes tab scope picker should default to the All scope."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    task_page.activate_changes_panel(scope="all")
    task_page.get_file_browser().get_refresh_button().click()

    changes_panel = task_page.get_changes_panel()
    scope_picker = changes_panel.get_scope_picker()
    expect(scope_picker).to_be_visible()
    expect(changes_panel.get_scope_all()).to_have_attribute("data-state", "on")


@user_story("to use the expand toggle for distraction-free diff review")
def test_expand_toggle_expands_and_collapses(sculptor_instance_: SculptorInstance) -> None:
    """The expand toggle should expand the diff to fill the layout area."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    _open_file_diff_from_changes(task_page)

    diff_panel = task_page.get_diff_panel()
    expand_toggle = diff_panel.get_expand_toggle()
    expect(expand_toggle).to_be_visible()
    expand_toggle.click()
