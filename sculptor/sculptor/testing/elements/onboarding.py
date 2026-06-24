from playwright.sync_api import Locator

from sculptor.constants import ElementIDs
from sculptor.testing.elements.base import PlaywrightIntegrationTestElement


class PlaywrightPathCheckStepElement(PlaywrightIntegrationTestElement):
    """Element representing the PATH-check step of onboarding."""

    def get_claude_status(self) -> Locator:
        """Get the claude tool status row."""
        return self.get_by_test_id(ElementIDs.ONBOARDING_TOOL_STATUS_CLAUDE)

    def get_git_status(self) -> Locator:
        """Get the git tool status row."""
        return self.get_by_test_id(ElementIDs.ONBOARDING_TOOL_STATUS_GIT)

    def get_missing_claude_message(self) -> Locator:
        """Get the friendly message shown when claude is missing from PATH."""
        return self.get_by_test_id(ElementIDs.ONBOARDING_TOOL_MISSING_CLAUDE_MESSAGE)

    def get_continue_button(self) -> Locator:
        """Get the continue button (always enabled — report-and-link)."""
        return self.get_by_test_id(ElementIDs.ONBOARDING_PATH_CHECK_CONTINUE)

    def submit(self) -> None:
        """Continue past the PATH-check step."""
        self.get_continue_button().click()

    def complete_step(self) -> None:
        """Complete the PATH-check step by clicking Continue."""
        self.submit()


class PlaywrightAddRepoStepElement(PlaywrightIntegrationTestElement):
    """Element representing the add-repo step of onboarding."""

    def get_path_input(self) -> Locator:
        """Get the repo path input field."""
        return self._page.get_by_test_id(ElementIDs.ADD_REPO_PATH_INPUT)

    def enter_path(self, path: str) -> None:
        """Enter a repo path in the input field."""
        path_input = self.get_path_input()
        path_input.click()
        path_input.fill(path)

    def submit(self) -> None:
        """Submit the path by pressing Enter."""
        self.get_path_input().press("Enter")

    def complete_step(self, repo_path: str) -> None:
        """Complete the add-repo step by entering a path and submitting."""
        self.enter_path(repo_path)
        self.submit()
