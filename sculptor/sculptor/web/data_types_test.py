"""Unit tests for sculptor.web.data_types."""

from sculptor.database.workspace_enums import WorkspaceInitializationStrategy
from sculptor.web.data_types import CreateWorkspaceRequestV2
from sculptor.web.data_types import StartTaskRequest


def test_create_workspace_request_has_no_harness_field() -> None:
    # Agent type is per-agent; the workspace carries no harness.
    request = CreateWorkspaceRequestV2(
        project_id="proj-1",
        initialization_strategy=WorkspaceInitializationStrategy.WORKTREE,
    )
    assert "harness" not in type(request).model_fields


def test_start_task_request_defaults_agent_type_to_none() -> None:
    # None means "resolve the user's most-recently-used harness" server-side.
    request = StartTaskRequest(prompt="hello")
    assert request.agent_type is None
