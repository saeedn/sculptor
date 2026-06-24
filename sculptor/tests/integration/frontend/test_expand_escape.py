"""Integration tests for exiting expanded diff view with the Escape key.

Tests verify that pressing Escape while in expand mode exits back to the
normal layout. (Expand mode used to be reached via the experimental Review All
combined view; it survives on the single-file diff opened from the Changes tab.)
"""

from playwright.sync_api import expect

from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to exit expanded diff view by pressing Escape")
def test_escape_exits_expand_mode(sculptor_instance_: SculptorInstance) -> None:
    """Pressing Escape in expand mode should return to the normal layout."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    # Open hello.py's diff from the Changes tab.
    task_page.activate_changes_panel(scope="all")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    changes_tree.get_tree_rows().filter(has_text="hello.py").click()

    # Click expand toggle to enter expand mode.
    diff_panel = task_page.get_diff_panel()
    expand_toggle = diff_panel.get_expand_toggle()
    expect(expand_toggle).to_be_visible()
    expand_toggle.click()

    # In expand mode the diff fills the layout; the terminal panel is hidden.
    terminal_panel = get_agent_terminal_panel(page)
    expect(terminal_panel).to_be_hidden()

    # Press Escape to exit expand mode.
    page.keyboard.press("Escape")

    # The terminal panel should be visible again after exiting expand mode.
    expect(terminal_panel).to_be_visible()
