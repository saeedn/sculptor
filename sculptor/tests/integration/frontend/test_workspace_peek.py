"""Integration tests for the workspace peek popover feature.

Tests cover:
- Popover appears on workspace tab hover with correct status content
- Idle state shows popover with workspace name, summary, and agent row (no banner)
- Waiting state shows orange waiting banner when a terminal agent signals waiting
- Hover mechanics: popover appears on hover and dismisses on mouse leave
- Diff stats in the popover footer

Agent state is driven by the fake registered terminal agent: a terminal agent's
peek status is derived from the lifecycle signal it last posted since its most
recent run start (busy -> WORKING, waiting -> WAITING, otherwise IDLE). To hold a
WAITING state the agent signals `waiting` and then blocks on a sentinel, so no
trailing `idle` fires until the test releases it.
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import add_registered_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import bash
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import navigate_to_add_workspace_page
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to see workspace peek status when hovering over a workspace tab with an idle agent")
def test_workspace_peek_popover_idle_state(
    sculptor_instance_: SculptorInstance,
) -> None:
    """When the agent is idle, hovering the workspace tab shows a popover with the
    workspace name, a summary, and an agent row.  No alert banner is shown
    because the agent is idle (ready for more input).
    """
    page = sculptor_instance_.page
    layout = PlaywrightProjectLayoutPage(page=page)

    start_task_and_wait_for_ready(page, agent_type="terminal", workspace_name="Idle WS")

    # Navigate away so we can hover over the workspace tab
    navigate_to_add_workspace_page(page)

    workspace_tab = layout.get_workspace_tabs().first
    workspace_tab.hover()

    peek = layout.get_workspace_peek_popover()
    expect(peek).to_be_visible()

    expect(peek.get_header()).to_contain_text("Idle WS")

    # No alert banner for idle state
    expect(peek.get_banner()).to_be_hidden()

    expect(peek.get_agent_rows().first).to_be_visible()


@user_story("to see workspace peek waiting status when a terminal agent signals waiting")
def test_workspace_peek_popover_waiting_state(
    sculptor_instance_: SculptorInstance,
) -> None:
    """When a terminal agent signals waiting (and holds it), hovering the
    workspace tab shows a popover with an orange waiting banner.
    """
    page = sculptor_instance_.page
    layout = PlaywrightProjectLayoutPage(page=page)
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    start_fake_terminal_agent(page, agents_dir, workspace_name="Waiting WS")

    # Drive the agent into a held WAITING state: signal `waiting` then block on a
    # sentinel so no trailing `idle` overrides it.
    send_fake_agent_command(
        agents_dir,
        multi_step([bash("sculpt signal waiting"), wait_for_file("hold.sentinel")]),
    )

    # Navigate away so we can hover over the workspace tab
    navigate_to_add_workspace_page(page)

    workspace_tab = layout.get_workspace_tabs().first
    workspace_tab.hover()

    peek = layout.get_workspace_peek_popover()
    expect(peek).to_be_visible()

    expect(peek.get_header()).to_contain_text("Waiting WS")

    expect(peek.get_banner()).to_be_visible()
    expect(peek.get_banner()).to_contain_text("needs your input")


@user_story("to quickly glance at workspace status by hovering over its tab")
def test_workspace_peek_popover_hover_mechanics(
    sculptor_instance_: SculptorInstance,
) -> None:
    """Hovering over a workspace tab shows the popover; moving the mouse
    away dismisses it. The popover contains a header, agent rows, and footer.
    """
    page = sculptor_instance_.page
    layout = PlaywrightProjectLayoutPage(page=page)

    start_task_and_wait_for_ready(page, agent_type="terminal", workspace_name="Hover WS")

    # Navigate away so we can hover over the workspace tab
    navigate_to_add_workspace_page(page)

    workspace_tab = layout.get_workspace_tabs().first
    peek = layout.get_workspace_peek_popover()

    expect(peek).to_be_hidden()

    workspace_tab.hover()
    expect(peek).to_be_visible()

    expect(peek.get_header()).to_be_visible()
    expect(peek.get_agent_rows().first).to_be_visible()

    # Move to the top-left corner which is far from the tab.
    page.mouse.move(0, 0)
    expect(peek).to_be_hidden()


@user_story("to see workspace peek status when hovering over a scrolled-into-view workspace tab")
def test_workspace_peek_popover_on_scrolled_tab(
    sculptor_instance_: SculptorInstance,
) -> None:
    """When the viewport is narrow enough that workspace tabs overflow into a
    horizontal scroll area, scrolling a tab into view and hovering it should
    still show the peek popover.
    """
    page = sculptor_instance_.page
    layout = PlaywrightProjectLayoutPage(page=page)

    # Create 3 workspaces so there are enough tabs to overflow a narrow viewport.
    for i in range(3):
        start_task_and_wait_for_ready(
            sculptor_page=page,
            agent_type="terminal",
            workspace_name=f"WS {i + 1}",
        )

    # Navigate away so we're not on any workspace tab
    navigate_to_add_workspace_page(page)

    # Shrink viewport to force tab overflow (3 workspace tabs + "Open Workspace"
    # tab at 200px each = 800px, which won't fit in a 500px-wide viewport).
    original_size = page.viewport_size
    page.set_viewport_size({"width": 500, "height": original_size["height"]})

    # "WS 1" is the leftmost tab, which may be scrolled out of view.
    # Scroll it into view and hover to trigger the peek popover.
    ws1_tab = layout.get_workspace_tabs().filter(has_text="WS 1")
    ws1_tab.scroll_into_view_if_needed()
    ws1_tab.hover()

    peek = layout.get_workspace_peek_popover()
    expect(peek).to_be_visible()

    # Restore viewport
    page.set_viewport_size(original_size)


@user_story("to see the workspace status turn yellow when any agent needs my attention")
def test_workspace_peek_waiting_overrides_running_in_banner(
    sculptor_instance_: SculptorInstance,
) -> None:
    """When one agent is running and another is waiting for user input, the
    peek popover should surface the waiting state via the attention banner,
    even though another agent is still running.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"
    second_registration_id = "fake-terminal-agent-2"

    # Create a workspace whose first registered fake terminal agent will be held
    # BUSY (running), then add a SECOND, independently-drivable fake terminal
    # agent that will be held WAITING.
    task_page, _ = start_fake_terminal_agent(page, agents_dir, workspace_name="Running+Waiting WS")
    add_registered_fake_terminal_agent(
        page,
        agents_dir,
        registration_id=second_registration_id,
        display_name="Fake Terminal Agent 2",
    )

    # Hold the first fake terminal agent BUSY (running) by blocking on a sentinel.
    send_fake_agent_command(
        agents_dir,
        multi_step([write_file("running.txt", "busy"), wait_for_file("running.sentinel")]),
    )

    # Hold the second fake terminal agent WAITING: signal `waiting` then block on
    # a sentinel so no trailing `idle` overrides it. Attention must win over the
    # still-running first agent in the banner.
    send_fake_agent_command(
        agents_dir,
        multi_step([bash("sculpt signal waiting"), wait_for_file("waiting.sentinel")]),
        registration_id=second_registration_id,
    )

    # Navigate away so the workspace tab is hoverable
    navigate_to_add_workspace_page(page)

    workspace_tab = task_page.get_workspace_tabs().first
    workspace_tab.hover()

    peek = task_page.get_workspace_peek_popover()
    expect(peek).to_be_visible()

    # The banner must surface the waiting agent — attention takes priority.
    expect(peek.get_banner()).to_be_visible()
    expect(peek.get_banner()).to_contain_text("needs your")


@user_story("to see diff stats in the workspace peek popover")
def test_peek_popover_shows_diff_stats(sculptor_instance_: SculptorInstance) -> None:
    """Hovering over the workspace tab should show a popover with
    target-branch diff stats (+N / -N)."""
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    # A file write so the workspace has an uncommitted diff for the footer stats.
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    workspace_tab = task_page.get_workspace_tabs().first
    expect(workspace_tab).to_be_visible()
    workspace_tab.hover()

    peek = task_page.get_workspace_peek_popover()
    expect(peek).to_be_visible()

    footer = peek.get_footer()
    expect(footer).to_be_visible()
    expect(footer).to_contain_text("+")
