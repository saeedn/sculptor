from playwright.sync_api import Locator
from playwright.sync_api import Page

from sculptor.constants import ElementIDs
from sculptor.testing.elements.base import PlaywrightIntegrationTestElement


class PlaywrightToastElement(PlaywrightIntegrationTestElement):
    """Page Object Model for toast notifications."""

    def __init__(self, page: Page) -> None:
        locator = page.get_by_test_id(ElementIDs.TOAST)
        super().__init__(locator=locator, page=page)

    def get_toasts(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.TOAST)

    def get_action_button(self) -> Locator:
        return self._page.get_by_test_id(ElementIDs.TOAST_ACTION_BUTTON)
