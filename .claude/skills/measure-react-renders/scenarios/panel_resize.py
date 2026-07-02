"""Scenario: Panel resize render cascade.

Measures re-renders triggered by resizing the panel divider between the
center content area and the side/bottom panels via keyboard arrow keys.

The default workspace layout opens the file browser (top-left) and terminal
(bottom) panels, so resize handles are present. If none are found we click a
sidebar panel icon to open one, then resize 5 steps left and 5 right.
"""

import time

DESCRIPTION = "Panel resize render cascade"

TARGET_COMPONENTS = [
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
    "DiffSummary",
    "FileBrowserPanel",
]


def _open_side_panel(page):
    """Ensure at least one panel is open so a resize handle exists."""
    # Check if any resize handle already exists
    handles = page.locator('[role="separator"]').all()
    if handles:
        return

    # Click a sidebar panel icon to open a panel. SidebarIcon renders
    # data-panel-icon="files" | "actions" | "terminal".
    file_icon = page.locator('[data-panel-icon="files"]')
    if file_icon.count() > 0:
        file_icon.first.click()
        time.sleep(0.5)
        return

    # Fallback: any panel icon
    sidebar_icons = page.locator("[data-panel-icon]").all()
    if sidebar_icons:
        sidebar_icons[0].click()
        time.sleep(0.5)


def setup(page, base_url, workspace_id, task_id):
    page.goto(f"{base_url}/#/ws/{workspace_id}/agent/{task_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(5)
    _open_side_panel(page)
    # Wait for panel to mount
    time.sleep(0.5)


def action(page):
    handles = page.locator('[role="separator"]').all()
    if not handles:
        # Try opening a panel at action time if setup didn't work
        _open_side_panel(page)
        time.sleep(0.5)
        handles = page.locator('[role="separator"]').all()

    if not handles:
        raise RuntimeError(
            "No resize handles found. Ensure a side panel is visible."
        )

    # Use the first separator (the left-panel/center divider by default)
    handle = handles[0]
    handle.focus()
    time.sleep(0.3)
    for _ in range(5):
        page.keyboard.press("ArrowLeft")
        time.sleep(0.15)
    for _ in range(5):
        page.keyboard.press("ArrowRight")
        time.sleep(0.15)
