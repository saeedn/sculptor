"""Integration tests for opening a file in the diff viewer from the file browser.

Tests verify that opening a file's diff from the Changes tab opens the diff
panel with actual file content (not "Could not load file content"), and that an
edited file shows an actual diff view rather than a read-only full-file preview.

(These flows previously entered via the chat-alpha file chip; they survive via
the file-browser Changes tab, which is the entry point asserted here.)
"""

from playwright.sync_api import expect

from sculptor.testing.elements.diff_panel import PlaywrightDiffPanelElement
from sculptor.testing.elements.diff_panel import get_diff_panel_from_page
from sculptor.testing.fake_terminal_agent import edit_file
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def open_file_diff_from_changes(task_page: PlaywrightTaskPage, file_path: str) -> None:
    """Open ``file_path``'s diff via the Changes tab (Uncommitted scope)."""
    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()
    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    changes_tree.get_tree_rows().filter(has_text=file_path).click()


def assert_diff_panel_shows_content(diff_panel: PlaywrightDiffPanelElement, tab_text: str) -> None:
    """Assert the diff panel is open with a tab and shows content (not an error)."""
    expect(diff_panel).to_be_visible()

    tab = diff_panel.get_tab_by_name(tab_text)
    expect(tab.first).to_be_visible()

    expect(diff_panel).not_to_contain_text("Could not load file content")


def assert_diff_panel_shows_diff_view(diff_panel: PlaywrightDiffPanelElement, tab_text: str) -> None:
    """Assert the diff panel shows an actual diff view (not a read-only file preview)."""
    expect(diff_panel).to_be_visible()

    tab = diff_panel.get_tab_by_name(tab_text)
    expect(tab.first).to_be_visible()

    unified = diff_panel.get_unified_diff_views()
    split = diff_panel.get_split_view()
    expect(unified.or_(split)).to_be_visible(timeout=30_000)

    expect(diff_panel.get_read_only_preview()).to_have_count(0)


@user_story("to open a created repo file in the diff viewer from the file browser")
def test_open_created_file_in_diff_viewer(sculptor_instance_: SculptorInstance) -> None:
    """Opening a written file's diff from the Changes tab opens the diff panel
    with the file's content visible (not 'Could not load file content').
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("greeting.txt", "Hello, world!\nThis is a new file.\n"))

    open_file_diff_from_changes(task_page, "greeting.txt")

    diff_panel = get_diff_panel_from_page(page)
    assert_diff_panel_shows_content(diff_panel, "greeting.txt")


@user_story("to open an edited repo file in the diff viewer from the file browser")
def test_open_edited_file_in_diff_viewer(sculptor_instance_: SculptorInstance) -> None:
    """Opening an edited file's diff from the Changes tab opens the diff panel
    with an actual diff view showing the changes (not a read-only full-file
    preview).
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Step 1: Create the file, then commit it so the later edit is a true diff.
    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("greeting.txt", "Hello, world!\nThis is a new file.\n"))
    send_fake_agent_command_and_wait(agents_dir, edit_file("greeting.txt", "Hello, world!", "Hi, everyone!"))

    # Step 2: Open the edited file's diff via the Changes tab.
    open_file_diff_from_changes(task_page, "greeting.txt")

    # Step 3: Verify the diff panel shows an actual diff view, not a read-only preview.
    diff_panel = get_diff_panel_from_page(page)
    assert_diff_panel_shows_diff_view(diff_panel, "greeting.txt")
