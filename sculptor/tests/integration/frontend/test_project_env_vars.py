"""Integration tests for project environment variable loading.

Tests verify that variables from .sculptor/.env are available in:
- The terminal agent's shell (its ``bash`` DSL runs in the agent env)
- Workspace terminal sessions
- Default override behavior
- Settings page display

The old chat-agent bash assertions are re-expressed against the terminal
agent: its ``bash`` command output reaches the agent's terminal panel, so the
injected env var is asserted from the xterm buffer rather than a chat bash pill.
The first-message env-var reminder tests are dropped: that reminder is injected
only into the removed SDK chat agent's first message; terminal agents have no
first-message injection (see test-triage §"workspace setup system reminder").
"""

from typing import Generator

import pytest
from playwright.sync_api import expect

from sculptor.testing.elements.terminal import get_add_terminal_button
from sculptor.testing.elements.terminal import get_terminal_tabs
from sculptor.testing.elements.terminal import open_terminal_and_wait
from sculptor.testing.elements.terminal import run_command_in_active_terminal
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.playwright_utils import navigate_to_settings_page
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@pytest.fixture(autouse=True)
def _isolate_dotenv_files(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Wipe both .env files before and after each shared-instance test.

    ``load_project_env_vars`` merges the global ``~/.sculptor/.env`` and
    project ``<repo>/.sculptor/.env``, so a stale file from either side leaks
    env-var names into a later test. The session-scoped ``sculptor_folder`` is
    never reset by ``_pre_test`` (only the project repo is, via
    ``_create_fresh_repo``), so the global ``.env`` is the actual leak source —
    but we handle both for symmetry.
    """
    if "sculptor_instance_" not in request.fixturenames:
        yield
        return

    instance = request.getfixturevalue("sculptor_instance_")
    global_env = instance.sculptor_folder / ".env"
    project_env = instance.project_path / ".sculptor" / ".env"

    global_env.unlink(missing_ok=True)
    project_env.unlink(missing_ok=True)
    try:
        yield
    finally:
        global_env.unlink(missing_ok=True)
        project_env.unlink(missing_ok=True)


@user_story("to have project env vars available in the terminal agent's shell")
def test_agent_shell_has_project_env_vars(sculptor_instance_: SculptorInstance) -> None:
    """The terminal agent's shell should see env vars loaded from .sculptor/.env.

    Steps:
    1. Create .sculptor/.env in the project repo before workspace creation.
    2. Start the fake terminal agent and run a ``bash`` command that echoes the
       env var.
    3. Verify the agent's terminal output contains the echoed env var value.
    """
    env_dir = sculptor_instance_.project_path / ".sculptor"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("SCTEST_AGENT_VAR=hello_from_dotenv\n")

    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    start_fake_terminal_agent(page, agents_dir, workspace_name="Agent Env WS")
    send_fake_agent_command_and_wait(agents_dir, bash("echo AGENT_ENV_CHECK:$SCTEST_AGENT_VAR"))

    wait_for_xterm_substring(page, "AGENT_ENV_CHECK:hello_from_dotenv")


@user_story("to have project env vars available in terminal sessions")
def test_terminal_has_project_env_vars(sculptor_instance_: SculptorInstance) -> None:
    """Terminal sessions should see env vars loaded from .sculptor/.env.

    Steps:
    1. Create .sculptor/.env in the project repo before workspace creation.
    2. Create a workspace and open the terminal.
    3. Echo the env var in the terminal and verify the output.
    """
    env_dir = sculptor_instance_.project_path / ".sculptor"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("SCTEST_TERMINAL_VAR=terminal_dotenv_value\n")

    page = sculptor_instance_.page
    start_task_and_wait_for_ready(page, workspace_name="Terminal Env WS")
    open_terminal_and_wait(page)

    run_command_in_active_terminal(page, 'echo "TERM_ENV_CHECK:${SCTEST_TERMINAL_VAR:-NOT_SET}"')
    wait_for_xterm_substring(page, "TERM_ENV_CHECK:terminal_dotenv_value")


@user_story("to have .env vars not override existing env vars by default")
def test_agent_shell_env_var_no_override_by_default(sculptor_instance_: SculptorInstance) -> None:
    """By default, .sculptor/.env values should NOT override existing environment variables.

    Steps:
    1. Create .sculptor/.env with PATH=/nonexistent and a unique test var.
    2. Start the fake terminal agent and run a ``bash`` command testing both.
    3. Verify the unique test var is injected, and PATH was NOT overridden (ls
       still works via PATH lookup).
    """
    env_dir = sculptor_instance_.project_path / ".sculptor"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("PATH=/nonexistent\nSCTEST_UNIQUE_VAR=dotenv_present\n")

    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    start_fake_terminal_agent(page, agents_dir, workspace_name="Override WS")
    send_fake_agent_command_and_wait(
        agents_dir,
        bash("echo OVERRIDE_CHECK:$SCTEST_UNIQUE_VAR && ls / >/dev/null 2>&1 && echo PATH_OK"),
    )

    # SCTEST_UNIQUE_VAR should be injected (it didn't exist before).
    wait_for_xterm_substring(page, "OVERRIDE_CHECK:dotenv_present")
    # PATH was NOT overridden, so `ls` (which requires PATH lookup) succeeded.
    wait_for_xterm_substring(page, "PATH_OK")


@user_story("to have newly-added .env vars available to terminals opened later")
def test_terminal_picks_up_newly_added_env_var(sculptor_instance_: SculptorInstance) -> None:
    """A terminal opened after a global .env update should see the newly-added var.

    Regression test for the case where TerminalEnvironmentConfig.extra_env was
    snapshotted at workspace startup, so terminals created later still saw the
    stale env even after ~/.sculptor/.env was updated.

    The initial terminal at index 0 is created during workspace load (before the
    user has had a chance to update the .env file), so the test exercises the
    "open a new terminal tab" flow: writes the var to the global .env, then
    clicks the "+" button to create a second terminal (index > 0), which goes
    through the lazy create_terminal_for_environment path.
    """
    global_env_file = sculptor_instance_.sculptor_folder / ".env"
    if global_env_file.exists():
        global_env_file.unlink()

    page = sculptor_instance_.page
    start_task_and_wait_for_ready(page, workspace_name="Late Terminal WS")
    open_terminal_and_wait(page)

    global_env_file.write_text("SCTEST_LATE_TERMINAL_VAR=terminal_loaded_after\n")

    get_add_terminal_button(page).click()
    # Two workspace bottom-terminal tabs now exist (a global "Terminal input"
    # count would also include the agent terminal's textarea, so assert on the
    # bottom-terminal tab count instead).
    expect(get_terminal_tabs(page)).to_have_count(2)

    run_command_in_active_terminal(page, 'echo "TERM_LATE_CHECK:${SCTEST_LATE_TERMINAL_VAR:-MISSING}"')
    wait_for_xterm_substring(page, "TERM_LATE_CHECK:terminal_loaded_after")


@user_story("to see loaded env var names in the settings page")
def test_env_var_names_shown_in_settings(sculptor_instance_: SculptorInstance) -> None:
    """After starting a workspace with .sculptor/.env, the settings page should display the loaded variable names.

    Steps:
    1. Create .sculptor/.env with two test variables.
    2. Start a task to create a workspace (which loads the .env).
    3. Navigate to the settings page and open the env vars section.
    4. Verify the variable names appear in the loaded names list.
    """
    env_dir = sculptor_instance_.project_path / ".sculptor"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("SCTEST_SETTING_A=value_a\nSCTEST_SETTING_B=value_b\n")

    page = sculptor_instance_.page
    start_task_and_wait_for_ready(page, agent_type="terminal", workspace_name="Settings Env WS")

    settings_page = navigate_to_settings_page(page=page)
    env_vars_section = settings_page.click_on_env_vars()

    names_list = env_vars_section.get_names_list()
    expect(names_list).to_contain_text("SCTEST_SETTING_A")
    expect(names_list).to_contain_text("SCTEST_SETTING_B")
