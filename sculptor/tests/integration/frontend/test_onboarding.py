"""Integration tests for the onboarding flow.

Onboarding is a single read-only PATH-check screen (claude + git) followed by
the repo-add step. The PATH check reports found/missing and links to install
docs but never blocks: the Continue button always proceeds.
"""

from pathlib import Path

from loguru import logger
from playwright.sync_api import expect

from sculptor.config.user_config import UserConfig
from sculptor.services.user_config.user_config import save_config
from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.pages.onboarding_page import PlaywrightOnboardingPage
from sculptor.testing.resources import custom_sculptor_folder_populator
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story


def _dont_populate_sculptor_folder(path: Path) -> None:
    logger.info("Skipping population of Sculptor folder for onboarding test.")


@user_story("to complete onboarding by passing the tool check and adding a repo")
@custom_sculptor_folder_populator.with_args(_dont_populate_sculptor_folder)
def test_full_onboarding_flow(sculptor_instance_factory_: SculptorInstanceFactory) -> None:
    """Test the complete onboarding flow from the PATH check through to the Add Workspace page.

    Verifies:
    1. The PATH-check screen loads and reports both tools (claude + git are on
       PATH in test environments)
    2. Continuing past the PATH check reaches the add-repo step
    3. The add-repo step accepts a repository path
    4. After completing onboarding, the Add Workspace page is shown
    """
    with sculptor_instance_factory_.spawn_instance(auto_project=False) as sculptor_instance:
        page = sculptor_instance.page
        onboarding_page = PlaywrightOnboardingPage(page)

        # PATH-check screen: both tools should be present in test environments.
        path_check_step = onboarding_page.get_path_check_step()
        expect(path_check_step).to_be_visible()
        # Both tools resolve, so neither row shows the "not found" wording.
        expect(path_check_step.get_claude_status()).not_to_contain_text("not found")
        expect(path_check_step.get_git_status()).not_to_contain_text("not found")

        # The missing-claude message must NOT appear when claude is on PATH.
        expect(path_check_step.get_missing_claude_message()).not_to_be_visible()

        # Continue is always enabled once the check resolves.
        path_check_step.complete_step()

        # Add-repo step accepts a repository path.
        add_repo_step = onboarding_page.get_add_repo_step()
        expect(add_repo_step).to_be_visible()
        add_repo_step.complete_step(str(sculptor_instance_factory_.base_repo.base_path))

        # After onboarding, the Add Workspace page should load.
        add_workspace_page = PlaywrightAddWorkspacePage(page)
        expect(add_workspace_page.get_submit_button()).to_be_visible()


def _populate_returning_user_no_privacy(path: Path) -> None:
    """Write a config for a returning user who has not recorded privacy consent.

    Simulates a user who already has an existing project but whose config
    predates the privacy/telemetry fields. Completing onboarding backfills
    the consent, so they should skip the add-repo step.
    """
    internal_dir = path / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    config = UserConfig(
        user_email="",
        user_id="returning-user-test",
        organization_id="returning-user-test-org",
        instance_id="returning-user-test-instance",
    )
    save_config(config, internal_dir / "config.toml")


@user_story("to skip the add-repo step when I already have a repo configured")
@custom_sculptor_folder_populator.with_args(_populate_returning_user_no_privacy)
def test_path_check_skips_add_repo_when_project_exists(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """Continuing past the PATH check should not show the add-repo step if a project already exists.

    A returning user with an existing project who still needs their privacy
    consent backfilled should be sent straight to the main app after the PATH
    check — not to the "Add your first repo" page.

    Verifies:
    1. User with a project but no privacy consent is routed to the PATH check
    2. After continuing, the add-repo step does NOT appear
    3. The main app (Add Workspace page) is shown instead
    """
    with sculptor_instance_factory_.spawn_instance(auto_project=True) as sculptor_instance:
        page = sculptor_instance.page
        onboarding_page = PlaywrightOnboardingPage(page)

        # User is routed to the PATH-check step (has a project but no consent).
        path_check_step = onboarding_page.get_path_check_step()
        expect(path_check_step).to_be_visible()

        # Continue past the PATH check.
        path_check_step.complete_step()

        # The main app should appear — not the add-repo step.
        add_workspace_page = PlaywrightAddWorkspacePage(page)
        expect(add_workspace_page.get_submit_button()).to_be_visible()

        # The add-repo step should not have appeared.
        expect(onboarding_page.get_add_repo_step()).not_to_be_visible()
