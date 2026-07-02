from sculptor.constants import ElementIDs
from sculptor.testing.elements.onboarding import PlaywrightAddRepoStepElement
from sculptor.testing.elements.onboarding import PlaywrightPathCheckStepElement
from sculptor.testing.pages.base import PlaywrightIntegrationTestPage


class PlaywrightOnboardingPage(PlaywrightIntegrationTestPage):
    """Page object for the onboarding wizard - provides access to step components."""

    def get_path_check_step(self) -> PlaywrightPathCheckStepElement:
        """Get the PATH-check step component."""
        path_check_step_locator = self.get_by_test_id(ElementIDs.ONBOARDING_PATH_CHECK_STEP)
        return PlaywrightPathCheckStepElement(locator=path_check_step_locator, page=self._page)

    def get_add_repo_step(self) -> PlaywrightAddRepoStepElement:
        """Get the add-repo step component."""
        add_repo_step_locator = self.get_by_test_id(ElementIDs.ONBOARDING_ADD_REPO_STEP)
        return PlaywrightAddRepoStepElement(locator=add_repo_step_locator, page=self._page)
