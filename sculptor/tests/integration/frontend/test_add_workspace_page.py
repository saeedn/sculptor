"""Integration tests for the Add Workspace page (/ws/new).

Tests verify:
- Form draft persistence (workspace name) across navigation
- Multiple new workspace tabs with independent draft state
- Creating a workspace without a prompt (agent in waiting state)
- Keyboard shortcuts: Cmd+I focuses workspace name input
- Arrow key focus recovery when nothing is focused
- Cmd+Enter in the workspace name input submits the form
- Deleting a project also deletes its workspaces
"""

import re

import pytest
from playwright.sync_api import expect

from sculptor.constants import ElementIDs
from sculptor.testing.elements.terminal import get_agent_terminal_textarea
from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.playwright_utils import blur_page
from sculptor.testing.playwright_utils import navigate_to_settings_page
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story
from sculptor.testing.utils import get_playwright_modifier_key


@user_story("to not lose my workspace form entries when navigating away and back")
def test_workspace_form_draft_persists_after_navigation(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Workspace name should persist after navigating away and back.

    Each new workspace tab has its own draftId, and drafts are keyed by that ID
    so they survive navigation within the same tab.

    Steps:
    1. Create an initial workspace so there is a tab to navigate to
    2. Navigate back to the Add Workspace page via the "+" button
    3. Fill in the workspace name
    4. Navigate away by clicking on the existing workspace tab
    5. Navigate back to the Add Workspace page via the "Open Workspace" tab
    6. Verify the workspace name is still populated
    """
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    # Step 1: Create a workspace so we have somewhere to navigate to.
    task_page = start_task_and_wait_for_ready(
        sculptor_page=page,
        prompt="Setup task",
        workspace_name="Initial Workspace",
    )

    # Step 2: Navigate back to Add Workspace page via the "+" button.
    add_workspace_button = task_page.get_add_workspace_button()
    expect(add_workspace_button).to_be_visible()
    add_workspace_button.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 3: Fill in the workspace name.
    draft_workspace_name = "My Draft Workspace"

    workspace_name_input = add_ws_page.get_workspace_name_input()
    workspace_name_input.fill(draft_workspace_name)

    # Step 4: Navigate away by clicking on the existing workspace tab.
    workspace_tab = add_ws_page.get_workspace_tabs().first
    expect(workspace_tab).to_be_visible()
    workspace_tab.click()

    # Confirm we navigated away — the chat panel of the existing workspace should appear.
    task_page = PlaywrightTaskPage(page=page)
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)

    # Step 5: Navigate back to the Add Workspace page via the "Open Workspace" tab.
    # Use .last because a stale "new workspace" tab may persist from previous test
    # cleanup when running on a shared instance with xdist reordering.
    open_workspace_tab = add_ws_page.get_add_workspace_tabs().last
    expect(open_workspace_tab).to_be_visible()
    open_workspace_tab.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 6: Verify the workspace name is still populated.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    expect(workspace_name_input).to_have_value(draft_workspace_name)


@user_story("to not lose my selected source branch and branch name when navigating away and back")
def test_workspace_form_branch_state_persists_after_navigation(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Selected source branch and manually-edited branch name should persist after navigating away and back.

    The workspace name already persists (it is keyed by draftId in localStorage),
    but the repo, source branch, and branch-name selections used to be ephemeral
    React state that reset to their defaults whenever the Add Workspace tab was
    unmounted and remounted. The result was that switching tabs and returning
    silently dropped the user's repo/branch choices while leaving the name intact
    — which could open a workspace on the wrong branch (SCU-1427).

    Steps:
    1. Create an initial workspace so there is a tab to navigate to
    2. Navigate back to the Add Workspace page via the "+" button
    3. Fill in the workspace name, select a non-default source branch ("main",
       since the test repo is checked out on "testing"), and type a custom branch name
    4. Navigate away by clicking on the existing workspace tab
    5. Navigate back to the Add Workspace page via the "Open Workspace" tab
    6. Verify the source branch and branch name are still the user's selections
    """
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    # Step 1: Create a workspace so we have somewhere to navigate to.
    task_page = start_task_and_wait_for_ready(
        sculptor_page=page,
        prompt="Setup task",
        workspace_name="Initial Workspace",
    )

    # Step 2: Navigate back to Add Workspace page via the "+" button.
    add_workspace_button = task_page.get_add_workspace_button()
    expect(add_workspace_button).to_be_visible()
    add_workspace_button.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 3: Fill in the workspace name, pick a non-default source branch, and
    # type a custom branch name. The test repo is checked out on "testing", so
    # "main" is a non-current branch the user can deliberately select.
    draft_workspace_name = "Branch State Workspace"
    custom_branch_name = "my-custom-branch-name"

    workspace_name_input = add_ws_page.get_workspace_name_input()
    workspace_name_input.fill(draft_workspace_name)

    add_ws_page.select_branch("main")
    branch_selector = add_ws_page.get_branch_selector()
    expect(branch_selector).to_contain_text("main")

    branch_name_input = add_ws_page.get_branch_name_input()
    branch_name_input.fill(custom_branch_name)
    expect(branch_name_input).to_have_value(custom_branch_name)

    # Step 4: Navigate away by clicking on the existing workspace tab.
    workspace_tab = add_ws_page.get_workspace_tabs().first
    expect(workspace_tab).to_be_visible()
    workspace_tab.click()

    # Confirm we navigated away — the chat panel of the existing workspace should appear.
    task_page = PlaywrightTaskPage(page=page)
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)

    # Step 5: Navigate back to the Add Workspace page via the "Open Workspace" tab.
    # Use .last because a stale "new workspace" tab may persist from previous test
    # cleanup when running on a shared instance with xdist reordering.
    open_workspace_tab = add_ws_page.get_add_workspace_tabs().last
    expect(open_workspace_tab).to_be_visible()
    open_workspace_tab.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 6: Verify the source branch and branch name survived the round trip.
    # The workspace name is also checked to confirm the documented asymmetry
    # (name persisted; branch/source did not) is fully resolved.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    expect(workspace_name_input).to_have_value(draft_workspace_name)

    branch_name_input = add_ws_page.get_branch_name_input()
    expect(branch_name_input).to_have_value(custom_branch_name)

    branch_selector = add_ws_page.get_branch_selector()
    expect(branch_selector).to_contain_text("main")


@user_story("to draft multiple workspaces in parallel, like browser tabs")
def test_multiple_new_workspace_tabs_with_independent_drafts(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Opening multiple new workspace tabs should give each its own independent draft state.

    Steps:
    1. On the initial Add Workspace page, fill in a workspace name
    2. Click the "+" button to open a second new workspace tab
    3. Verify the second tab has an empty form (independent of the first)
    4. Fill in a different workspace name on the second tab
    5. Click the first "Open Workspace" tab to switch back
    6. Verify the first tab still has its original draft content
    7. Click the second "Open Workspace" tab to switch back
    8. Verify the second tab still has its draft content
    """
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    # Step 1: We start on the Add Workspace page. Fill in workspace name.
    # Record the initial tab count so we can navigate relative to it —
    # a stale "new workspace" tab may survive from previous test cleanup.
    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    all_tabs = add_ws_page.get_add_workspace_tabs()
    initial_tab_count = all_tabs.count()
    first_tab_index = initial_tab_count - 1

    first_workspace_name = "First Draft Workspace"

    workspace_name_input = add_ws_page.get_workspace_name_input()
    workspace_name_input.fill(first_workspace_name)

    # Step 2: Click the "+" button to open a second new workspace tab.
    add_workspace_button = add_ws_page.get_add_workspace_button()
    expect(add_workspace_button).to_be_visible()
    add_workspace_button.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 3: Verify the second tab has an empty form.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    expect(workspace_name_input).to_have_value("")

    # Step 4: Fill in a different workspace name on the second tab.
    second_workspace_name = "Second Draft Workspace"
    workspace_name_input.fill(second_workspace_name)

    # Step 5: Click the first tab we created to switch back.
    open_workspace_tabs = add_ws_page.get_add_workspace_tabs()
    open_workspace_tabs.nth(first_tab_index).click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 6: Verify the first tab still has its original draft content.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    expect(workspace_name_input).to_have_value(first_workspace_name)

    # Step 7: Click the second (last) "Open Workspace" tab to switch back.
    open_workspace_tabs = add_ws_page.get_add_workspace_tabs()
    open_workspace_tabs.last.click()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Step 8: Verify the second tab still has its draft content.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    expect(workspace_name_input).to_have_value(second_workspace_name)


@user_story("to have a seamless tab transition when creating a workspace from a new-workspace tab")
def test_no_extra_tab_flash_when_creating_workspace_from_new_tab(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Creating a workspace from a new-workspace tab must not briefly show an extra tab.

    Uses a MutationObserver on the tab bar to record the maximum tab count
    seen across all DOM mutations between clicking submit and landing on
    the workspace page.
    """
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    # We start on the Add Workspace page with a single "Open Workspace" tab.
    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_visible()

    # Fill in the workspace name.
    workspace_name_input = add_ws_page.get_workspace_name_input()
    workspace_name_input.fill("Flash Test Workspace")

    # Record baseline tab count and install a MutationObserver.
    page.evaluate("""() => {
        const tablist = document.querySelector('[role="tablist"]');
        const countTabs = () => tablist.querySelectorAll('[role="tab"]').length;
        window.__tabFlashTest = { maxTabCount: countTabs(), baseline: countTabs() };
        const observer = new MutationObserver(() => {
            const count = countTabs();
            if (count > window.__tabFlashTest.maxTabCount) {
                window.__tabFlashTest.maxTabCount = count;
            }
        });
        observer.observe(tablist, { childList: true, subtree: true });
        window.__tabFlashTestObserver = observer;
    }""")

    # Pick a plain terminal agent so the terminal panel renders in CI, then submit.
    add_ws_page.select_terminal_agent_type()
    expect(submit_button).to_be_enabled()
    submit_button.click()

    # Wait for the workspace page to load (terminal panel visible).
    task_page = PlaywrightTaskPage(page=page)
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)

    # Disconnect observer and read results.
    result = page.evaluate("""() => {
        window.__tabFlashTestObserver.disconnect();
        return window.__tabFlashTest;
    }""")

    baseline = result["baseline"]
    max_tab_count = result["maxTabCount"]

    assert max_tab_count <= baseline, (
        f"Tab count briefly increased from {baseline} to {max_tab_count} during "
        + "workspace creation — the pseudo-tab was not atomically replaced"
    )


@user_story("to create a workspace with only a name")
def test_create_workspace_without_prompt(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Creating a workspace with only a name should produce a ready terminal agent.

    Steps:
    1. Create a workspace with only a name (the Add Workspace form has no prompt)
    2. Verify the terminal panel appears (the agent is ready)
    """
    page = sculptor_instance_.page

    # Step 1: Create a workspace with only a name.
    task_page = start_task_and_wait_for_ready(
        sculptor_page=page,
        workspace_name="Prompt-less Workspace",
    )

    # Step 2: Verify the terminal panel appears (the agent is ready).
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)


@user_story("to type into the agent terminal right after creating a workspace")
def test_agent_terminal_ready_after_workspace_creation(
    sculptor_instance_: SculptorInstance,
) -> None:
    """After creating a workspace, the agent terminal input should be ready to type into.

    The agent terminal deliberately does not steal focus on initial mount, so we
    assert the input textarea is attached (the user can click and type) rather
    than asserting it is focused.

    Covers two scenarios:
    1. Creating the very first workspace (initial page load)
    2. Creating a second workspace via the "+" button (switching from an existing workspace)
    """
    page = sculptor_instance_.page

    # Scenario 1: Create the first workspace.
    start_task_and_wait_for_ready(
        sculptor_page=page,
        workspace_name="First Workspace",
    )
    expect(get_agent_terminal_textarea(page)).to_be_attached()

    # Scenario 2: Create a second workspace via the "+" button.
    start_task_and_wait_for_ready(
        sculptor_page=page,
        workspace_name="Second Workspace",
    )
    expect(get_agent_terminal_textarea(page)).to_be_attached()


@user_story("to regain keyboard control by pressing arrow keys when nothing is focused")
def test_arrow_down_focuses_name_input_when_nothing_focused(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Pressing ArrowDown when no element has focus should focus the workspace name input."""
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    name_input = add_ws_page.get_workspace_name_input()
    expect(name_input).to_be_visible()

    blur_page(page)
    expect(name_input).not_to_be_focused()

    page.keyboard.press("ArrowDown")
    expect(name_input).to_be_focused()


@user_story("to regain keyboard control by pressing arrow keys when nothing is focused")
def test_arrow_up_focuses_name_input_when_nothing_focused(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Pressing ArrowUp when no element has focus should focus the workspace name input."""
    page = sculptor_instance_.page
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    name_input = add_ws_page.get_workspace_name_input()
    expect(name_input).to_be_visible()

    blur_page(page)
    expect(name_input).not_to_be_focused()

    page.keyboard.press("ArrowUp")
    expect(name_input).to_be_focused()


@user_story("to create a workspace by pressing Cmd+Enter while the workspace name input is focused")
def test_cmd_enter_in_workspace_name_creates_workspace(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Pressing Cmd+Enter while focus is in the workspace name input should create the workspace."""
    page = sculptor_instance_.page
    mod_key = get_playwright_modifier_key()
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    name_input = add_ws_page.get_workspace_name_input()
    expect(name_input).to_be_visible()

    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_enabled()

    name_input.fill("Cmd Enter Test")
    # Pick a plain terminal agent so the terminal panel renders in CI. The menu
    # interaction moves focus, so we re-focus the name input before Cmd+Enter.
    add_ws_page.select_terminal_agent_type()
    name_input.click()
    expect(name_input).to_be_focused()

    page.keyboard.press(f"{mod_key}+Enter")

    task_page = PlaywrightTaskPage(page=page)
    expect(task_page.get_terminal_panel()).to_be_visible(timeout=60_000)


@user_story("to submit a repo path with Cmd+Enter without the New Workspace being created")
def test_cmd_enter_in_repo_autocomplete_does_not_create_workspace(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Cmd+Enter in the repo path autocomplete must not also create the workspace.

    Regression test for SCU-1450. On the New Workspace page the user opens the
    "Open New Repo" dialog and presses Cmd+Enter to submit a path in the repo
    autocomplete (the dropdown covers the Add button, so Cmd+Enter is the
    shortcut to submit). That keystroke used to bubble up to NewWorkspaceForm's
    document-level Cmd+Enter handler, which immediately created the workspace
    and navigated away — skipping the chance to name the branch/workspace.

    The autocomplete owns that keystroke; it must not leak to the outer form.
    """
    page = sculptor_instance_.page
    mod_key = get_playwright_modifier_key()
    add_ws_page = PlaywrightAddWorkspacePage(page=page)

    # Wait until the form would actually submit on Cmd+Enter: a project is
    # selected and the branch-name preview has loaded (so submit is enabled).
    # This guarantees the bug reproduces if the keystroke leaks through.
    submit_button = add_ws_page.get_submit_button()
    expect(submit_button).to_be_enabled()

    # Open the "Open New Repo" dialog from the repo selector.
    add_repo_dialog = add_ws_page.open_add_repo_dialog()
    path_input = add_repo_dialog.get_path_input()

    # Type a path and confirm the input holds it. Cmd+Enter submits the path
    # regardless of dropdown state, so this does not depend on the host home
    # directory listing any subdirectories (which would flake on empty-home CI).
    path_input.fill("~/")
    expect(path_input).to_have_value("~/")

    # Submit the path with Cmd+Enter.
    path_input.press(f"{mod_key}+Enter")

    # Desired behaviour: the workspace is NOT created. Wait long enough for the
    # (buggy) workspace-creation path to navigate to the terminal panel — when
    # the bug is present it does so within a few seconds — then conclude it did
    # not. The 10s is a deliberate bounded wait for a negative assertion (the
    # panel is expected to never appear), not a tightened positive timeout.
    terminal_panel = page.get_by_test_id(ElementIDs.AGENT_TERMINAL_PANEL)
    try:
        expect(terminal_panel).to_be_visible(timeout=10_000)
    except AssertionError:
        pass  # expected: no workspace created, so the terminal panel never appears
    else:
        pytest.fail(
            "Cmd+Enter in the repo autocomplete created the workspace and "
            + "navigated to the workspace (SCU-1450 regression)"
        )

    # Confirm we are still on the New Workspace page (no navigation happened).
    expect(terminal_panel).not_to_be_visible()


def _extract_workspace_id(url: str) -> str:
    """Extract the workspace ID from a Sculptor URL (format: /ws/{workspaceID}/agent/...)."""
    match = re.search(r"/ws/([a-zA-Z0-9_-]+)/", url)
    if not match:
        raise ValueError(f"Could not extract workspace ID from URL: {url}")
    return match.group(1)


@user_story("to have workspaces cleaned up when I delete a project")
def test_deleting_project_also_deletes_its_workspaces(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """Deleting a project should also soft-delete all workspaces belonging to it."""
    with sculptor_instance_factory_.spawn_instance() as sculptor_instance:
        page = sculptor_instance.page

        start_task_and_wait_for_ready(
            sculptor_page=page,
            prompt="Setup task",
            workspace_name="Workspace To Delete",
        )

        workspace_id = _extract_workspace_id(page.url)
        base_url = sculptor_instance.backend_api_url.rstrip("/")

        # The workspace's agents endpoint routes through `_get_workspace_or_404`,
        # so it serves a real 200/404 (a deleted workspace 404s) rather than the
        # SPA catch-all — making it a reliable existence/deletion probe.
        get_response = page.request.get(f"{base_url}/api/v1/workspaces/{workspace_id}/agents")
        assert get_response.ok, f"Expected workspace {workspace_id} to exist, got status {get_response.status}"

        settings_page = navigate_to_settings_page(page=page)
        repos_section = settings_page.click_on_repositories()

        # Delete the first repo row (the original project).
        repos_section.remove_first_repo()

        get_response = page.request.get(f"{base_url}/api/v1/workspaces/{workspace_id}/agents")
        assert get_response.status == 404, (
            f"Expected workspace {workspace_id} to be deleted (404) after project deletion, but got status {get_response.status}"
        )
