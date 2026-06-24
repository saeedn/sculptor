"""Integration tests for deleting the last repository.

When a user deletes their only remaining repository, the app should redirect
them back to the onboarding wizard at the ADD_REPO step so they can add a
new repo.
"""

from playwright.sync_api import expect

from sculptor.testing.pages.onboarding_page import PlaywrightOnboardingPage
from sculptor.testing.playwright_utils import navigate_to_settings_page
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story


@user_story("to be redirected to onboarding after deleting my last repo")
def test_deleting_last_repo_shows_onboarding_add_repo_step(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """After deleting the only remaining repo, the onboarding wizard should reappear
    so the user can add a new repo.

    Steps:
    1. Navigate to Settings > Repositories
    2. Delete the only repo (the remove button should be enabled)
    3. Confirm the deletion
    4. The onboarding wizard reappears at the PATH-check step
    5. Completing the PATH-check step lands on the ADD_REPO step
    """
    with sculptor_instance_factory_.spawn_instance() as sculptor_instance:
        page = sculptor_instance.page

        settings_page = navigate_to_settings_page(page=page)
        repos_settings = settings_page.click_on_repositories()

        remove_button = repos_settings.get_first_repo_remove_button()
        expect(remove_button).to_be_enabled()

        repos_settings.remove_first_repo()

        # Onboarding restarts at its first step (the PATH check); advancing past
        # it reaches the ADD_REPO step where the user can register a new repo.
        onboarding_page = PlaywrightOnboardingPage(page)
        path_check_step = onboarding_page.get_path_check_step()
        expect(path_check_step).to_be_visible()
        path_check_step.complete_step()

        add_repo_step = onboarding_page.get_add_repo_step()
        expect(add_repo_step).to_be_visible()
