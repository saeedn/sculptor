"""Integration tests for agent tab Diagnostics context menu.

Tests cover:
- Copy agent name (top-level menu) and Copy agent id (Diagnostics) copy correct values
- Claude session and Sculptor transcript copy items are disabled for a terminal
  agent, which has no Claude on-disk session layout and no transcript yet (the
  diagnostics menu itself survives; only its session-dependent copy targets stay
  disabled)
"""

from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.clipboard import install_clipboard_interceptor
from sculptor.testing.elements.clipboard import read_intercepted_clipboard
from sculptor.testing.elements.clipboard import reset_intercepted_clipboard
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to see the Claude session diagnostics items disabled for a terminal agent")
def test_agent_diagnostics_claude_items_disabled_for_terminal_agent(
    sculptor_instance_: SculptorInstance,
) -> None:
    """The Claude session and Sculptor transcript copy items are disabled for a terminal agent.

    Terminal agents have no Claude on-disk session layout and no transcript yet,
    so the diagnostics endpoint returns no session id or transcript path — the
    menu items render but stay disabled (Radix marks disabled items with a
    data-disabled attribute).

    Steps:
    1. Create a workspace with a terminal agent
    2. Right-click the agent tab and open the Diagnostics sub-menu
    3. Verify Copy session id and Copy Sculptor transcript path items are disabled
    """
    page = sculptor_instance_.page
    tab_bar = PlaywrightAgentTabBarElement(page)

    # Step 1: Create a workspace with a terminal agent (no chat surface).
    start_task_and_wait_for_ready(page, agent_type="terminal", model_name=None, workspace_name="Diag Disabled WS")

    # Step 2: Right-click the agent tab, open Diagnostics.
    agent_tabs = tab_bar.get_agent_tabs()
    expect(agent_tabs).to_have_count(1)
    tab_bar.open_diagnostics_submenu(agent_tabs.first)

    # Step 3: Verify the Claude-specific items are disabled (Radix uses data-disabled).
    copy_session_id = tab_bar.get_copy_session_id_item()
    expect(copy_session_id).to_be_visible()
    expect(copy_session_id).to_have_attribute("data-disabled", "")

    copy_sculptor_transcript = tab_bar.get_copy_sculptor_transcript_item()
    expect(copy_sculptor_transcript).to_be_visible()
    expect(copy_sculptor_transcript).to_have_attribute("data-disabled", "")


@user_story("to copy the agent name and id from the agent tab context menu")
def test_agent_context_menu_copy_name_and_id(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Copy agent name (top-level menu) and Copy agent id (Diagnostics) copy the right values.

    Unlike the Claude session/transcript items, these don't depend on a Claude
    session — they are available as soon as the agent exists, for any agent type.

    Steps:
    1. Create a workspace with a terminal agent
    2. Install clipboard interceptor
    3. Copy agent name from the top-level context menu and verify it matches the tab name
    4. Copy agent id from the Diagnostics sub-menu and verify a non-empty value
    """
    page = sculptor_instance_.page
    tab_bar = PlaywrightAgentTabBarElement(page)

    # Step 1: Create a workspace with a terminal agent.
    start_task_and_wait_for_ready(page, agent_type="terminal", model_name=None, workspace_name="Diag Name Id WS")

    # Step 2: Install clipboard interceptor.
    install_clipboard_interceptor(page)
    agent_tabs = tab_bar.get_agent_tabs()
    expect(agent_tabs).to_have_count(1)

    # Step 3: Copy agent name from the top-level context menu.
    tab_bar.open_context_menu(agent_tabs.first)
    copy_agent_name = tab_bar.get_copy_agent_name_item()
    expect(copy_agent_name).to_be_visible()
    reset_intercepted_clipboard(page)
    copy_agent_name.click()

    page.wait_for_function("() => window.__clipboardWritten !== null")
    agent_name = read_intercepted_clipboard(page)
    assert agent_name, "Expected agent name to be copied to clipboard"
    # The copied name is the agent's display name, which the tab shows.
    expect(agent_tabs.first).to_contain_text(agent_name)

    # Step 4: Copy agent id from the Diagnostics sub-menu.
    tab_bar.open_diagnostics_submenu(agent_tabs.first)
    copy_agent_id = tab_bar.get_copy_agent_id_item()
    expect(copy_agent_id).to_be_visible()
    reset_intercepted_clipboard(page)
    copy_agent_id.click()

    page.wait_for_function("() => window.__clipboardWritten !== null")
    agent_id = read_intercepted_clipboard(page)
    assert agent_id, "Expected agent id to be copied to clipboard"
