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


def _populate_returning_user_config(path: Path) -> None:
    """Write a minimal config for a returning user (already past first run)."""
    internal_dir = path / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    config = UserConfig(instance_id="returning-user-test-instance")
    save_config(config, internal_dir / "config.toml")


@user_story("to skip onboarding entirely when I already have a repo configured")
@custom_sculptor_folder_populator.with_args(_populate_returning_user_config)
def test_existing_project_skips_onboarding(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """A returning user with an existing project skips onboarding entirely.

    Onboarding completion is implied by having a project, so a user who
    already has one is sent straight to the main app — no PATH-check or
    add-repo step.

    Verifies:
    1. The main app (Add Workspace page) is shown directly
    2. Neither onboarding step (PATH check, add-repo) appears
    """
    with sculptor_instance_factory_.spawn_instance(auto_project=True) as sculptor_instance:
        page = sculptor_instance.page
        onboarding_page = PlaywrightOnboardingPage(page)

        # The main app appears directly — onboarding is skipped.
        add_workspace_page = PlaywrightAddWorkspacePage(page)
        expect(add_workspace_page.get_submit_button()).to_be_visible()

        # Neither onboarding step should have appeared.
        expect(onboarding_page.get_path_check_step()).not_to_be_visible()
        expect(onboarding_page.get_add_repo_step()).not_to_be_visible()
