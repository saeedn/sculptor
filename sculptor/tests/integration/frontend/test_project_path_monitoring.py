"""Integration tests for project path monitoring functionality."""

import shutil

import pytest
from playwright.sync_api import expect

from sculptor.foundation.common import get_temp_dir
from sculptor.foundation.test_utils import create_temp_dir
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@pytest.mark.release
@pytest.mark.skip(reason="Flakey (PROD-2871)")
@user_story("to be notified when the project directory is moved or deleted")
def test_project_path_monitoring(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page

    # Create a workspace (terminal agent, no model) to activate the project.
    # Activating it first avoids a race where moving the project path mid-
    # activation fails the activation. No chat agent is needed.
    start_task_and_wait_for_ready(page, agent_type="terminal", model_name=None, workspace_name="Path Monitoring WS")
    layout = PlaywrightProjectLayoutPage(page=page)

    original_path = sculptor_instance_.repo.base_path

    with create_temp_dir(root_dir=get_temp_dir()) as temp_dir:
        moved_path = temp_dir / original_path.name
        shutil.move(str(original_path), str(moved_path))

        warning_banner_element = layout.get_warning_banner()
        expect(warning_banner_element).to_be_visible()

        warning_banner_element.click_link()

        dialog = layout.get_project_path_dialog()
        expect(dialog).to_be_visible()

        dialog.close()
        expect(dialog).not_to_be_visible()

        shutil.move(str(moved_path), str(original_path))

        expect(warning_banner_element).not_to_be_visible()
