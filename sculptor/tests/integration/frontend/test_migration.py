"""Integration tests for Sculptor data directory bootstrap.

Tests verify:
- Bootstrap creates the correct directory structure on startup.
"""

import hashlib
import os
import tempfile
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.config.user_config import UserConfig
from sculptor.services.user_config.user_config import save_config
from sculptor.testing.dependency_stubs import DependencyState
from sculptor.testing.dependency_stubs import stub_dependency
from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.resources import custom_sculptor_folder_populator
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story


def _make_test_config() -> UserConfig:
    """Create a minimal test UserConfig."""
    test_email = "test@imbue.com"
    return UserConfig(
        user_email=test_email,
        user_id=hashlib.md5(test_email.encode()).hexdigest(),
        organization_id=hashlib.md5(f"organization:{test_email}".encode()).hexdigest(),
        instance_id=hashlib.md5(os.urandom(64)).hexdigest(),
    )


def _populate_bootstrap_folder(folder_path: Path) -> None:
    """Set up a sculptor folder with internal/config.toml (where the backend expects it).

    ensure_sculptor_folder_ready() then creates any missing subdirectories on startup.
    """
    internal = folder_path / "internal"
    internal.mkdir(parents=True, exist_ok=True)
    save_config(_make_test_config(), internal / "config.toml")


def _dump_diagnostics(page: Page, sculptor_folder: Path, label: str) -> None:
    """Capture page screenshot and config for debugging CI failures."""
    screenshot_dir = Path(tempfile.mkdtemp(prefix="migration_test_diag_"))
    screenshot_path = screenshot_dir / f"{label}.png"
    page.screenshot(path=str(screenshot_path))
    print(f"\n=== MIGRATION TEST DIAGNOSTICS ({label}) ===")
    print(f"Screenshot saved to: {screenshot_path}")
    print(f"Page URL: {page.url}")
    config_path = sculptor_folder / "internal" / "config.toml"
    if config_path.exists():
        print(f"Config ({config_path}):\n{config_path.read_text()}")
    else:
        print(f"Config NOT FOUND at {config_path}")
    # Dump visible test IDs to understand what UI state we're in
    test_ids = page.evaluate("() => [...document.querySelectorAll('[data-testid]')].map(e => e.dataset.testid)")
    print(f"Visible test IDs: {test_ids}")
    print("=== END DIAGNOSTICS ===\n")


@user_story("to have Sculptor bootstrap its data directory correctly")
@custom_sculptor_folder_populator.with_args(_populate_bootstrap_folder)
@stub_dependency("claude", state=DependencyState.INSTALLED_STUB)
def test_bootstrap_and_workspace_operations(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """Verify bootstrap creates the data dirs and the frontend works afterward.

    The populator creates internal/config.toml; on startup
    ensure_sculptor_folder_ready() creates internal/ and workspaces/, and the
    backend then proceeds normally.
    """
    with sculptor_instance_factory_.spawn_instance() as instance:
        page = instance.page

        add_workspace_page = PlaywrightAddWorkspacePage(page)

        # Verify the Add Workspace page loaded — bootstrap succeeded
        try:
            expect(add_workspace_page.get_submit_button()).to_be_visible(timeout=45_000)
        except AssertionError:
            _dump_diagnostics(page, instance.sculptor_folder, "bootstrap")
            raise

        # Verify bootstrap created the expected structure
        assert (instance.sculptor_folder / "internal").is_dir()
        assert (instance.sculptor_folder / "workspaces").is_dir()

        # Create a workspace to verify full functionality
        start_task_and_wait_for_ready(
            sculptor_page=page,
            workspace_name="Bootstrap Test Workspace",
        )
