"""Scenario: Panel visibility toggle render cascade.

Measures re-renders triggered when the user opens and closes side panels
via the sidebar icon buttons. Toggling panel visibility changes
zoneVisibilityAtom which DockingLayout subscribes to — this should NOT
cause the agent terminal panel or diff content to re-render.
"""

import time

DESCRIPTION = "Panel visibility toggle (open/close side panel)"

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
    "AgentTabs",
    "SidebarIcon",
]

# The Actions panel lives in the top-right zone and is closed by default,
# so toggling it exercises a clean open/close cycle of the right side.
# SidebarIcon renders data-panel-icon="files" | "actions" | "terminal".
_RIGHT_PANEL_ICON = '[data-panel-icon="actions"]'


def setup(page, base_url, workspace_id, task_id):
    page.goto(f"{base_url}/#/ws/{workspace_id}/agent/{task_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(5)
    # Ensure the right panel is closed to start from a consistent state
    # (it is closed by default; close it if a persisted layout opened it).
    right_panel_area = page.locator('[data-testid="PANEL_RIGHT_AREA"]')
    if right_panel_area.count() > 0 and right_panel_area.is_visible():
        icons = page.locator(_RIGHT_PANEL_ICON).all()
        if icons:
            icons[0].click()
            time.sleep(0.5)


def action(page):
    # Click the Actions panel's sidebar icon to toggle the right panel
    # open and closed twice.
    icons = page.locator(_RIGHT_PANEL_ICON).all()
    if not icons:
        # Fall back: any panel icon button
        icons = page.locator("[data-panel-icon]").all()

    if not icons:
        raise RuntimeError("No sidebar panel icons found")

    icon = icons[0]

    # Open the panel
    icon.click()
    time.sleep(0.3)

    # Close the panel
    icon.click()
    time.sleep(0.3)

    # Open again
    icon.click()
    time.sleep(0.3)
