"""Regression test: Agent count in diagnostics overlay should match settings page.

Bug: The diagnostics overlay (VersionPopover) shows "Active Agents" from the
health check endpoint, which uses get_active_tasks(). This query only filtered
is_deleted but not is_deleting, so tasks in the process of being deleted were
still counted. Meanwhile, the settings page agent count comes from the frontend
task state (via WebSocket), which uses get_tasks_for_user() — a query that
filters both is_deleted and is_deleting. This caused the diagnostics count to
be higher than the settings page count whenever agents were being deleted.

Root cause: get_active_tasks() in sql_implementation.py was missing a
.where(is_deleting.is_(False)) filter that get_tasks_for_user() already had.

The agent here is a fake registered terminal agent held busy on a sentinel, so
it is in a running (cancellable) state when deleted — exercising the is_deleting
window the bug lived in.
"""

import re

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import release_fake_agent_wait
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.playwright_utils import navigate_to_settings_page
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _get_health_check_active_task_count(page: Page, base_url: str) -> int:
    """Call the health check API and return the activeTaskCount."""
    response = page.request.get(f"{base_url}/api/v1/health")
    assert response.ok, f"Health check failed: {response.status}"
    data = response.json()
    return int(data["activeTaskCount"])


def _get_settings_total_agent_count(page: Page) -> int:
    """Navigate to settings, read the agent count from each project row, and return the total."""
    settings_page = navigate_to_settings_page(page=page)
    # Wait for the settings page to be fully rendered before interacting
    expect(settings_page.get_settings_page_locator()).to_be_visible()
    repos_settings = settings_page.click_on_repositories()

    repo_rows = repos_settings.get_repo_rows()
    expect(repo_rows.first).to_be_visible()

    total = 0
    for row in repo_rows.all():
        # The row text contains e.g. "3 agents" or "1 agent"
        row_text = row.inner_text()
        match = re.search(r"(\d+)\s+agents?", row_text)
        if match:
            total += int(match.group(1))
    return total


@user_story("to see consistent agent counts between the settings page and diagnostics overlay")
def test_agent_count_matches_between_settings_and_diagnostics(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Agent count in diagnostics overlay should match the settings page total.

    Steps:
    1. Create a workspace with a fake terminal agent held busy (running)
    2. Delete the running agent via the close button
    3. Read the health check API's activeTaskCount
    4. Read the settings page's total agent count across all project rows
    5. Assert they match
    """
    page = sculptor_instance_.page
    base_url = sculptor_instance_.backend_api_url
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Create a workspace whose first agent is a registered fake terminal agent.
    _, agent_tab_bar = start_fake_terminal_agent(page, agents_dir, workspace_name="Agent Count Test WS")

    # Hold the terminal agent busy (running, cancellable) by blocking on a
    # sentinel. Write no file so the agent's worktree stays clean for teardown.
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first
    send_fake_agent_command(
        agents_dir,
        multi_step([wait_for_file("release.sentinel")]),
    )
    expect(terminal_tab).to_have_attribute("data-dot-status", "running", timeout=30_000)

    # Save the URL before deletion so we can detect when the new agent loads
    old_url = page.url

    # Delete the running terminal agent via the close button on the agent tab.
    agent_tabs = agent_tab_bar.get_agent_tabs()
    # The workspace has the chat first agent plus the fake terminal agent; delete
    # the fake terminal agent (the held-busy one) specifically.
    terminal_index = None
    for index in range(agent_tabs.count()):
        if agent_tabs.nth(index).get_attribute("data-dot-status") == "running":
            terminal_index = index
            break
    assert terminal_index is not None, "expected to find the held-busy terminal agent tab"
    agent_tab_bar.delete_agent_via_close_button(terminal_index)

    # Wait for the deletion dialog to close
    expect(agent_tab_bar.get_delete_confirmation_dialog()).to_be_hidden()

    # Release the sentinel so the runner can exit cleanly during teardown.
    release_fake_agent_wait(agents_dir, "release.sentinel")

    # After deletion the frontend may navigate to the remaining agent. Wait for
    # the URL to change, proving the post-deletion navigation completed.
    page.wait_for_url(lambda url: url != old_url)

    # Now compare: the health check API count should match the settings page count.
    # With the bug, the health check would still count the is_deleting task,
    # while the settings page (fed by the frontend stream) would not.
    health_check_count = _get_health_check_active_task_count(page, base_url)
    settings_count = _get_settings_total_agent_count(page)

    assert health_check_count == settings_count, (
        f"Agent count mismatch: health check API reports {health_check_count} active agents, "
        f"but settings page shows {settings_count}. "
        f"This indicates get_active_tasks() is not filtering is_deleting tasks."
    )
