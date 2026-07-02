"""Integration tests for the discard file workflow.

Tests verify that clicking the discard button on a file in the Changes panel
opens a confirmation dialog, and confirming removes the file from the list.
"""

from pathlib import Path

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _write_two_files(agents_dir: Path) -> None:
    """Write two files (keep.py + discard_me.py) as one fake-agent turn."""
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                write_file("keep.py", "keep = True\n"),
                write_file("discard_me.py", "remove = True\n"),
            ]
        ),
    )


@user_story("to discard changes to a single file via the Changes panel")
def test_discard_file_removes_from_changes(sculptor_instance_: SculptorInstance) -> None:
    """Discarding a file should remove it from the Changes panel.

    Write two files, open the Changes tab, hover over one file to reveal the
    discard button, click it, confirm the dialog, and verify only one file
    remains.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    _write_two_files(agents_dir)

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(2)

    # Find the row containing discard_me.py and hover to reveal the discard button
    discard_row = tree_rows.filter(has_text="discard_me.py")
    expect(discard_row).to_have_count(1)
    discard_row.hover()

    discard_button = changes_panel.get_discard_button(discard_row)
    expect(discard_button).to_be_visible()
    discard_button.click()

    # The confirmation dialog should appear
    dialog = changes_panel.get_discard_dialog()
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("discard_me.py")
    expect(dialog).to_contain_text("cannot be undone")

    changes_panel.get_discard_dialog_confirm().click()

    # Dialog should close and the file should be removed from the list
    expect(dialog).to_be_hidden()
    expect(tree_rows).to_have_count(1)
    expect(tree_rows.first).to_contain_text("keep.py")


@user_story("to cancel the discard dialog without losing changes")
def test_discard_cancel_preserves_file(sculptor_instance_: SculptorInstance) -> None:
    """Cancelling the discard dialog should leave the file in the Changes panel."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    _write_two_files(agents_dir)

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(2)

    # Hover and click discard on discard_me.py
    discard_row = tree_rows.filter(has_text="discard_me.py")
    discard_row.hover()
    changes_panel.get_discard_button(discard_row).click()

    dialog = changes_panel.get_discard_dialog()
    expect(dialog).to_be_visible()
    changes_panel.get_discard_dialog_cancel().click()

    # Dialog should close and both files should still be listed
    expect(dialog).to_be_hidden()
    expect(tree_rows).to_have_count(2)
