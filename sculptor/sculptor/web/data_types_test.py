"""Unit tests for sculptor.web.data_types."""

from sculptor.web.data_types import CreateWorkspaceRequestV2


def test_create_workspace_request_has_no_harness_field() -> None:
    # Agent type is per-agent; the workspace carries no harness.
    request = CreateWorkspaceRequestV2(
        project_id="proj-1",
    )
    assert "harness" not in type(request).model_fields
