"""Integration tests for read/unread status indicators on agent and workspace tabs.

These tests verify:
- Agent tabs show read (grey) after the user navigates to that agent
- Workspace tabs derive unread state from their agents
- The focused agent stays read as it receives updates
- Read/unread status persists across server restarts

Agents are driven by the fake registered terminal agent. A focused terminal
agent receives updates by emitting lifecycle signals (busy/idle/files-changed)
via send_fake_agent_command, the terminal-agent equivalent of a chat response.
"""

from playwright.sync_api import expect

from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.fake_terminal_agent import add_registered_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story


@user_story("to see my focused agents stay read within a workspace")
def test_focused_agents_stay_read_within_workspace(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Create a workspace with two agents, verify read transitions on agent tabs.

    Flow:
    1. Create workspace with agent 1 (a terminal agent; read while viewing it)
    2. Add agent 2 (auto-navigates to agent 2; read while viewing it)
    3. Drive agent 2 (focused) — it stays read as its updatedAt advances
    4. Switch to agent 1 — agent 2 had no updates after we left → stays read
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Create first agent in a new workspace (a terminal agent).
    task_page = start_task_and_wait_for_ready(
        page, agent_type="terminal", model_name=None, workspace_name="Read Test WS"
    )

    # Agent 1 should be read (we're viewing it and it is ready).
    agent_tab_bar = task_page.get_agent_tab_bar()
    agent_tabs = agent_tab_bar.get_agent_tabs()
    expect(agent_tabs).to_have_count(1)
    expect(agent_tabs.first).to_have_attribute("data-dot-status", "read")

    # Workspace tab should also be read (only agent is read).
    workspace_tabs = task_page.get_workspace_tabs()
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")

    # Add a second agent (a registered fake terminal agent; auto-navigates to it).
    add_registered_fake_terminal_agent(page, agents_dir)
    expect(agent_tabs).to_have_count(2)

    # Drive agent 2 (focused) so its updatedAt advances; it should stay read.
    send_fake_agent_command_and_wait(agents_dir, bash("echo agent2 > agent2.txt"))
    expect(agent_tabs.last).to_have_attribute("data-dot-status", "read")

    # Switch to agent 1 — we leave agent 2 behind.
    agent_tabs.first.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    # Agent 1 should be read (we just navigated to it).
    expect(agent_tabs.first).to_have_attribute("data-dot-status", "read")

    # Agent 2 should still be read — no new updates happened after we left.
    expect(agent_tabs.last).to_have_attribute("data-dot-status", "read")


@user_story("to see which workspaces have unseen agent updates")
def test_unread_workspace_indicator_across_workspaces(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Create two workspaces and verify the workspace tab unread indicator.

    Flow:
    1. Create workspace A with a terminal agent (read while viewing)
    2. Create workspace B (navigates away from A)
    3. Both workspaces should be read (A's agent was seen before leaving)
    4. Navigate back to workspace A — still read
    5. Navigate to workspace B — both stay read
    """
    page = sculptor_instance_.page

    # Create workspace A with a terminal agent.
    task_page_a = start_task_and_wait_for_ready(
        page, agent_type="terminal", model_name=None, workspace_name="Workspace A"
    )

    workspace_tabs = task_page_a.get_workspace_tabs()
    expect(workspace_tabs).to_have_count(1)
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")

    # Create workspace B (navigates away from A).
    start_task_and_wait_for_ready(page, agent_type="terminal", model_name=None, workspace_name="Workspace B")

    expect(workspace_tabs).to_have_count(2)

    # Both workspaces should be read.
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")
    expect(workspace_tabs.last).to_have_attribute("data-has-unread", "false")

    # Navigate back to workspace A — its agent was seen, so it stays read.
    workspace_tabs.first.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")

    # Now navigate to workspace B — both stay read.
    workspace_tabs.last.click()
    expect(get_agent_terminal_panel(page)).to_be_visible()

    # Both workspaces should be read.
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")
    expect(workspace_tabs.last).to_have_attribute("data-has-unread", "false")


@user_story("to see my focused agent stay read as it receives updates")
def test_focused_agent_stays_read_while_receiving_updates(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Verify that the agent the user is currently viewing stays read.

    The useMarkRead hook should re-fire (debounced) whenever updatedAt
    changes while the user is viewing the agent, keeping it read.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Create a workspace, then add a registered fake terminal agent we can drive.
    task_page = start_task_and_wait_for_ready(
        page, agent_type="terminal", model_name=None, workspace_name="Focused WS"
    )
    add_registered_fake_terminal_agent(page, agents_dir)

    agent_tab_bar = task_page.get_agent_tab_bar()
    agent_tabs = agent_tab_bar.get_agent_tabs()
    expect(agent_tabs).to_have_count(2)

    # Drive a follow-up while staying on this agent; useMarkRead re-fires on the
    # updatedAt change, keeping the focused agent read.
    send_fake_agent_command_and_wait(agents_dir, bash("echo follow1 > follow1.txt"))

    # Agent should be read (useMarkRead re-fires on updatedAt change).
    expect(agent_tabs.last).to_have_attribute("data-dot-status", "read")

    # Drive another follow-up.
    send_fake_agent_command_and_wait(agents_dir, bash("echo follow2 > follow2.txt"))

    # Agent should still be read.
    expect(agent_tabs.last).to_have_attribute("data-dot-status", "read")

    # Workspace should also show no unread.
    workspace_tabs = task_page.get_workspace_tabs()
    expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")


@user_story("to have my read/unread agent status persist after restarting Sculptor")
def test_read_status_persists_after_restart(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """Agent read status should survive a full server restart.

    Regression test for a bug where all agents/workspaces showed as unread on
    startup. CodingAgentTaskView.updated_at was computed from the last message
    of any type, including bookkeeping messages that are persisted to the DB
    with timestamps lagging behind the frontend's mark_read call. On restart
    these stale bookkeeping timestamps became updated_at > last_read_at, making
    previously-read tasks appear unread.

    Steps:
    1. Start Sculptor, create a workspace with a terminal agent, let it settle
    2. Verify the workspace shows as read (user is viewing it)
    3. Wait for the debounced mark_read to fire and persist to the database
    4. Restart Sculptor (full server restart against the same database)
    5. Verify the workspace tab still shows as read WITHOUT clicking on it
       (clicking would trigger useMarkRead, masking the persistence bug)
    """
    # === First instance: create agent and mark as read ===
    with sculptor_instance_factory_.spawn_instance() as instance:
        page = instance.page

        # Step 1: Create a terminal agent and wait for it to be ready.
        task_page = start_task_and_wait_for_ready(
            page, agent_type="terminal", model_name=None, workspace_name="Persist WS"
        )

        # Step 2: Verify the workspace and agent show as read.
        agent_tab_bar = task_page.get_agent_tab_bar()
        agent_tabs = agent_tab_bar.get_agent_tabs()
        expect(agent_tabs).to_have_count(1)
        expect(agent_tabs.first).to_have_attribute("data-dot-status", "read")

        workspace_tabs = task_page.get_workspace_tabs()
        expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")

        # Step 3: Give time for the debounced mark_read to fire and persist.
        page.wait_for_timeout(2000)

    # === Second instance: verify read status persists after restart ===
    with sculptor_instance_factory_.spawn_instance() as instance:
        page = instance.page

        # Step 4: Wait for the workspace tab to appear (server has restarted).
        layout_page = PlaywrightTaskPage(page=page)
        workspace_tabs = layout_page.get_workspace_tabs()
        expect(workspace_tabs.first).to_be_visible()

        # Step 5: Check workspace tab shows read WITHOUT clicking on it.
        # Clicking would navigate into the workspace, mount the agent panel,
        # and trigger useMarkRead — which would re-mark the agent as read,
        # masking the persistence bug.
        expect(workspace_tabs.first).to_have_attribute("data-has-unread", "false")
