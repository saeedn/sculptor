"""Panel zone layout element POM for integration tests.

Provides a POM for interacting with the panel zone layout system:
sidebar icons, zone containers, context menus, and resize handles.
"""

from playwright.sync_api import Locator
from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.constants import ElementIDs


class PlaywrightPanelZonesElement:
    """POM for the panel zone layout: sidebar icons, zone containers,
    context menus, and resize handles."""

    def __init__(self, page: Page) -> None:
        self._page = page

    def get_actions_icon(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_ICON_ACTIONS)

    def get_files_icon(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_ICON_FILES)

    def get_terminal_icon(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_ICON_TERMINAL)

    def get_top_right_zone(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_TOP_RIGHT)

    def get_bottom_right_zone(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_BOTTOM_RIGHT)

    def get_right_area(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.PANEL_RIGHT_AREA)

    def get_right_resize_handle(self) -> Locator:
        return self.get_right_area().get_by_test_id(ElementIDs.PANEL_RIGHT_RESIZE_HANDLE)

    def get_side_toggle_left(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.SIDE_TOGGLE_LEFT)

    def get_side_toggle_bottom(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.SIDE_TOGGLE_BOTTOM)

    def get_side_toggle_right(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.SIDE_TOGGLE_RIGHT)

    def get_focus_mode_button(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.FOCUS_MODE_BUTTON)

    def get_file_browser_panel(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.FILE_BROWSER_PANEL)

    def activate_plugin_panel(self, plugin_id: str) -> None:
        """Click a plugin-contributed panel's sidebar icon to make it the active
        panel in its zone.

        Plugin panels render `data-panel-icon=<id>` with no ElementIDs testid
        (unlike built-in panels, which are in PANEL_ICON_TEST_IDS), so they're
        located by that attribute.
        """
        icon = self._page.locator(f'[data-panel-icon="{plugin_id}"]')
        expect(icon).to_be_visible()
        icon.click()
