"""Integration tests for the split `+` button and its agent-type menu.

The chevron menu lists the agent types, selecting Terminal creates a
"Terminal N" agent, and a plain `+` click creates the last-used type.
Terminal-panel behavior is covered by the terminal-agent tests; here we
only assert tab titles.
"""

from playwright.sync_api import expect

from sculptor.testing.elements.terminal import expect_agent_terminal_panel_visible
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to create agents of different types from the tab bar")
def test_agent_type_menu_creates_terminal_agent_and_remembers_type(
    sculptor_instance_: SculptorInstance,
) -> None:
    """The chevron menu creates plain Terminal agents and updates the last-used
    type so a subsequent plain `+` click creates the same type."""
    page = sculptor_instance_.page
    task_page = PlaywrightTaskPage(page=page)
    agent_tab_bar = task_page.get_agent_tab_bar()

    # The first agent is a plain terminal ("Terminal 1"), created by the helper.
    start_task_and_wait_for_ready(page, workspace_name="Agent Type WS")
    agent_tabs = agent_tab_bar.get_agent_tabs()
    expect(agent_tabs).to_have_count(1)
    expect(agent_tab_bar.get_agent_tab_by_name("Terminal 1")).to_have_count(1)

    # Chevron menu → Terminal creates "Terminal 2" whose main panel is a terminal.
    agent_tab_bar.open_agent_type_menu()
    agent_tab_bar.get_agent_type_menu_item_terminal().click()
    expect(agent_tabs).to_have_count(2)
    expect(agent_tab_bar.get_agent_tab_by_name("Terminal 2")).to_have_count(1)
    expect_agent_terminal_panel_visible(page)

    # Last-used type persisted: a plain + click now creates another Terminal.
    agent_tab_bar.get_add_agent_button().click()
    expect(agent_tabs).to_have_count(3)
    expect(agent_tab_bar.get_agent_tab_by_name("Terminal 3")).to_have_count(1)
    expect_agent_terminal_panel_visible(page)


@user_story("to see registered terminal agents in the type menu without restarting")
def test_registered_terminal_agent_appears_in_menu_and_creates(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Dropping a registration TOML makes it appear on the next menu open
    (the backend re-reads the directory per request); creating it names the
    tab from display_name and opens a terminal panel."""
    page = sculptor_instance_.page
    task_page = PlaywrightTaskPage(page=page)
    agent_tab_bar = task_page.get_agent_tab_bar()

    start_task_and_wait_for_ready(page, workspace_name="Registered Agent WS")

    # The registration does not exist yet — the menu shows no registered entry.
    agent_tab_bar.open_agent_type_menu()
    expect(agent_tab_bar.get_agent_type_menu_item_registered("fake-reg")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(agent_tab_bar.get_agent_type_menu()).not_to_be_visible()

    # Drop a registration file into the live instance's sculptor folder.
    registrations_dir = sculptor_instance_.sculptor_folder / "terminal_agents"
    registrations_dir.mkdir(parents=True, exist_ok=True)
    (registrations_dir / "fake-reg.toml").write_text(
        'display_name = "Fake Reg"\nlaunch_command = "echo hello-from-registration"\n'
    )
    try:
        # No restart: the entry appears on the next menu open.
        agent_tab_bar.open_agent_type_menu()
        registered_item = agent_tab_bar.get_agent_type_menu_item_registered("fake-reg")
        expect(registered_item).to_be_visible()
        registered_item.click()

        # Created agent is named from display_name and shows a terminal panel.
        expect(agent_tab_bar.get_agent_tab_by_name("Fake Reg 1")).to_have_count(1)
        expect_agent_terminal_panel_visible(page)
    finally:
        (registrations_dir / "fake-reg.toml").unlink(missing_ok=True)


@user_story("to have the Claude Code terminal agent available out of the box")
def test_bundled_claude_code_registration_installed_by_default(
    sculptor_instance_: SculptorInstance,
) -> None:
    """The backend installs the bundled Claude Code registration at startup,
    so a fresh instance lists it in the agent-type menu with no setup. Menu
    presence only — creating the agent would launch the real Claude TUI."""
    page = sculptor_instance_.page
    task_page = PlaywrightTaskPage(page=page)
    agent_tab_bar = task_page.get_agent_tab_bar()

    start_task_and_wait_for_ready(page, workspace_name="Bundled Claude WS")

    registrations_dir = sculptor_instance_.sculptor_folder / "terminal_agents"
    assert (registrations_dir / "claude-code.toml").is_file()
    assert (registrations_dir / "claude-code-hooks.json").is_file()

    agent_tab_bar.open_agent_type_menu()
    claude_cli_item = agent_tab_bar.get_agent_type_menu_item_registered("claude-code")
    expect(claude_cli_item).to_be_visible()
    expect(claude_cli_item).to_contain_text("Claude CLI")
    page.keyboard.press("Escape")
    expect(agent_tab_bar.get_agent_type_menu()).not_to_be_visible()
