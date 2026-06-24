"""Integration test: diff refreshes when the current branch changes.

When the current branch changes, the file browser should update to reflect
the new branch's diff — just like it already does when the target branch
changes.
"""

import subprocess
from pathlib import Path

from playwright.sync_api import expect

from sculptor.testing.elements.file_tree import get_changes_tree
from sculptor.testing.fake_terminal_agent import send_fake_agent_command_and_wait
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _get_workspace_working_dir(sculptor_instance: SculptorInstance) -> Path:
    """Find the clone workspace's working directory.

    After a workspace is created via the UI (clone mode), the clone lives at
    ``sculptor_folder / "workspaces" / env_id / "code"``.
    """
    workspaces_dir = sculptor_instance.sculptor_folder / "workspaces"
    code_dirs = sorted(workspaces_dir.glob("*/code"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert code_dirs, f"No workspace clone found under {workspaces_dir}"
    return code_dirs[0]


@user_story("to see the diff update when the current branch changes")
def test_diff_refreshes_when_current_branch_changes(sculptor_instance_: SculptorInstance) -> None:
    """The changes tree should update when the current branch changes.

    Steps:
    1. Agent writes hello.py — it appears in the Uncommitted changes tree.
    2. *Outside* the agent (directly on the filesystem), commit hello.py and
       check out a new branch at the fork point so the workspace has zero diff.
    3. The branch polling manager detects the branch change within 3 seconds
       and pushes a WebSocket update.  The frontend should detect this, clear
       stale diff data, and refetch — making hello.py disappear from Changes.

    By performing the checkout outside the agent, ``on_diff_needed()`` does
    NOT fire, so the only path that can update the diff is the frontend
    detecting the branch change via the ``workspaceBranchAtomFamily`` atom.
    """
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    # Step 1: Create the workspace and have the agent write a file. Wait for the
    # write to land so the changes tree is populated before we inspect it.
    task_page, _ = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command_and_wait(agents_dir, write_file("hello.py", "print('hello')\n"))

    # Open the Changes panel (Uncommitted scope) and verify hello.py is listed.
    task_page.activate_changes_panel(scope="uncommitted")
    # Force a fresh diff fetch: on a freshly-created workspace the initial
    # files-changed signal can land before the frontend's diff subscription is
    # ready, leaving the changes tree empty until an explicit refetch.
    task_page.get_file_browser().get_refresh_button().click()
    changes_tree = get_changes_tree(page)
    expect(changes_tree).to_be_visible()
    hello_row = changes_tree.get_tree_rows().filter(has_text="hello.py")
    expect(hello_row).to_be_visible()

    # Wait for branch polling to publish its baseline before changing the
    # branch externally. The polling callback's diff-refresh path only fires
    # on a branch *transition* (`repo_polling_manager.py` — requires
    # `_last_branch is not None`); the first poll fires 3s after the poller
    # starts, so without this wait, a fast checkout can beat the first poll
    # and set the baseline to the new branch — bypassing the refresh.
    task_page.get_branch_name_element()

    # Step 2: Commit and checkout *outside* the agent — no on_diff_needed().
    workspace_dir = _get_workspace_working_dir(sculptor_instance_)
    subprocess.run(
        ["git", "add", "hello.py"],
        cwd=workspace_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Add hello"],
        cwd=workspace_dir,
        check=True,
        capture_output=True,
    )
    # Check out a new branch at the fork point (HEAD~1, the commit before
    # hello.py was committed) so the workspace has zero diff vs the target
    # branch again. Worktree-mode workspaces have no `origin/main` ref to
    # target, so we use the parent commit, which is the target fork point.
    subprocess.run(
        ["git", "checkout", "-b", "fresh-from-main", "HEAD~1"],
        cwd=workspace_dir,
        check=True,
        capture_output=True,
    )

    # Step 3: The changes tree should no longer show hello.py.
    # Allow up to 15 seconds for the branch polling (3s interval) to detect
    # the change and the frontend to clear + refetch the diff.
    expect(hello_row).to_be_hidden(timeout=15_000)
