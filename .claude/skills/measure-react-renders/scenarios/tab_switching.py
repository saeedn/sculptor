"""Scenario: Workspace tab switching render cascade.

Measures re-renders when the user clicks between workspace tabs in the
WorkspaceTabs component. Tab switching navigates to a different workspace URL
and changes the active agent, causing WorkspacePage to mount new content.

This tests whether tab switching causes excessive re-renders in components
that should be stable across tab changes (sidebars, DockingLayout structure).
"""

import time

DESCRIPTION = "Workspace tab switching"

TARGET_COMPONENTS = [
    "WorkspacePage",
    "WorkspacePageContent",
    "DockingLayout",
    "LeftSidebar",
    "LeftSidebarInner",
    "RightSidebar",
    "RightSidebarInner",
    "ZoneContent",
    "ZoneContentInner",
    "DiffSplitContainer",
    "ChatPanelContent",
    "AgentTerminalPanel",
    "WorkspaceBanner",
    "WorkspaceTabs",
    "TopBar",
]


def _create_second_workspace(page, base_url):
    """Create a second workspace + terminal agent via the API.

    Returns {"workspaceId": ..., "agentId": ...} or None on failure.
    """
    # Use fetch() inside the page to call the API directly
    result = page.evaluate("""async () => {
        const projectsRes = await fetch('/api/v1/projects');
        const projects = await projectsRes.json();
        const projectId = projects[0]?.objectId;
        if (!projectId) return null;
        const branchRes = await fetch(`/api/v1/projects/${projectId}/current_branch`);
        const sourceBranch = (await branchRes.json())?.currentBranch;
        if (!sourceBranch) return null;
        const wsRes = await fetch('/api/v1/workspaces', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                projectId,
                sourceBranch,
                requestedBranchName: `perf-tab-switching-${Date.now()}`,
                description: 'Tab switching perf scenario'
            })
        });
        if (!wsRes.ok) return null;
        const workspace = await wsRes.json();
        const agentRes = await fetch(`/api/v1/workspaces/${workspace.objectId}/agents`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ agentType: 'terminal' })
        });
        if (!agentRes.ok) return null;
        const agent = await agentRes.json();
        return { workspaceId: workspace.objectId, agentId: agent.id };
    }""")
    return result


def setup(page, base_url, workspace_id, task_id):
    page.goto(f"{base_url}/#/ws/{workspace_id}/agent/{task_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    # Create a second workspace so we have two tabs to switch between
    second = _create_second_workspace(page, base_url)
    if second:
        page.goto(f"{base_url}/#/ws/{second['workspaceId']}/agent/{second['agentId']}")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        # Navigate back to the first workspace
        page.goto(f"{base_url}/#/ws/{workspace_id}/agent/{task_id}")
        page.wait_for_load_state("networkidle")
        time.sleep(2)


def action(page):
    # Find workspace tab buttons in the tab bar. SortableTab renders each
    # workspace tab with data-testid="WORKSPACE_TAB" (ElementIds.WORKSPACE_TAB).
    tabs = page.locator('[data-testid="WORKSPACE_TAB"]').all()

    if len(tabs) < 2:
        # Fall back to any tab-like elements in the top bar
        tabs = page.locator('[role="tab"]').all()

    if len(tabs) < 2:
        # Last resort: navigate directly via URL to simulate a tab switch
        result = page.evaluate("""async () => {
            const res = await fetch('/api/v1/projects');
            const projects = await res.json();
            const projectId = projects[0]?.objectId;
            const wsRes = await fetch(`/api/v1/projects/${projectId}/workspaces`);
            const workspaces = await wsRes.json();
            return workspaces.map(ws => ({ id: ws.objectId }));
        }""")
        if result and len(result) >= 2:
            ws_id_2 = result[1]["id"]
            # Simulate tab switch via navigation
            page.evaluate(f"window.location.hash = '#/ws/{ws_id_2}'")
            time.sleep(0.5)
            # Navigate back
            page.go_back()
            time.sleep(0.5)
        return

    # Click second tab
    tabs[1].click()
    time.sleep(0.4)

    # Click first tab
    tabs[0].click()
    time.sleep(0.4)

    # Click second tab again
    tabs[1].click()
    time.sleep(0.4)
