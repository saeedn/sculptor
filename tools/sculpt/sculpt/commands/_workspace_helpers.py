"""Shared helpers for workspace-creating commands (``sculpt workspace create`` and ``sculpt run``)."""

import httpx

from sculpt.client import Client
from sculpt.client.api.default import preview_branch_name
from sculpt.client.models.http_validation_error import HTTPValidationError
from sculpt.formatting import cli_error
from sculpt.formatting import handle_connection_error


def resolve_requested_branch_name(
    *,
    client: Client,
    project_id: str,
    branch_name: str | None,
    workspace_name: str | None,
    json_output: bool,
) -> str | None:
    """Resolve ``requested_branch_name`` to send when creating a workspace.

    Without an explicit ``--branch-name``, mirror the UI by calling
    ``/api/v1/workspaces/preview-branch-name`` to auto-fill a slug derived from
    the workspace name (or a random one if no name was given).
    """
    if branch_name is not None:
        return branch_name

    try:
        preview = preview_branch_name.sync(
            client=client,
            project_id=project_id,
            workspace_name=workspace_name or "",
        )
    except httpx.ConnectError:
        handle_connection_error(json_output)

    if preview is None:
        cli_error(
            "Failed to resolve branch name for workspace",
            detail="No response from server",
            json_output=json_output,
        )
    if isinstance(preview, HTTPValidationError):
        cli_error("Validation error resolving branch name", detail=str(preview), json_output=json_output)
    return preview.branch_name
