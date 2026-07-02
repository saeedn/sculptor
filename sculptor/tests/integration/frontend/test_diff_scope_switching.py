"""Integration tests for switching between diff scopes.

Tests verify that the scope picker toggles correctly and the diff content
updates when switching between scopes.
"""

import re

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _extract_workspace_id(url: str) -> str:
    """Extract the workspace ID from a Sculptor URL (format: /ws/{workspaceID}/agent/...)."""
    match = re.search(r"/ws/([a-zA-Z0-9_-]+)/", url)
    if not match:
        raise ValueError(f"Could not extract workspace ID from URL: {url}")
    return match.group(1)


@user_story("to switch diff scope and see the toggle update")
def test_scope_switch_toggles_active_scope(sculptor_instance_: SculptorInstance) -> None:
    """Switching scope should update the active scope button and diff content.

    Start on All scope (the default), switch to Uncommitted scope,
    then switch back to All and verify content is restored.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(agents_dir, write_file("hello.py", "print('hello')\n"))

    # Open Changes tab
    task_page.activate_changes_panel()

    changes_panel = task_page.get_changes_panel()
    expect(changes_panel).to_be_visible()

    # Verify scope picker starts on All (the default)
    scope_picker = changes_panel.get_scope_picker()
    expect(scope_picker).to_be_visible()

    scope_all = changes_panel.get_scope_all()
    expect(scope_all).to_have_attribute("data-state", "on")

    # The file should be visible in the changes tree
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    expect(changes_tree.get_tree_rows().filter(has_text="hello.py")).to_be_visible()

    # Switch to Uncommitted scope
    scope_uncommitted = changes_panel.get_scope_uncommitted()
    scope_uncommitted.click()
    expect(scope_uncommitted).to_have_attribute("data-state", "on")

    # Switch back to All — the file should still be listed
    scope_all.click()
    expect(scope_all).to_have_attribute("data-state", "on")
    expect(changes_tree.get_tree_rows().filter(has_text="hello.py")).to_be_visible()


@user_story("to see the Changes tab update when the target branch is changed")
def test_changes_tab_updates_on_target_branch_change(sculptor_instance_: SculptorInstance) -> None:
    """Changing the target branch should trigger a diff refresh so the Changes
    tab All scope reflects the new fork-point.

    When the target branch is changed to the same branch we just pushed (which
    has the same commits as HEAD), the All scope should show no changed files
    since there is no divergence.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(
        agents_dir,
        multi_step(
            [
                bash("git checkout -b feature-refresh-test"),
                write_file("first.py", "x = 1\n"),
                bash("git add -A && git commit -m 'Add first.py'"),
                write_file("second.py", "y = 2\n"),
                bash("git add -A && git commit -m 'Add second.py'"),
                bash("git push origin feature-refresh-test"),
            ]
        ),
    )

    # Open Changes tab and switch to All scope
    task_page.activate_changes_panel()

    changes_panel = task_page.get_changes_panel()
    scope_all = changes_panel.get_scope_all()
    expect(scope_all).to_be_visible()
    scope_all.click()

    # Initially (target = origin/main), both files should be visible as changes
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows.filter(has_text="first.py")).to_be_visible()
    expect(tree_rows.filter(has_text="second.py")).to_be_visible()

    # Change target branch to origin/feature-refresh-test (same as HEAD)
    workspace_id = _extract_workspace_id(page.url)
    base_url = sculptor_instance_.backend_api_url.rstrip("/")
    response = page.request.patch(
        f"{base_url}/api/v1/workspaces/{workspace_id}",
        data={"target_branch": "origin/feature-refresh-test"},
    )
    assert response.ok, f"Failed to update target branch: {response.status}"

    # The Changes tab should refresh — since fork-point = HEAD, no files changed
    # Wait for the files to disappear
    expect(tree_rows.filter(has_text="first.py")).to_be_hidden()
    expect(tree_rows.filter(has_text="second.py")).to_be_hidden()
