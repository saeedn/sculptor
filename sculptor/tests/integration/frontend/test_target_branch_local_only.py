"""Regression test for the Changes tab on a local-only repo with no remotes.

Two related bugs:

1. The "All" sub-tab is missing on WORKTREE workspaces created from a
   local-only source repo. ``_resolve_default_target_branch`` only falls
   back to the local ``main``/``master`` ref for workspaces, so
   WORKTREE leaves ``target_branch=None`` and ``DiffScopePicker`` hides
   the "All" item.

2. The Uncommitted tab shows "No changes" even after the agent has
   written a new file into the worktree. The diff pipeline should
   surface untracked files via the ``git ls-files --others`` step.

Both should work for a worktree workspace created from a local-only repo
(the user-reported repro: ``~/code/builder``).
"""

from playwright.sync_api import expect

from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to see uncommitted changes and the All tab on a worktree workspace from a local-only repo")
def test_worktree_on_local_only_repo_shows_all_tab_and_uncommitted_changes(
    sculptor_instance_: SculptorInstance,
) -> None:
    """A WORKTREE workspace on a local-only repo (no remotes) should still
    show both the "All" sub-tab and the agent's uncommitted file.

    The default test repo built by ``MockRepoState.build_locally`` has no
    remotes — so it matches the user's ``~/code/builder`` scenario.

    Worktree mode is the default; no mode-selector interaction needed.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, _ = start_fake_terminal_agent(page, agents_dir, workspace_name="Local only worktree")
    send_fake_agent_command(agents_dir, write_file("hello.py", "print('hello')\n"))

    task_page.activate_changes_panel(scope="uncommitted")

    # Bug 1: The "All" scope button must be present for a local-only repo
    # once the target_branch fallback resolves to a local main/master.
    changes_panel = task_page.get_changes_panel()
    scope_all = changes_panel.get_scope_all()
    expect(scope_all).to_be_visible()

    # Bug 2: The Uncommitted tab must list the file the agent just wrote.
    changes_tree = changes_panel.get_changes_tree()
    expect(changes_tree).to_be_visible()
    tree_rows = changes_tree.get_tree_rows()
    expect(tree_rows.filter(has_text="hello.py")).to_be_visible()
