from playwright.sync_api import Locator
from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.constants import ElementIDs
from sculptor.testing.elements.base import PlaywrightIntegrationTestElement


class PlaywrightActionDialogElement(PlaywrightIntegrationTestElement):
    """Page Object Model for the Action create/edit dialog."""

    def fill_name(self, name: str) -> None:
        """Fill the action name field."""
        name_input = self.get_by_test_id(ElementIDs.ACTION_DIALOG_NAME_INPUT)
        expect(name_input).to_be_visible()
        name_input.fill(name)

    def fill_prompt(self, prompt: str) -> None:
        """Fill the action prompt textarea (``fill`` clears then sets, so it covers
        both create and edit modes)."""
        prompt_input = self.get_by_test_id(ElementIDs.ACTION_DIALOG_PROMPT_INPUT)
        expect(prompt_input).to_be_visible()
        prompt_input.fill(prompt)

    def click_save(self) -> None:
        """Click the 'Save Action' button."""
        save_button = self.get_by_test_id(ElementIDs.ACTION_DIALOG_SAVE_BUTTON)
        expect(save_button).to_be_enabled()
        save_button.click()

    def select_group(self, group_name: str) -> None:
        """Select an existing group in the group dropdown."""
        trigger = self.get_by_test_id(ElementIDs.ACTION_DIALOG_GROUP_SELECT)
        expect(trigger).to_be_visible()
        trigger.click()
        self._page.get_by_role("option", name=group_name).click()

    def select_new_group(self, group_name: str) -> None:
        """Select '+ Create new group...' and fill the group name."""
        trigger = self.get_by_test_id(ElementIDs.ACTION_DIALOG_GROUP_SELECT)
        expect(trigger).to_be_visible()
        trigger.click()
        self._page.get_by_role("option", name="+ Create new group...").click()
        name_input = self._page.get_by_test_id(ElementIDs.ACTION_DIALOG_NEW_GROUP_NAME_INPUT)
        expect(name_input).to_be_visible()
        name_input.fill(group_name)

    def get_prompt_input(self) -> Locator:
        """Get the prompt textarea locator."""
        return self.get_by_test_id(ElementIDs.ACTION_DIALOG_PROMPT_INPUT)

    def get_group_select(self) -> Locator:
        """Get the group select trigger."""
        return self.get_by_test_id(ElementIDs.ACTION_DIALOG_GROUP_SELECT)

    def get_auto_submit_switch(self) -> Locator:
        """Get the auto-submit switch."""
        return self.get_by_test_id(ElementIDs.ACTION_DIALOG_AUTO_SUBMIT_SWITCH)


def get_action_dialog(page: Page) -> PlaywrightActionDialogElement:
    """Get the action dialog from the page (rendered at page level by Radix)."""
    dialog = page.get_by_test_id(ElementIDs.ACTION_DIALOG)
    return PlaywrightActionDialogElement(locator=dialog, page=page)
