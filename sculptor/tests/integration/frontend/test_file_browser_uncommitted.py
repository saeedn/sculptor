"""Integration tests for uncommitted changes shown in the Changes panel.

Tests verify that the Changes panel correctly shows only uncommitted changes
(HEAD->working tree), not the full history from the base branch. Tests that
involve commits use a feature branch so that the base branch (main) stays
behind, making committed vs uncommitted changes distinct.
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import edit_file
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

# Tests that exercise committed-vs-uncommitted behavior start with
# `git checkout -b feature` so that commits land on the feature branch while
# `main` (the source_branch / diff base) stays at the initial commit.


@user_story("to see only uncommitted changes when clicking a file in the Changes panel")
def test_individual_file_diff_shows_only_uncommitted_changes(sculptor_instance_: SculptorInstance) -> None:
    """Clicking a file in the Changes panel should show only uncommitted changes.

    After creating a feature branch, committing a file, then editing it again,
    the diff panel should show a modification diff (hello -> goodbye) -- not the
    entire file as newly added from the base branch.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature"),
                write_file("app.py", "def main():\n    print('hello')\n"),
                bash("git add -A && git commit -m 'Add app.py'"),
                edit_file("app.py", "print('hello')", "print('goodbye')"),
            ]
        ),
    )

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()

    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(1)
    expect(tree_rows.first).to_contain_text("app.py")

    # The status indicator in the changes tree should show "M" (modified)
    status = changes_tree.get_row_status(tree_rows.first)
    expect(status).to_have_text("M")

    # Now click the file to open it in the diff panel
    tree_rows.first.click()

    diff_panel = task_page.get_diff_panel()
    expect(diff_panel).to_be_visible()

    # Ensure unified mode via the toggle's data-state attribute
    diff_panel.ensure_unified_mode()

    # Wait for the diff file header to confirm the correct file is active
    diff_header = diff_panel.get_file_header()
    expect(diff_header).to_contain_text("app.py")

    # The diff should show a modification: both 'hello' (removed) and 'goodbye'
    # (added) should be visible since it's a HEAD->working tree change.
    diff_view = diff_panel.get_unified_diff_views()
    expect(diff_view).to_be_visible()
    expect(diff_view).to_contain_text("hello")
    expect(diff_view).to_contain_text("goodbye")


@user_story("to see all branch files in the All scope and uncommitted changes in individual file view")
def test_individual_diff_matches_all_scope(sculptor_instance_: SculptorInstance) -> None:
    """The All scope shows all branch changes, while individual file clicks from
    the Uncommitted scope show only the uncommitted change.

    After creating a feature branch, committing alpha.py and beta.py, then
    editing alpha.py: the All scope should list both alpha.py and beta.py,
    while clicking alpha.py in the Uncommitted scope shows the uncommitted edit.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature"),
                write_file("alpha.py", "a = 1\n"),
                write_file("beta.py", "b = 2\n"),
                bash("git add -A && git commit -m 'Add alpha and beta'"),
                edit_file("alpha.py", "a = 1", "a = 999"),
            ]
        ),
    )

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()

    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    # Only alpha.py should appear in the Uncommitted changes tree
    # (beta.py is committed and has no uncommitted changes)
    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(1)
    expect(tree_rows.first).to_contain_text("alpha.py")

    # The All scope should list both alpha.py and beta.py (all branch changes).
    changes_panel.get_scope_all().click()
    all_rows = changes_tree.get_tree_rows()
    expect(all_rows.filter(has_text="alpha.py")).to_be_visible()
    expect(all_rows.filter(has_text="beta.py")).to_be_visible()

    # Back to Uncommitted scope, click alpha.py directly in the changes tree.
    changes_panel.get_scope_uncommitted().click()
    tree_rows = changes_tree.get_tree_rows()
    tree_rows.first.click()

    diff_panel = task_page.get_diff_panel()
    expect(diff_panel).to_be_visible()
    diff_header = diff_panel.get_file_header()
    expect(diff_header).to_contain_text("alpha.py")

    diff_panel.ensure_unified_mode()

    # The individual file diff should show the uncommitted change: a=1 -> a=999
    diff_view = diff_panel.get_unified_diff_views()
    expect(diff_view).to_be_visible()
    expect(diff_view).to_contain_text("a = 1")
    expect(diff_view).to_contain_text("a = 999")


@user_story("to see the changes panel clear after committing all changes")
def test_changes_panel_empty_after_commit(sculptor_instance_: SculptorInstance) -> None:
    """After committing all changes, the Changes panel should show no files."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                write_file("done.py", "x = 42\n"),
                bash("git add -A && git commit -m 'Add done.py'"),
            ]
        ),
    )

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()
    expect(changes_panel).to_contain_text("No changes")


@user_story("to see the changes panel update correctly after a second commit")
def test_changes_panel_updates_after_second_commit(sculptor_instance_: SculptorInstance) -> None:
    """The Changes panel should clear after committing the remaining changes.

    Sequence: write -> commit -> edit -> (file shows as M) -> commit again
    After the second commit, the Changes panel should be empty.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                write_file("counter.py", "count = 0\n"),
                bash("git add -A && git commit -m 'Add counter'"),
                edit_file("counter.py", "count = 0", "count = 1"),
            ]
        ),
    )

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()

    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(1)
    expect(tree_rows.first).to_contain_text("counter.py")

    # Now commit the remaining changes via a follow-up command
    send_fake_agent_command(agents_dir, bash("git add -A && git commit -m 'Increment counter'"))

    # After the second commit, Changes panel should be empty
    expect(tree_rows).to_have_count(0)


@user_story("to see correct line stats for uncommitted changes")
def test_diff_header_line_stats_reflect_uncommitted_only(sculptor_instance_: SculptorInstance) -> None:
    """Diff file header line stats should reflect only uncommitted changes.

    After creating a feature branch, committing a 5-line file, then modifying
    1 line, the header should show +1/-1 (the uncommitted edit), not +5/-0
    (the entire file as new from the base branch).
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature"),
                write_file("lines.py", "line1 = 1\nline2 = 2\nline3 = 3\nline4 = 4\nline5 = 5\n"),
                bash("git add -A && git commit -m 'Add lines.py'"),
                edit_file("lines.py", "line3 = 3", "line3 = 333"),
            ]
        ),
    )

    task_page.activate_changes_panel(scope="uncommitted")

    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows).to_have_count(1)
    tree_rows.first.click()

    diff_panel = task_page.get_diff_panel()
    diff_header = diff_panel.get_file_header()
    expect(diff_header).to_be_visible()
    expect(diff_header).to_contain_text("lines.py")

    # The uncommitted change is 1 line modified (1 added, 1 removed).
    # The header should show +1 (not +5).
    expect(diff_header).to_contain_text("+1")
    expect(diff_header).not_to_contain_text("+5")


@user_story("to see correct status for files whose content contains 'deleted file mode'")
def test_file_containing_deleted_file_mode_text_not_shown_as_deleted(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Files whose content contains 'deleted file mode' should not be marked as deleted.

    The determineFileStatus function must not match diff metadata patterns
    against file content. A new file with 'deleted file mode' in its body
    should show status 'A' (added), and an edited file with the same text
    should show status 'M' (modified).
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # --- Scenario 1: new file whose content contains "deleted file mode" ---
    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(
        agents_dir,
        write_file("tricky.txt", "This file talks about deleted file mode in git diffs.\n"),
    )

    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch (cold-start: the initial files-changed signal can
    # land before the frontend's diff subscription is ready).
    task_page.get_file_browser().get_refresh_button().click()

    changes_panel = task_page.get_changes_panel()
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()

    tricky_row = changes_tree.get_tree_rows().filter(has_text="tricky.txt")
    expect(tricky_row).to_be_visible()

    # The file is newly added — status must be "A", not "D"
    status = changes_tree.get_row_status(tricky_row)
    expect(status).to_have_text("A")

    # --- Scenario 2: edited file whose new content contains "deleted file mode" ---
    send_fake_agent_command_and_wait(
        agents_dir,
        multi_step(
            [
                write_file("notes.txt", "Some initial content.\n"),
                bash("git add -A && git commit -m 'Add notes.txt'"),
                edit_file(
                    "notes.txt",
                    "Some initial content.",
                    "This line mentions deleted file mode for documentation.",
                ),
            ]
        ),
    )

    # The `git add -A && git commit` in the second turn commits everything
    # (including tricky.txt from the first turn). Only notes.txt remains
    # uncommitted after being edited — it should show as "M", not "D".
    notes_row = changes_tree.get_tree_rows().filter(has_text="notes.txt")
    expect(notes_row).to_be_visible()
    notes_status = changes_tree.get_row_status(notes_row)
    expect(notes_status).to_have_text("M")
