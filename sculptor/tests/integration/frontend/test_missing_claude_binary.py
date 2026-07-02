"""Integration test for the onboarding PATH-check when ``claude`` is missing.

Onboarding's PATH-check screen resolves ``claude`` and ``git`` with
``shutil.which`` (read-only — it never installs). When ``claude`` is not on
the backend's PATH, the screen must report it as missing with a friendly,
plain-language message and an install link, while still letting the user
continue (report-and-link, never hard-block).

Setup strategy
--------------
Rather than stubbing the dependency service (removed in the slim-down), this
test drives the failure purely through PATH: it gives the backend a PATH built
from the host PATH with every directory that contains a ``claude`` executable
dropped (leaving the venv ``python``, the shell, and ``git`` in their real
directories so the backend still boots), so ``shutil.which("claude")`` returns
``None`` while ``git`` still resolves.
"""

import os
import shutil
from pathlib import Path

from loguru import logger
from playwright.sync_api import expect

from sculptor.testing.pages.onboarding_page import PlaywrightOnboardingPage
from sculptor.testing.resources import custom_sculptor_folder_populator
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story


def _dont_populate_sculptor_folder(path: Path) -> None:
    logger.info("Skipping population of Sculptor folder for missing-claude test.")


def _make_path_without_claude() -> str:
    """Return a PATH built from the host PATH minus any directory containing a
    ``claude`` executable.

    Keeping the surviving directories intact (rather than mirroring them into a
    single dir) preserves venv ``python`` resolution — the venv is detected from
    ``pyvenv.cfg`` next to the real interpreter, which a symlink elsewhere would
    hide. Drops only claude-bearing directories so the backend still boots with
    python/shell/git while ``shutil.which("claude")`` returns ``None``.
    """
    surviving_dirs: list[str] = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        if os.path.exists(os.path.join(directory, "claude")):
            continue
        surviving_dirs.append(directory)
    new_path = os.pathsep.join(surviving_dirs)
    assert shutil.which("git", path=new_path) is not None, "git must be on PATH (in a non-claude dir) for this test"
    assert shutil.which("claude", path=new_path) is None, "claude must not resolve on the filtered PATH"
    return new_path


@user_story("to see a friendly message and install link when Claude is not on my PATH")
@custom_sculptor_folder_populator.with_args(_dont_populate_sculptor_folder)
def test_missing_claude_binary_shows_friendly_error(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """When ``claude`` is not on PATH, the onboarding PATH-check screen should
    report it as missing with a plain-language message + install link, and
    still allow the user to continue.

    Verifies:
    1. The PATH-check screen reports claude as not found
    2. The friendly missing-claude message is shown (no install is attempted)
    3. git is still reported as found
    4. The Continue button is enabled (report-and-link, never hard-block)
    """
    # Override the backend's PATH so claude is absent but everything else
    # (python, shell, git) still resolves and the backend can boot.
    sculptor_instance_factory_.update_environment(PATH=_make_path_without_claude())

    with sculptor_instance_factory_.spawn_instance(auto_project=False) as sculptor_instance:
        onboarding_page = PlaywrightOnboardingPage(sculptor_instance.page)

        path_check_step = onboarding_page.get_path_check_step()
        expect(path_check_step).to_be_visible()

        # Claude is reported missing, with the friendly message (no install).
        expect(path_check_step.get_claude_status()).to_contain_text("not found")
        missing_message = path_check_step.get_missing_claude_message()
        expect(missing_message).to_be_visible()
        expect(missing_message).to_contain_text("Claude")

        # git still resolves through the overridden PATH.
        expect(path_check_step.get_git_status()).to_contain_text("found")

        # The user can still continue despite the missing tool.
        continue_button = path_check_step.get_continue_button()
        expect(continue_button).to_be_enabled()
