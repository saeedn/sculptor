"""Integration test for branch switching and workspace creation."""

from playwright.sync_api import expect

from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to create workspaces from different branches using the branch selector")
def test_branch_switching_with_untracked_file(sculptor_instance_: SculptorInstance) -> None:
    """Test that sets up a test repo with two branches A and B as well as a single untracked file,
    checks out branch A, starts sculptor, and uses the branch selector on the New Workspace page
    to create a workspace cloned from branch B.
    """
    page = sculptor_instance_.page

    branch_a = "branch_a"
    branch_b = "branch_b"

    sculptor_instance_.repo.create_reset_and_checkout_branch(branch_a)
    sculptor_instance_.repo.write_file("src/file_a.py", "print('Hello from branch A!')")
    sculptor_instance_.repo.stage_all_changes()
    sculptor_instance_.repo.commit("Add file A", commit_time="2025-01-01T00:00:01")

    sculptor_instance_.repo.create_reset_and_checkout_branch(branch_b)
    sculptor_instance_.repo.write_file("src/file_b.py", "print('Hello from branch B!')")
    sculptor_instance_.repo.stage_all_changes()
    sculptor_instance_.repo.commit("Add file B", commit_time="2025-01-01T00:00:02")

    # Switch back to branch A (this is our current branch when Sculptor starts)
    sculptor_instance_.repo.checkout_branch(branch_a)

    sculptor_instance_.repo.write_file("untracked_file.txt", "This is an untracked file")

    current_branch = sculptor_instance_.repo.get_current_branch_name()
    assert current_branch == branch_a, f"Expected to be on {branch_a}, but on {current_branch}"

    all_branches = sculptor_instance_.repo.get_branches()
    assert branch_a in all_branches, f"Branch {branch_a} not found in repo. Available branches: {all_branches}"
    assert branch_b in all_branches, f"Branch {branch_b} not found in repo. Available branches: {all_branches}"

    # We should already be on the Add Workspace page (cleanup deletes all workspaces).
    # Worktree is the only mode, so the branch selector is editable.
    add_workspace_page = PlaywrightAddWorkspacePage(page=page)
    submit_button = add_workspace_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Fill in the workspace name (required field)
    add_workspace_page.get_workspace_name_input().fill("Branch B workspace")

    # Select branch B via the branch selector on the New Workspace page
    add_workspace_page.select_branch(branch_b)

    # Submit to create the workspace (no prompt on the Add Workspace page).
    # Pick a plain terminal agent so the terminal panel renders in CI.
    add_workspace_page.select_terminal_agent_type()
    expect(submit_button).to_be_enabled()
    submit_button.click()

    # Wait for the terminal panel to appear (we navigated to the workspace/agent page).
    task_page = PlaywrightTaskPage(page=page)
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)

    # Worktree mode should not show a mode badge.
    mode_badge = task_page.get_mode_badge()
    expect(mode_badge).not_to_be_visible()
