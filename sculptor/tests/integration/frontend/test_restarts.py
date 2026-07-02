"""Backend-restart persistence, re-expressed against the fake terminal agent.

The surviving contract: a workspace and its agent persist across a backend
restart, and a registered terminal agent resumes its session (the relaunch
runs the rendered ``resume_command_template`` and the tab comes back). The
agent task-list popover and the rich chat surface do not survive the slim-down,
so the chat-panel vehicle is replaced by the terminal-agent harness.
"""

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import focus_agent_terminal
from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import DEFAULT_REGISTRATION_ID
from sculptor.testing.fake_terminal_agent import register_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.pages.add_workspace_page import PlaywrightAddWorkspacePage
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.user_stories import user_story

_TERMINAL_AGENT_TAB_NAME = f"{DEFAULT_DISPLAY_NAME} 1"
# Mirrors the ``{registration_id}-session`` id the fake runner reports and the
# resume command renders (see ``register_fake_terminal_agent``).
_TERMINAL_AGENT_SESSION_ID = f"{DEFAULT_REGISTRATION_ID}-session"


def _launch_registered_terminal_agent(instance: SculptorInstance) -> None:
    """Create a workspace and launch the fake terminal agent into it.

    Registers the fake terminal agent once (so the registration TOML persists
    across the restart and the resume relaunch can find it), then selects it
    from the agent-type menu and waits for its ready banner.
    """
    page = instance.page
    agents_dir = instance.sculptor_folder / "terminal_agents"

    start_task_and_wait_for_ready(page)
    register_fake_terminal_agent(agents_dir)

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    agent_tab_bar.open_agent_type_menu()
    registered_item = agent_tab_bar.get_agent_type_menu_item_registered("fake-terminal-agent")
    expect(registered_item).to_be_visible()
    registered_item.click()

    expect(get_agent_terminal_panel(page)).to_be_visible()
    wait_for_xterm_substring(page, "FAKE-TERMINAL-AGENT-READY")

    # Wait for the runner's SESSION-REPORTED marker, which it prints only AFTER
    # its blocking `sculpt signal session-id` call returns. This proves the
    # session id was persisted before we tear the instance down, so the
    # post-restart resume can render `RESUMED-<id>` rather than relaunching from
    # scratch. (Waiting for the tab dot to settle is NOT sufficient: the dot can
    # read read/unread for reasons unrelated to the session-id signal, racing
    # teardown against persistence.)
    wait_for_xterm_substring(page, f"SESSION-REPORTED-{_TERMINAL_AGENT_SESSION_ID}")


def _reopen_persisted_workspace(page: Page) -> PlaywrightAgentTabBarElement:
    """Click the persisted workspace tab on a fresh Sculptor instance."""
    layout = PlaywrightProjectLayoutPage(page=page)
    workspace_tab = layout.get_workspace_tabs().first
    expect(workspace_tab).to_be_visible()
    workspace_tab.click()
    return PlaywrightAgentTabBarElement(page)


@user_story("my progress to stay on backend restarts")
def test_tasks_persist_on_restart(sculptor_instance_factory_: SculptorInstanceFactory) -> None:
    """The workspace and its terminal agent survive a restart."""
    with sculptor_instance_factory_.spawn_instance() as instance:
        _launch_registered_terminal_agent(instance)

    with sculptor_instance_factory_.spawn_instance() as instance:
        agent_tab_bar = _reopen_persisted_workspace(instance.page)
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
        expect(terminal_tab).to_be_visible()


@user_story("my progress to stay on backend restarts")
def test_chats_persist_on_restart(sculptor_instance_factory_: SculptorInstanceFactory) -> None:
    """A terminal agent persists across a backend restart and relaunches usably.

    The persistence contract: the agent's tab survives the restart and its
    terminal relaunches into a live, usable shell. (The registered-agent resume
    path — relaunch via the rendered ``resume_command_template`` — is asserted
    in detail by ``test_registered_terminal_agent_resumes_after_restart``; here
    we assert the surviving-agent persistence + that the relaunched terminal is
    operational.)
    """
    with sculptor_instance_factory_.spawn_instance() as instance:
        _launch_registered_terminal_agent(instance)

    with sculptor_instance_factory_.spawn_instance() as instance:
        page = instance.page
        agent_tab_bar = _reopen_persisted_workspace(page)
        terminal_tab = agent_tab_bar.get_agent_tab_by_name(_TERMINAL_AGENT_TAB_NAME).first
        expect(terminal_tab).to_be_visible()
        terminal_tab.click()
        expect(get_agent_terminal_panel(page)).to_be_visible()
        focus_agent_terminal(page)
        # The session id was reported before the restart, so the runner resumes:
        # its rendered resume command echoes "RESUMED-<session id>".
        wait_for_xterm_substring(page, f"RESUMED-{_TERMINAL_AGENT_SESSION_ID}")

        # The relaunched agent is operational, not a dead tab: a fresh DSL
        # command is picked up and run to completion by the resumed runner.
        agents_dir = instance.sculptor_folder / "terminal_agents"
        send_fake_agent_command_and_wait(agents_dir, write_file("after_restart.txt", "ok"))


@user_story("my new workspace tab to persist on restart")
def test_restart_reuses_existing_new_workspace_tab(
    sculptor_instance_factory_: SculptorInstanceFactory,
) -> None:
    """Restarting without creating a workspace should reuse the existing new-workspace tab, not add another."""
    with sculptor_instance_factory_.spawn_instance() as instance:
        add_workspace = PlaywrightAddWorkspacePage(page=instance.page)

        # We land on the add-workspace page (no workspaces exist yet)
        expect(add_workspace.get_submit_button()).to_be_visible()

        # There should be exactly one new-workspace tab
        expect(add_workspace.get_add_workspace_tabs()).to_have_count(1)

    # Restart — the rootLoader should reuse the existing new-workspace pseudo-tab
    with sculptor_instance_factory_.spawn_instance() as instance:
        add_workspace = PlaywrightAddWorkspacePage(page=instance.page)

        expect(add_workspace.get_submit_button()).to_be_visible()

        # Still exactly one new-workspace tab — not two
        expect(add_workspace.get_add_workspace_tabs()).to_have_count(1)
