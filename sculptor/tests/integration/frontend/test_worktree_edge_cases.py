"""Integration tests for worktree-mode edge cases.

Two orthogonal spec requirements bundled for suite manageability:
- Workspace setup command runs in a worktree workspace.
- Missing local repo surfaces a clear error state.

The "missing local repo" case is intentionally last: the project-accessibility
background monitor flips ``is_path_accessible=False`` while the repo is moved
away, and the next monitor cycle (~10s) has to elapse before the flag flips
back to True after the test restores the path. Subsequent tests get 404s on
``/repo_info`` until that happens, so we keep this test at the bottom.
"""

import re

from playwright.sync_api import expect

from sculptor.constants import ElementIDs
from sculptor.testing.elements.setup_status import PlaywrightSetupStatusElement
from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.playwright_utils import navigate_to_add_workspace_page
from sculptor.testing.playwright_utils import navigate_to_settings_page
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to have my worktree workspace automatically set up when created")
def test_setup_command_runs_in_worktree_workspace(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page

    settings_page = navigate_to_settings_page(page=page)
    settings_page.click_on_repositories().expand_repo_config()
    setup_input = page.get_by_test_id(ElementIDs.SETTINGS_WORKSPACE_SETUP_COMMAND_INPUT).first
    expect(setup_input).to_be_visible()
    setup_input.fill('echo "SCULPTOR_SETUP_WORKTREE_MARKER_67890"')
    setup_input.blur()
    page.wait_for_timeout(500)

    # Worktree is the default; no mode selector interaction needed.
    navigate_to_add_workspace_page(page)
    add_ws = PlaywrightAddWorkspacePage(page=page)
    add_ws.get_workspace_name_input().fill("setup-in-worktree")
    branch_input = add_ws.get_branch_name_input()
    expect(branch_input).to_have_value(re.compile(r".+"), timeout=5_000)
    add_ws.select_terminal_agent_type()
    add_ws.get_submit_button().click()

    # The workspace/agent page loaded once the terminal panel appears.
    terminal_panel = page.get_by_test_id(ElementIDs.AGENT_TERMINAL_PANEL)
    expect(terminal_panel).to_be_visible(timeout=60_000)

    # The setup command no longer runs in a PTY tab; it streams into the
    # SetupStatusCard popover. Wait for a known terminal state before opening
    # the popover instead of relying on the click to auto-wait: the rerun
    # button only mounts once the run has finished (succeeded/failed), so its
    # visibility is a reliable "setup is done and the card is in its
    # interactive popover layout" signal. Clicking only after that avoids
    # racing the pending->running->succeeded transition, which on fast
    # machines completes between the card appearing and the popover opening —
    # leaving `setup-status-output` unmounted (the flake this test hit). The
    # canonical test_workspace_setup_status.py cases gate on the same signal.
    setup = PlaywrightSetupStatusElement(page)
    card = setup.get_card()
    expect(card).to_be_visible()
    expect(setup.get_rerun_button()).to_be_visible()
    card.click()
    expect(setup.get_output()).to_contain_text("SCULPTOR_SETUP_WORKTREE_MARKER_67890")


@user_story("to see a clear error when my local repo disappears under a worktree workspace")
def test_missing_local_repo_surfaces_error(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page

    # Worktree is the default; no mode selector interaction needed.
    navigate_to_add_workspace_page(page)
    add_ws = PlaywrightAddWorkspacePage(page=page)
    add_ws.get_workspace_name_input().fill("missing-repo")

    branch_input = add_ws.get_branch_name_input()
    expect(branch_input).to_have_value(re.compile(r".+"))

    add_ws.submit_and_wait_for_workspace()

    user_repo_path = sculptor_instance_.project_path
    moved_path = user_repo_path.parent / f"{user_repo_path.name}-moved-by-test"
    user_repo_path.rename(moved_path)
    try:
        # The banner appears only after the project-accessibility background
        # monitor (10s interval) detects the missing path AND the frontend's
        # subsequent project-state poll picks it up — give it two full cycles
        # plus a safety margin to avoid flaking when other tests churn state.
        error_banner = add_ws.get_warning_banner()
        expect(error_banner).to_be_visible(timeout=45_000)
    finally:
        moved_path.rename(user_repo_path)

    # Wait for the project monitor to clear the warning banner once the
    # repo path is restored. Without this, the next test in the same
    # sandbox can hit a transient "repo missing" state and the new
    # workspace's worktree creation stalls until the monitor recovers.
    error_banner = add_ws.get_warning_banner()
    expect(error_banner).not_to_be_visible(timeout=45_000)
