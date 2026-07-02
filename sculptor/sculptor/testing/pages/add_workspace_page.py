from playwright.sync_api import Locator
from playwright.sync_api import expect

from sculptor.constants import ElementIDs
from sculptor.testing.elements.add_repo_dialog import PlaywrightAddRepoDialogElement
from sculptor.testing.pages.project_layout import PlaywrightProjectLayoutPage


class PlaywrightAddWorkspacePage(PlaywrightProjectLayoutPage):
    """Page object for the Add Workspace page (/ws/new)."""

    def get_project_selector(self) -> Locator:
        return self.get_by_test_id(ElementIDs.PROJECT_SELECTOR)

    def get_project_options(self) -> Locator:
        return self.get_by_test_id(ElementIDs.PROJECT_SELECT_ITEM)

    def select_project_by_name(self, project_name: str) -> None:
        self.get_project_selector().click()
        project_option = self.get_project_options().filter(has_text=project_name)
        expect(project_option).to_be_visible()
        project_option.click()

    def get_open_new_repo_button(self) -> Locator:
        return self.get_by_test_id(ElementIDs.OPEN_NEW_REPO_BUTTON)

    def open_add_repo_dialog(self) -> PlaywrightAddRepoDialogElement:
        """Open the 'Add Repository' dialog from the repo selector."""
        self.get_project_selector().click()
        self.get_open_new_repo_button().click()
        dialog = PlaywrightAddRepoDialogElement(
            locator=self.get_by_test_id(ElementIDs.ADD_REPO_DIALOG), page=self._page
        )
        expect(dialog.get_path_input()).to_be_visible()
        return dialog

    def get_workspace_name_input(self) -> Locator:
        return self.get_by_test_id(ElementIDs.WORKSPACE_NAME_INPUT)

    def get_submit_button(self) -> Locator:
        return self.get_by_test_id(ElementIDs.START_TASK_BUTTON)

    def get_branch_name_input(self) -> Locator:
        return self.get_by_test_id(ElementIDs.BRANCH_NAME_INPUT)

    def get_branch_name_collision_error(self) -> Locator:
        return self.get_by_test_id(ElementIDs.BRANCH_NAME_COLLISION_ERROR)

    def get_branch_selector(self) -> Locator:
        return self.get_by_test_id(ElementIDs.BRANCH_SELECTOR)

    def select_branch(self, branch_name: str) -> None:
        self.get_branch_selector().click()
        branch_option = (
            self.get_by_test_id(ElementIDs.BRANCH_OPTION).filter(has_text=branch_name).filter(has_not_text="*")
        )
        expect(branch_option).to_have_count(1)
        branch_option.click()

    def get_terminal_panel(self) -> Locator:
        """The agent terminal panel — the main pane of a (terminal-only) workspace."""
        return self.get_by_test_id(ElementIDs.AGENT_TERMINAL_PANEL)

    def select_terminal_agent_type(self) -> None:
        """Pick the plain Terminal agent type for the first agent.

        The default first agent is the bundled ``claude-code`` registered agent,
        which launches the real Claude TUI — unavailable in CI, so its terminal
        never renders. A plain terminal agent is a bare shell that always
        launches, so tests that need the workspace's terminal panel to appear
        select it explicitly.
        """
        self.get_by_test_id(ElementIDs.ADD_WORKSPACE_AGENT_TYPE_SELECT).click()
        self.get_by_test_id(ElementIDs.AGENT_TYPE_OPTION_TERMINAL).click()

    def submit_and_wait_for_workspace(self, timeout: int = 60_000) -> None:
        """Select a plain terminal agent, submit, and wait for the workspace to load.

        The workspace/agent page has loaded once the terminal panel appears —
        the surviving signal in the terminal-only world. A plain terminal agent
        is selected so the panel reliably renders in CI (the default bundled
        ``claude-code`` agent would try to launch the real Claude TUI).
        """
        self.select_terminal_agent_type()
        submit_button = self.get_submit_button()
        expect(submit_button).to_be_enabled()
        submit_button.click()
        expect(self.get_terminal_panel()).to_be_visible(timeout=timeout)
