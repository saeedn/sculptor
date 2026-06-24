"""Integration tests for the sculpt CLI against a running Sculptor backend.

These tests verify that:
- Users can interact with Sculptor via the sculpt CLI and see results in the UI
- Users can interact with Sculptor via the UI and see results via the sculpt CLI
- The CLI's JSON output accurately reflects backend state

Each test uses the shared sculptor_instance_ fixture, which provides a running
Sculptor backend and a Playwright browser page.  The sculpt CLI is invoked as a
subprocess pointed at the backend's URL so its stdout is isolated from the
backend's logging.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import playwright.sync_api
from playwright.sync_api import expect

from sculptor.testing.pages.home_page import PlaywrightHomePage
from sculptor.testing.playwright_utils import navigate_to_home_page
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


def _get_project_id(instance: SculptorInstance, retries: int = 3) -> str:
    """Fetch the active project ID from the running backend with retries.

    Retries on transient connection errors (e.g. ECONNRESET) that can
    occur under heavy CI load.
    """
    base_url = instance.backend_api_url.rstrip("/")
    for attempt in range(retries):
        try:
            response = instance.page.request.get(f"{base_url}/api/v1/projects/active")
            projects = response.json()
            return projects[0]["objectId"] if projects else ""
        except playwright.sync_api.Error:
            if attempt == retries - 1:
                raise
            instance.page.wait_for_timeout(200)
    return ""  # unreachable, but satisfies type checker


def _run_sculpt(instance: SculptorInstance, args: list[str]) -> tuple[int, str]:
    """Invoke the sculpt CLI as a subprocess and return (exit_code, stdout).

    Automatically injects --base-url and --json flags, and sets the
    SCULPT_PROJECT_ID environment variable so the CLI can resolve the project
    without needing cwd-based detection.
    """
    project_id = _get_project_id(instance)

    env = {
        **os.environ,
        "SCULPT_PROJECT_ID": project_id,
    }

    full_args = args + ["--base-url", instance.backend_api_url, "--json"]
    result = subprocess.run(
        [sys.executable, "-m", "sculpt.main"] + full_args,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout


def _run_sculpt_capture(instance: SculptorInstance, args: list[str]) -> tuple[int, str, str]:
    """Like _run_sculpt but does not inject --json and also returns stderr.

    Use for error cases — cli_error writes the message to stderr (which the
    other helpers discard), so asserting on it needs the captured stream.
    """
    project_id = _get_project_id(instance)

    env = {
        **os.environ,
        "SCULPT_PROJECT_ID": project_id,
    }

    full_args = args + ["--base-url", instance.backend_api_url]
    result = subprocess.run(
        [sys.executable, "-m", "sculpt.main"] + full_args,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _assert_is_iso_datetime(value: object) -> None:
    """Assert that a value is a string that looks like an ISO 8601 datetime."""
    assert isinstance(value, str), f"Expected str, got {type(value)}"
    assert len(value) >= 19, f"ISO datetime too short: {value!r}"
    assert "T" in value, f"Missing 'T' separator in ISO datetime: {value!r}"


def _assert_subset(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    """Assert that all key-value pairs in expected are present in actual.

    Produces a clear diff on failure showing only mismatched entries.
    """
    mismatches = {}
    for key, expected_val in expected.items():
        if key not in actual:
            mismatches[key] = {"expected": expected_val, "actual": "<missing>"}
        elif actual[key] != expected_val:
            mismatches[key] = {"expected": expected_val, "actual": actual[key]}
    assert not mismatches, f"Subset mismatch:\n{json.dumps(mismatches, indent=2, default=str)}"


# -- Expected key sets for each command's JSON output --------------------------

WORKSPACE_CREATE_KEYS = {"id", "repo_id", "description", "strategy", "source_branch"}

WORKSPACE_LIST_ALL_KEYS = {
    "id",
    "repo_id",
    "repo_path",
    "description",
    "strategy",
    "source_branch",
    "agent_count",
    "is_open",
    "created_at",
    "last_activity_at",
}

REPO_KEYS = {"id", "name", "path", "accessible", "created_at"}

AGENT_CREATE_KEYS = {"id", "title", "status", "model", "workspace_id", "created_at"}

AGENT_LIST_KEYS = {"id", "title", "status", "model", "workspace_id", "created_at"}

AGENT_SHOW_KEYS = {
    "id",
    "title",
    "status",
    "model",
    "interface",
    "created_at",
    "updated_at",
    "repo_id",
    "workspace_id",
    "is_deleted",
    "artifact_names",
    "current_activity",
    "last_activity",
    "task_completed",
    "task_total",
    "current_task_subject",
    "waiting_detail",
    "error_detail",
}

AGENT_STATUS_KEYS = {
    "id",
    "status",
    "updated_at",
    "current_activity",
    "last_activity",
    "waiting_detail",
    "error_detail",
    "task_completed",
    "task_total",
    "current_task_subject",
}

RUN_KEYS = {"workspace_id", "agent_id", "strategy", "model", "prompt"}


# ---------------------------------------------------------------------------
# Workspace tests: CLI → verify via CLI
# ---------------------------------------------------------------------------


@user_story("to create a workspace via the CLI and confirm it exists")
def test_workspace_create_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace with the sculpt CLI and verify it appears in the workspace list."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "CLI Created")
    assert exit_code == 0, f"workspace create failed: {output}"
    created = json.loads(output)

    assert set(created.keys()) == WORKSPACE_CREATE_KEYS
    _assert_subset(
        {"description": "CLI Created", "strategy": "WORKTREE", "source_branch": base_branch},
        created,
    )

    # List workspaces via CLI and verify the new workspace appears
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0, f"workspace list failed: {output}"
    workspaces = json.loads(output)
    assert isinstance(workspaces, list)
    assert len(workspaces) >= 1

    ws_match = next(w for w in workspaces if w["id"] == created["id"])
    assert set(ws_match.keys()) == WORKSPACE_LIST_ALL_KEYS
    _assert_subset(
        {"description": "CLI Created", "strategy": "WORKTREE", "agent_count": 0},
        ws_match,
    )
    _assert_is_iso_datetime(ws_match["created_at"])
    _assert_is_iso_datetime(ws_match["last_activity_at"])


@user_story("to inspect workspace details via the CLI")
def test_workspace_show_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace and then retrieve its details via `sculpt workspace show`."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Show Test")
    assert exit_code == 0, f"workspace create failed: {output}"
    created = json.loads(output)
    ws_id = created["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "show", ws_id])
    assert exit_code == 0, f"workspace show failed: {output}"
    detail = json.loads(output)

    assert set(detail.keys()) == WORKSPACE_LIST_ALL_KEYS
    _assert_subset(
        {
            "id": ws_id,
            "repo_id": created["repo_id"],
            "description": "Show Test",
            "strategy": "WORKTREE",
            "agent_count": 0,
        },
        detail,
    )
    _assert_is_iso_datetime(detail["created_at"])
    _assert_is_iso_datetime(detail["last_activity_at"])


@user_story("to delete a workspace via the CLI")
def test_workspace_delete_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace, delete it via CLI, and verify it no longer appears in the list."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Delete Me")
    assert exit_code == 0, f"workspace create failed: {output}"
    created = json.loads(output)
    ws_id = created["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "delete", ws_id, "--yes"])
    assert exit_code == 0, f"workspace delete failed: {output}"
    deleted = json.loads(output)
    assert deleted == {"deleted": True, "id": ws_id}

    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0
    workspaces = json.loads(output)
    ws_ids = [w["id"] for w in workspaces]
    assert ws_id not in ws_ids


_WORKTREE_CREATE_TIMEOUT_S = 90.0


def _worktree_paths(user_repo_path: Path) -> list[Path]:
    """Return all worktree paths (except the main one) for the user's repo."""
    result = subprocess.run(
        ["git", "-C", str(user_repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    main_path = user_repo_path.resolve()
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            p = Path(line.removeprefix("worktree ").strip()).resolve()
            if p != main_path:
                paths.append(p)
    return paths


def _worktree_branch(worktree_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(worktree_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _create_workspace_via_cli(instance: SculptorInstance, name: str) -> tuple[int, str]:
    """Create a worktree workspace via ``sculpt workspace create``.

    Worktree (the only surviving strategy) requires an explicit source branch,
    so mirror a real invocation by sourcing the repo's current branch — the same
    value the Add Workspace form pre-selects.
    """
    base_branch = _worktree_branch(instance.project_path)
    return _run_sculpt(
        instance,
        ["workspace", "create", "--name", name, "--strategy", "worktree", "--branch", base_branch],
    )


def _wait_for_new_worktree(
    instance: SculptorInstance,
    before: set[Path],
    timeout_s: float = _WORKTREE_CREATE_TIMEOUT_S,
) -> Path:
    """Poll the user's repo until a new worktree (not in ``before``) appears, then return its path.

    Uses ``page.wait_for_timeout`` instead of ``time.sleep`` so the wait yields to the
    Playwright event loop and matches the project's integration-test idiom.
    """
    deadline = time.monotonic() + timeout_s
    user_repo_path = instance.project_path
    while time.monotonic() < deadline:
        new_paths = set(_worktree_paths(user_repo_path)) - before
        if new_paths:
            return next(iter(new_paths))
        instance.page.wait_for_timeout(500)
    final_paths = set(_worktree_paths(user_repo_path))
    raise AssertionError(f"no new worktree appeared within {timeout_s:.0f}s; git worktree list: {final_paths!r}")


@user_story(
    "to invoke `sculpt run --repo <already-registered path>` without seeing the SCU-1309"
    + " 'Failed to initialize repo (no response)' error"
)
def test_run_with_repo_to_already_registered_path_is_idempotent(
    sculptor_instance_: SculptorInstance,
) -> None:
    """SCU-1309 e2e: when --repo points at a path the backend already has registered
    (the common case for any agent running inside a Sculptor worktree), the CLI used
    to print 'Failed to initialize repo (no response)' and exit 1. With the fix it
    must look up the existing project on the 409 'already added' response and reuse
    its id, so creating a workspace+agent succeeds.

    This test drives the real sculpt subprocess against a real backend, exercising
    the full CLI -> /api/v1/projects/initialize -> /api/v1/projects -> /api/v1/workspaces
    chain. Without the fix, `sculpt run --repo <auto-registered project>` is the exact
    invocation pattern that blocks every agent that tries to spawn a workspace."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, output = _run_sculpt(
        sculptor_instance_,
        [
            "run",
            "scu-1309 idempotent --repo",
            "--repo",
            str(sculptor_instance_.project_path),
            "--model",
            "haiku",
            "--name",
            "SCU-1309 idempotent repo",
            "--strategy",
            "worktree",
            "--branch",
            base_branch,
        ],
    )
    assert exit_code == 0, f"`sculpt run --repo <already-registered>` failed: {output}"
    assert "Failed to initialize repo (no response)" not in output
    result = json.loads(output)
    assert set(result.keys()) == RUN_KEYS
    _assert_subset({"strategy": "WORKTREE", "prompt": "scu-1309 idempotent --repo"}, result)


@user_story("to spawn a worktree-strategy agent via the sculpt CLI with an explicit branch name")
def test_run_creates_worktree_workspace_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """`sculpt run --strategy worktree --branch <base> --branch-name <new>` should create a real
    git worktree on disk on the requested new branch and a workspace whose strategy is WORKTREE."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    new_branch = "dev/cli-worktree-explicit"

    before = set(_worktree_paths(sculptor_instance_.project_path))

    exit_code, output = _run_sculpt(
        sculptor_instance_,
        [
            "run",
            "Do something",
            "--model",
            "haiku",
            "--strategy",
            "worktree",
            "--branch",
            base_branch,
            "--branch-name",
            new_branch,
            "--name",
            "CLI Worktree Explicit",
        ],
    )
    assert exit_code == 0, f"run failed: {output}"
    result = json.loads(output)
    _assert_subset({"strategy": "WORKTREE"}, result)

    # Verify the workspace's recorded strategy/branch via `sculpt workspace show`.
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "show", result["workspace_id"]])
    assert exit_code == 0, f"workspace show failed: {output}"
    ws_detail = json.loads(output)
    _assert_subset(
        {"description": "CLI Worktree Explicit", "strategy": "WORKTREE", "source_branch": base_branch},
        ws_detail,
    )

    worktree_path = _wait_for_new_worktree(sculptor_instance_, before)
    assert worktree_path.exists(), f"worktree path does not exist: {worktree_path}"
    assert _worktree_branch(worktree_path) == new_branch


@user_story("to spawn a worktree-strategy agent via the sculpt CLI without naming the new branch")
def test_run_creates_worktree_workspace_autogen_branch_name(sculptor_instance_: SculptorInstance) -> None:
    """When `--branch-name` is omitted, the CLI mirrors the UI by calling preview-branch-name to
    auto-fill a slug derived from the workspace name."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)

    before = set(_worktree_paths(sculptor_instance_.project_path))

    exit_code, output = _run_sculpt(
        sculptor_instance_,
        [
            "run",
            "Do something",
            "--model",
            "haiku",
            "--strategy",
            "worktree",
            "--branch",
            base_branch,
            "--name",
            "CLI Worktree Autogen",
        ],
    )
    assert exit_code == 0, f"run failed: {output}"
    result = json.loads(output)
    _assert_subset({"strategy": "WORKTREE"}, result)

    worktree_path = _wait_for_new_worktree(sculptor_instance_, before)
    branch_on_worktree = _worktree_branch(worktree_path)
    # The auto-generated slug ends with the slugified workspace name; the full pattern depends
    # on a configurable `<user>/<slug>` prefix, so we only pin the trailing slug.
    assert branch_on_worktree.endswith("cli-worktree-autogen"), (
        f"expected auto-generated branch to end with 'cli-worktree-autogen', got: {branch_on_worktree!r}"
    )


@user_story("to list repos known to the server via the CLI")
def test_repo_list_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """The running test backend should have at least one repo registered."""
    exit_code, output = _run_sculpt(sculptor_instance_, ["repo", "list"])
    assert exit_code == 0, f"repo list failed: {output}"
    repos = json.loads(output)
    assert isinstance(repos, list)
    assert len(repos) >= 1

    repo = repos[0]
    assert set(repo.keys()) == REPO_KEYS
    assert isinstance(repo["id"], str)
    assert isinstance(repo["name"], str)
    assert isinstance(repo["path"], str)
    assert isinstance(repo["accessible"], bool)


@user_story("to show details of a specific repo via the CLI")
def test_repo_show_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Fetch the repo list, then show details for the first repo."""
    exit_code, output = _run_sculpt(sculptor_instance_, ["repo", "list"])
    assert exit_code == 0
    repos = json.loads(output)
    first_repo = repos[0]

    exit_code, output = _run_sculpt(sculptor_instance_, ["repo", "show", first_repo["id"]])
    assert exit_code == 0, f"repo show failed: {output}"
    detail = json.loads(output)

    assert set(detail.keys()) == REPO_KEYS
    _assert_subset(
        {
            "id": first_repo["id"],
            "name": first_repo["name"],
            "path": first_repo["path"],
            "accessible": first_repo["accessible"],
        },
        detail,
    )


# ---------------------------------------------------------------------------
# Workspace tests: CLI ↔ UI cross-channel
# ---------------------------------------------------------------------------


@user_story("to create a workspace via the CLI and see it in the UI")
def test_workspace_created_via_cli_visible_in_ui(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace via the sculpt CLI and verify it appears on the home page."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "CLI Visible In UI")
    assert exit_code == 0, f"workspace create failed: {output}"

    page = sculptor_instance_.page
    navigate_to_home_page(page)

    home_page = PlaywrightHomePage(page)
    workspace_row = home_page.get_workspace_rows().filter(has_text="CLI Visible In UI")
    expect(workspace_row).to_be_visible()


@user_story("to create a workspace in the UI and list it via the CLI")
def test_workspace_created_in_ui_visible_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace through the UI and verify it appears in `sculpt workspace list`."""
    page = sculptor_instance_.page

    start_task_and_wait_for_ready(
        sculptor_page=page,
        prompt="Hello from UI",
        workspace_name="UI Created Workspace",
    )

    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0, f"workspace list failed: {output}"
    workspaces = json.loads(output)

    ws_match = next(w for w in workspaces if w.get("description") == "UI Created Workspace")
    _assert_subset({"strategy": "WORKTREE"}, ws_match)
    assert ws_match["agent_count"] >= 1


@user_story("to delete a workspace via the CLI and see it disappear from the UI")
def test_workspace_deleted_via_cli_disappears_from_ui(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace in the UI, delete it via CLI, and verify it's gone from the home page."""
    page = sculptor_instance_.page

    start_task_and_wait_for_ready(
        sculptor_page=page,
        prompt="Doomed workspace",
        workspace_name="Will Be Deleted",
    )

    # Verify it's on the home page
    navigate_to_home_page(page)
    home_page = PlaywrightHomePage(page)
    workspace_row = home_page.get_workspace_rows().filter(has_text="Will Be Deleted")
    expect(workspace_row).to_be_visible()

    # Find its ID via the CLI
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0
    workspaces = json.loads(output)
    ws = next(w for w in workspaces if w.get("description") == "Will Be Deleted")

    # Delete via CLI
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "delete", ws["id"], "--yes"])
    assert exit_code == 0
    deleted = json.loads(output)
    assert deleted == {"deleted": True, "id": ws["id"]}

    # Verify gone from UI
    navigate_to_home_page(page)
    workspace_row = home_page.get_workspace_rows().filter(has_text="Will Be Deleted")
    expect(workspace_row).not_to_be_visible()


# ---------------------------------------------------------------------------
# Agent tests: CLI → verify via CLI
# ---------------------------------------------------------------------------


@user_story("to create an agent via the CLI and see it in the agent list")
def test_agent_create_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace and agent via the CLI, then list agents in that workspace."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Agent Test WS")
    assert exit_code == 0, f"workspace create failed: {output}"
    ws_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0, f"agent create failed: {output}"
    agent = json.loads(output)

    assert set(agent.keys()) == AGENT_CREATE_KEYS
    _assert_subset({"workspace_id": ws_id}, agent)
    _assert_is_iso_datetime(agent["created_at"])

    # List agents in the workspace
    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "list", "--workspace", ws_id])
    assert exit_code == 0, f"agent list failed: {output}"
    agents = json.loads(output)
    assert isinstance(agents, list)
    assert len(agents) >= 1

    agent_match = next(a for a in agents if a["id"] == agent["id"])
    assert set(agent_match.keys()) == AGENT_LIST_KEYS
    _assert_subset({"workspace_id": ws_id}, agent_match)
    _assert_is_iso_datetime(agent_match["created_at"])


@user_story("to inspect agent details via the CLI")
def test_agent_show_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create an agent and retrieve its details via `sculpt agent show`."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Agent Show WS")
    assert exit_code == 0
    ws = json.loads(output)

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws["id"]])
    assert exit_code == 0
    agent_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "show", agent_id])
    assert exit_code == 0, f"agent show failed: {output}"
    detail = json.loads(output)

    assert set(detail.keys()) == AGENT_SHOW_KEYS
    _assert_subset(
        {
            "id": agent_id,
            "workspace_id": ws["id"],
            "repo_id": ws["repo_id"],
            "interface": "API",
            "is_deleted": False,
        },
        detail,
    )
    assert isinstance(detail["artifact_names"], list)
    assert detail["task_completed"] >= 0
    assert detail["task_total"] >= 0
    _assert_is_iso_datetime(detail["created_at"])
    _assert_is_iso_datetime(detail["updated_at"])


@user_story("to check an agent's status via the CLI")
def test_agent_status_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create an agent and check its status via `sculpt agent status`."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Agent Status WS")
    assert exit_code == 0
    ws_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0
    agent_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "status", agent_id])
    assert exit_code == 0, f"agent status failed: {output}"
    status = json.loads(output)

    assert set(status.keys()) == AGENT_STATUS_KEYS
    _assert_subset({"id": agent_id}, status)
    assert isinstance(status["status"], str)
    assert status["task_completed"] >= 0
    assert status["task_total"] >= 0
    _assert_is_iso_datetime(status["updated_at"])


@user_story("to delete an agent via the CLI")
def test_agent_delete_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create an agent, delete it, and verify it no longer appears in the list."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Agent Delete WS")
    assert exit_code == 0
    ws_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0
    agent_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "delete", agent_id, "--workspace", ws_id])
    assert exit_code == 0, f"agent delete failed: {output}"
    deleted = json.loads(output)
    assert deleted == {"deleted": True, "id": agent_id}

    # If the agent was still running, the delete sets is_deleting for
    # cooperative shutdown — the agent may linger until the runner stops.
    # Poll until the agent disappears from the list.
    page = sculptor_instance_.page
    for _ in range(20):
        exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "list", "--workspace", ws_id])
        assert exit_code == 0
        agents = json.loads(output)
        agent_ids = [a["id"] for a in agents]
        if agent_id not in agent_ids:
            break
        page.wait_for_timeout(500)
    else:
        assert agent_id not in agent_ids, f"Agent {agent_id} still in list after 10s"


# ---------------------------------------------------------------------------
# Agent tests: CLI ↔ UI cross-channel
# ---------------------------------------------------------------------------


@user_story("to create an agent in the UI and list it via the CLI")
def test_agent_created_in_ui_visible_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace and agent through the UI, then list agents via the CLI."""
    page = sculptor_instance_.page

    start_task_and_wait_for_ready(
        sculptor_page=page,
        prompt="Hello from UI agent",
        workspace_name="UI Agent Workspace",
    )

    # List all workspaces via CLI to find the one we just created
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0
    workspaces = json.loads(output)
    ws = next(w for w in workspaces if w.get("description") == "UI Agent Workspace")

    # List agents in that workspace
    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "list", "--workspace", ws["id"]])
    assert exit_code == 0, f"agent list failed: {output}"
    agents = json.loads(output)
    assert len(agents) >= 1

    agent = agents[0]
    assert set(agent.keys()) == AGENT_LIST_KEYS
    _assert_subset({"workspace_id": ws["id"]}, agent)
    _assert_is_iso_datetime(agent["created_at"])


@user_story("to create a workspace and agent via CLI and see the agent in the UI")
def test_agent_created_via_cli_visible_in_ui(sculptor_instance_: SculptorInstance) -> None:
    """Create a workspace and agent via the CLI, then verify the workspace tab appears in the UI."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "CLI Agent UI Check")
    assert exit_code == 0
    ws_id = json.loads(output)["id"]

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0

    # The workspace should appear on the home page
    page = sculptor_instance_.page
    navigate_to_home_page(page)

    home_page = PlaywrightHomePage(page)
    workspace_row = home_page.get_workspace_rows().filter(has_text="CLI Agent UI Check")
    expect(workspace_row).to_be_visible()


@user_story("to create multiple workspaces via CLI and list them all")
def test_multiple_workspaces_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """Create several workspaces via the CLI and verify they all appear in the list."""
    names = ["Multi WS Alpha", "Multi WS Beta", "Multi WS Gamma"]
    created_ids = []

    for name in names:
        exit_code, output = _create_workspace_via_cli(sculptor_instance_, name)
        assert exit_code == 0, f"workspace create failed for {name}: {output}"
        created = json.loads(output)
        _assert_subset({"description": name, "strategy": "WORKTREE"}, created)
        created_ids.append(created["id"])

    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "list", "--all"])
    assert exit_code == 0
    workspaces = json.loads(output)
    listed_ids = [w["id"] for w in workspaces]

    for ws_id in created_ids:
        assert ws_id in listed_ids


@user_story("to use the `sculpt run` shortcut to create a workspace and agent in one step")
def test_run_command_creates_workspace_and_agent(sculptor_instance_: SculptorInstance) -> None:
    """The `sculpt run` command should create a workspace with an agent in a single step."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, output = _run_sculpt(
        sculptor_instance_,
        [
            "run",
            "--model",
            "haiku",
            "--name",
            "Run Command Test",
            "--strategy",
            "worktree",
            "--branch",
            base_branch,
            "Do something",
        ],
    )
    assert exit_code == 0, f"run command failed: {output}"
    result = json.loads(output)

    assert set(result.keys()) == RUN_KEYS
    _assert_subset(
        {"strategy": "WORKTREE", "model": "CLAUDE-4-HAIKU", "prompt": "Do something"},
        result,
    )

    # Verify the workspace exists and has the right description
    ws_id = result["workspace_id"]
    exit_code, output = _run_sculpt(sculptor_instance_, ["workspace", "show", ws_id])
    assert exit_code == 0
    ws_detail = json.loads(output)
    _assert_subset({"description": "Run Command Test", "strategy": "WORKTREE"}, ws_detail)

    # Verify the agent exists in that workspace
    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "list", "--workspace", ws_id])
    assert exit_code == 0
    agents = json.loads(output)
    agent_match = next(a for a in agents if a["id"] == result["agent_id"])
    _assert_subset({"model": "CLAUDE-4-HAIKU"}, agent_match)


# ---------------------------------------------------------------------------
# Harness selection / most-recently-used (MRU) harness tests
#
# The CLI's JSON output has no explicit harness field, but the auto-assigned
# agent title encodes the type ("Claude N" / "Terminal N" / "Pi N"), so these
# tests verify the harness via the title. Terminal is used as the non-default
# harness: it has no enable gate and creates a waiting agent whose title is
# stable (no prompt, so no later prompt-derived rename).
# ---------------------------------------------------------------------------


@user_story("to create agents with --harness and have a bare create reuse the most-recently-used one")
def test_agent_create_harness_records_and_reuses_mru_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """`sculpt agent create --harness X` records X as the default; a later bare create reuses it."""
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Harness MRU WS")
    assert exit_code == 0, f"workspace create failed: {output}"
    ws_id = json.loads(output)["id"]

    # With no --harness and no prior choice, the server defaults to Claude.
    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0, f"agent create failed: {output}"
    assert json.loads(output)["title"].startswith("Claude"), output

    # An explicit --harness creates that type and records it as the new default.
    exit_code, output = _run_sculpt(
        sculptor_instance_, ["agent", "create", "--workspace", ws_id, "--harness", "Terminal"]
    )
    assert exit_code == 0, f"agent create --harness Terminal failed: {output}"
    assert json.loads(output)["title"].startswith("Terminal"), output

    # A subsequent bare create reuses the recorded harness (Terminal), not Claude.
    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "create", "--workspace", ws_id])
    assert exit_code == 0, f"agent create failed: {output}"
    assert json.loads(output)["title"].startswith("Terminal"), output


@user_story("to be told that `sculpt run` cannot create a terminal agent, since it always sends a prompt")
def test_run_rejects_explicit_terminal_harness_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """`sculpt run --harness Terminal` is rejected up front (a terminal agent can't take a prompt)."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, _stdout, stderr = _run_sculpt_capture(
        sculptor_instance_,
        ["run", "do something", "--strategy", "worktree", "--branch", base_branch, "--harness", "Terminal"],
    )
    assert exit_code == 1, f"expected rejection, got exit {exit_code}; stderr={stderr!r}"
    assert "sculpt run" in stderr, stderr


@user_story("to pass an explicit chat harness to `sculpt run`")
def test_run_accepts_explicit_chat_harness_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """`sculpt run --harness Claude` is accepted and creates the workspace + a chat agent."""
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, output = _run_sculpt(
        sculptor_instance_,
        [
            "run",
            "do something",
            "--strategy",
            "worktree",
            "--branch",
            base_branch,
            "--model",
            "haiku",
            "--harness",
            "Claude",
        ],
    )
    assert exit_code == 0, f"run --harness Claude failed: {output}"
    result = json.loads(output)
    assert set(result.keys()) == RUN_KEYS

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "show", result["agent_id"]])
    assert exit_code == 0, f"agent show failed: {output}"
    assert not json.loads(output)["title"].startswith("Terminal"), output


@user_story("to have `sculpt run` reuse the most-recently-used harness, falling back to Claude for a terminal default")
def test_run_reuses_mru_and_falls_back_for_terminal_via_cli(sculptor_instance_: SculptorInstance) -> None:
    """A bare `sculpt run` reads the shared default; a Terminal default falls back to Claude (it has a prompt)."""
    # Record a Terminal default through `agent create` (shares the server-side MRU with run).
    exit_code, output = _create_workspace_via_cli(sculptor_instance_, "Run MRU WS")
    assert exit_code == 0, f"workspace create failed: {output}"
    ws_id = json.loads(output)["id"]
    exit_code, output = _run_sculpt(
        sculptor_instance_, ["agent", "create", "--workspace", ws_id, "--harness", "Terminal"]
    )
    assert exit_code == 0, f"agent create --harness Terminal failed: {output}"
    assert json.loads(output)["title"].startswith("Terminal"), output

    # A bare `run` always sends a prompt, so the Terminal default must fall back to a chat
    # agent rather than failing — the run succeeds and the created agent is not a terminal one.
    base_branch = _worktree_branch(sculptor_instance_.project_path)
    exit_code, output = _run_sculpt(
        sculptor_instance_,
        ["run", "do something", "--strategy", "worktree", "--branch", base_branch, "--model", "haiku"],
    )
    assert exit_code == 0, f"run with a Terminal MRU should fall back to Claude, not fail: {output}"
    result = json.loads(output)
    assert set(result.keys()) == RUN_KEYS

    exit_code, output = _run_sculpt(sculptor_instance_, ["agent", "show", result["agent_id"]])
    assert exit_code == 0, f"agent show failed: {output}"
    assert not json.loads(output)["title"].startswith("Terminal"), output
