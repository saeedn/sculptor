"""
Test the API endpoints for the Sculptor application.

NOTE: Endpoints are not currently tested for cross-user authorization (preventing users from changing resources such as
     tasks or user profiles belonging to other users). This coverage is needed before any multi-user deployment.

"""

from pathlib import Path
from typing import Generator

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import sculptor.services.user_config.user_config as user_config_module
from sculptor.config.user_config import UserConfig
from sculptor.database.models import AgentTaskInputsV2
from sculptor.database.models import AgentTaskStateV2
from sculptor.database.models import Project
from sculptor.database.models import Task
from sculptor.database.models import TaskID
from sculptor.database.models import Workspace
from sculptor.foundation.pydantic_serialization import model_dump
from sculptor.foundation.pydantic_utils import model_update
from sculptor.interfaces.agents.agent import RegisteredTerminalAgentConfig
from sculptor.interfaces.agents.agent import TerminalAgentConfig
from sculptor.primitives.ids import ProjectID
from sculptor.primitives.ids import RequestID
from sculptor.service_collections.service_collection import CompleteServiceCollection
from sculptor.services.data_model_service.data_types import DataModelTransaction
from sculptor.services.terminal_agent_registry import registry as registry_module
from sculptor.services.user_config.user_config import set_user_config_instance
from sculptor.web.app import _agent_config_for_request
from sculptor.web.auth import SESSION_TOKEN_HEADER_NAME
from sculptor.web.auth import UserSession
from sculptor.web.auth import authenticate_anonymous
from sculptor.web.data_types import AgentTypeName
from sculptor.web.data_types import CreateAgentRequest

# Check session token enforcement on a sample authenticated endpoint.


def test_endpoints_return_403_when_session_token_required_but_not_set(
    client_with_session_token_required: TestClient,
) -> None:
    response = client_with_session_token_required.get("/api/v1/config")
    assert response.status_code == 403


def test_endpoints_return_200_when_session_token_required_and_set(
    client_with_session_token_required: TestClient,
) -> None:
    response = client_with_session_token_required.get(
        "/api/v1/config", headers={SESSION_TOKEN_HEADER_NAME: "test_token"}
    )
    assert response.status_code == 200


def test_endpoints_return_200_when_session_token_required_and_set_via_a_get_param(
    client_with_session_token_required: TestClient,
) -> None:
    response = client_with_session_token_required.get(f"/api/v1/config?{SESSION_TOKEN_HEADER_NAME}=test_token")
    assert response.status_code == 200


def test_endpoints_return_200_when_session_token_required_and_set_via_a_cookie(
    client_with_session_token_required: TestClient,
) -> None:
    response = client_with_session_token_required.get(
        "/api/v1/config", cookies={SESSION_TOKEN_HEADER_NAME: "test_token"}
    )
    assert response.status_code == 200


def test_endpoints_return_200_when_api_secret_key_not_required_and_not_set(client: TestClient) -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200


def test_health_endpoint_never_requires_a_token(client_with_session_token_required: TestClient) -> None:
    response = client_with_session_token_required.get("/api/v1/health")
    assert response.status_code == 200


def test_get_session_token_returns_204_and_sets_cookie_even_when_header_not_set(
    client_with_session_token_required: TestClient,
) -> None:
    response = client_with_session_token_required.get("/api/v1/session-token")
    assert response.status_code == 204
    assert "set-cookie" in response.headers
    assert response.headers["set-cookie"].startswith(SESSION_TOKEN_HEADER_NAME)
    assert response.headers["set-cookie"].endswith("; HttpOnly; Path=/; SameSite=strict")
    assert "test_token" in response.headers["set-cookie"]


def _create_workspace(
    transaction: DataModelTransaction,
    services: CompleteServiceCollection,
    project: Project,
    description: str = "test workspace",
) -> Workspace:
    """Create an IN_PLACE workspace for testing."""
    return services.workspace_service.create_workspace(
        project=project,
        source_branch=None,
        requested_branch_name=None,
        description=description,
        transaction=transaction,
    )


def _create_task_in_workspace(
    transaction: DataModelTransaction,
    user_session: UserSession,
    project: Project,
    services: CompleteServiceCollection,
    workspace: Workspace,
    agent_config: TerminalAgentConfig | RegisteredTerminalAgentConfig | None = None,
) -> Task:
    """Create a task associated with a specific workspace."""
    task_id = TaskID()
    task = Task(
        object_id=task_id,
        user_reference=user_session.user_reference,
        organization_reference=user_session.organization_reference,
        project_id=project.object_id,
        input_data=AgentTaskInputsV2(
            agent_config=agent_config if agent_config is not None else TerminalAgentConfig(),
            git_hash="doesn't matter",
            system_prompt=None,
        ),
        current_state=AgentTaskStateV2(workspace_id=workspace.object_id),
    )
    services.task_service.create_task(task, transaction)
    return task


def _create_task_with_message_in_workspace(
    transaction: DataModelTransaction,
    user_session: UserSession,
    project: Project,
    services: CompleteServiceCollection,
    workspace: Workspace,
) -> Task:
    """Create a task associated with a workspace (create_task emits its QUEUED status message)."""
    return _create_task_in_workspace(transaction, user_session, project, services, workspace)


def test_resolve_agent_by_prefix_unique(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        task = _create_task_with_message_in_workspace(
            transaction, user_session, test_project, test_services, workspace
        )
    full_id = str(task.object_id)
    response = client.get(f"/api/v1/agents/by-prefix/{full_id[:10]}")
    assert response.status_code == 200
    assert response.json()["agentId"] == full_id


def test_resolve_agent_by_prefix_full_id(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        task = _create_task_with_message_in_workspace(
            transaction, user_session, test_project, test_services, workspace
        )
    full_id = str(task.object_id)
    response = client.get(f"/api/v1/agents/by-prefix/{full_id}")
    assert response.status_code == 200
    assert response.json()["agentId"] == full_id


def test_resolve_agent_by_prefix_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/agents/by-prefix/tsk_doesnotexist")
    assert response.status_code == 404


def test_resolve_agent_by_prefix_ambiguous(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        _create_task_with_message_in_workspace(transaction, user_session, test_project, test_services, workspace)
        _create_task_with_message_in_workspace(transaction, user_session, test_project, test_services, workspace)
    response = client.get("/api/v1/agents/by-prefix/tsk_")
    assert response.status_code == 409


def test_delete_agent_removes_task(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        task_1 = _create_task_with_message_in_workspace(
            transaction, user_session, test_project, test_services, workspace
        )
        task_2 = _create_task_with_message_in_workspace(
            transaction, user_session, test_project, test_services, workspace
        )
    response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/{task_1.object_id}")
    assert response.status_code in (200, 204)
    response = client.get(f"/api/v1/workspaces/{workspace.object_id}/agents")
    assert response.status_code == 200
    data = response.json()
    for item in data:
        if item["id"] != str(task_2.object_id):
            assert item["isDeleted"]


def test_delete_agent_returns_404_if_agent_does_not_exist(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
    response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/{TaskID()}")
    assert response.status_code == 404


def test_delete_agent_returns_422_if_id_is_invalid(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
    response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/onetwo")
    assert response.status_code == 422


def test_manual_422_responses_use_validation_error_list_format(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    """Manual HTTPException(422) responses must use the same list-of-dicts format
    as FastAPI's automatic Pydantic validation errors, so the generated client
    can parse them without crashing."""
    # Use an invalid workspace ID to trigger validate_workspace_id's manual 422
    response = client.get("/api/v1/workspaces/not-a-valid-id/agents")
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], list), (
        f"Expected detail to be a list, got {type(body['detail'])}: {body['detail']}"
    )
    assert len(body["detail"]) >= 1
    error = body["detail"][0]
    assert "loc" in error
    assert "msg" in error
    assert "type" in error


def test_update_naming_pattern_performs_update(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    new_pattern = "feature/{slug}"
    response = client.put(
        f"/api/v1/projects/{test_project.object_id}/naming_pattern",
        json={"requestId": str(RequestID()), "namingPattern": new_pattern},
    )
    assert response.status_code == 200
    assert response.json() == new_pattern
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        project = transaction.get_project(test_project.object_id)
        assert project is not None
        assert project.naming_pattern == new_pattern


def test_update_naming_pattern_returns_404_for_missing_project(client: TestClient) -> None:
    nonexistent_project_id = ProjectID()
    response = client.put(
        f"/api/v1/projects/{nonexistent_project_id}/naming_pattern",
        json={"requestId": str(RequestID()), "namingPattern": "x/{slug}"},
    )
    assert response.status_code == 404


@pytest.mark.skip(reason="We need to resolve user project boostrapping first.")
def test_get_repo_info_returns_200(client: TestClient, test_project: Project) -> None:
    response = client.get(f"/api/v1/projects/{test_project.object_id}/repo_info")
    assert response.status_code == 200
    data = response.json()
    assert "repo_path" in data
    assert "current_branch" in data


def test_delete_agent_does_not_delete_workspace_when_other_agents_exist(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    """Create 2 agents sharing a workspace. Delete one. Verify workspace still exists."""
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project, description="shared workspace")
        task_1 = _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)
        task_2 = _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)

    response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/{task_1.object_id}")
    assert response.status_code in (200, 204)

    with user_session.open_transaction(test_services) as transaction:
        remaining_workspace = transaction.get_workspace(workspace.object_id)
        assert remaining_workspace is not None, "Workspace should still exist when another task uses it"
        assert not remaining_workspace.is_deleted

    with user_session.open_transaction(test_services) as transaction:
        remaining_task = test_services.task_service.get_task(task_2.object_id, transaction)
        assert remaining_task is not None
        assert not remaining_task.is_deleted


def test_delete_last_agent_preserves_workspace(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    """Create 1 agent in workspace. Delete it. Verify workspace still exists."""
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project, description="solo workspace")
        task = _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)

    response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/{task.object_id}")
    assert response.status_code in (200, 204)

    # Workspace survives because agents are managed independently from workspaces.
    with user_session.open_transaction(test_services) as transaction:
        remaining_workspace = transaction.get_workspace(workspace.object_id)
        assert remaining_workspace is not None, "Workspace should survive when its last agent is deleted"
        assert not remaining_workspace.is_deleted


def test_mark_read_sets_last_read_at(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        task = _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)

    response = client.patch(
        f"/api/v1/workspaces/{workspace.object_id}/agents/{task.object_id}/mark-read",
    )
    assert response.status_code == 200

    with user_session.open_transaction(test_services) as transaction:
        updated_task = test_services.task_service.get_task(task.object_id, transaction)
        assert updated_task is not None
        assert updated_task.last_read_at is not None


def test_mark_read_returns_404_if_agent_does_not_exist(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
    response = client.patch(
        f"/api/v1/workspaces/{workspace.object_id}/agents/{TaskID()}/mark-read",
    )
    assert response.status_code == 404


def test_mark_unread_clears_last_read_at(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        task = _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)

    response = client.patch(
        f"/api/v1/workspaces/{workspace.object_id}/agents/{task.object_id}/mark-read",
    )
    assert response.status_code == 200

    response = client.patch(
        f"/api/v1/workspaces/{workspace.object_id}/agents/{task.object_id}/mark-unread",
    )
    assert response.status_code == 200

    with user_session.open_transaction(test_services) as transaction:
        updated_task = test_services.task_service.get_task(task.object_id, transaction)
        assert updated_task is not None
        assert updated_task.last_read_at is None


def test_mark_unread_returns_404_if_agent_does_not_exist(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
    response = client.patch(
        f"/api/v1/workspaces/{workspace.object_id}/agents/{TaskID()}/mark-unread",
    )
    assert response.status_code == 404


def test_create_agent_does_not_send_intro_message_when_agents_exist(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    """Users with existing agents should not get an auto-sent intro message."""
    user_session = authenticate_anonymous(test_services, RequestID())

    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)
        _create_task_in_workspace(transaction, user_session, test_project, test_services, workspace)

    response = client.post(
        f"/api/v1/workspaces/{workspace.object_id}/agents",
        json=model_dump(CreateAgentRequest(), is_camel_case=True),
    )
    assert response.status_code == 200
    agent_id = response.json()["id"]

    with user_session.open_transaction(test_services) as transaction:
        # pyrefly: ignore [missing-attribute]
        saved_messages = transaction.get_messages_for_tasks([TaskID(agent_id)]).get(TaskID(agent_id), ())
    assert len(saved_messages) == 0


# Config + onboarding endpoints.


@pytest.fixture
def onboarding_test_config(tmp_path, monkeypatch) -> Generator[UserConfig, None, None]:
    """A fresh anonymous config, as it exists before onboarding completes."""
    monkeypatch.setattr(user_config_module, "_CONFIG_PATH", tmp_path / "config.toml")
    config = user_config_module.get_default_user_config_instance()
    set_user_config_instance(config)
    yield config
    set_user_config_instance(None)


def test_put_user_config_passes_through(client: TestClient, onboarding_test_config: UserConfig) -> None:
    response = client.put(
        "/api/v1/config",
        json={"userConfig": {"envVarOverrideEnabled": True}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["envVarOverrideEnabled"] is True


def test_complete_onboarding_succeeds_for_anonymous_user(
    client: TestClient, onboarding_test_config: UserConfig
) -> None:
    """Onboarding completion just persists the current config and returns 200."""
    response = client.post("/api/v1/config/complete")
    assert response.status_code == 200, response.text


# Agent-type creation path (terminal agents).


def test_agent_config_for_request_resolves_each_type() -> None:
    # Agent type comes only from the creation request.
    assert isinstance(_agent_config_for_request(AgentTypeName.TERMINAL, None), TerminalAgentConfig)
    with pytest.raises(HTTPException) as exc_info:
        _agent_config_for_request(AgentTypeName.REGISTERED, "some-registration")
    assert exc_info.value.status_code == 422


def _post_agent(client: TestClient, workspace: Workspace, body: dict) -> httpx.Response:
    return client.post(f"/api/v1/workspaces/{workspace.object_id}/agents", json=body)


def test_create_terminal_agent_stamps_terminal_config_and_names_terminal_n(
    client: TestClient, test_services: CompleteServiceCollection, test_project: Project
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    first = _post_agent(client, workspace, {"agentType": "terminal"})
    assert first.status_code == 200, first.text
    assert first.json()["title"] == "Terminal 1"
    first_task_id = TaskID(first.json()["id"])

    with user_session.open_transaction(test_services) as transaction:
        task = test_services.task_service.get_task(first_task_id, transaction)
    assert task is not None
    assert isinstance(task.input_data, AgentTaskInputsV2)
    assert task.input_data.agent_config.object_type == "TerminalAgentConfig"

    second = _post_agent(client, workspace, {"agentType": "terminal"})
    assert second.status_code == 200, second.text
    assert second.json()["title"] == "Terminal 2"

    # Lowest-available reuse: deleting "Terminal 1" frees its number.
    delete_response = client.delete(f"/api/v1/workspaces/{workspace.object_id}/agents/{first_task_id}")
    assert delete_response.status_code in (200, 204)
    third = _post_agent(client, workspace, {"agentType": "terminal"})
    assert third.status_code == 200, third.text
    assert third.json()["title"] == "Terminal 1"


@pytest.fixture
def isolated_user_config(tmp_path, monkeypatch) -> Generator[None, None, None]:
    """Isolate the on-disk config path and reset the config singleton after.

    The most-recently-used harness tests set a real config instance (so the
    server records/reads it) and must not write the developer's actual config
    or leak the singleton into other tests.
    """
    monkeypatch.setattr(user_config_module, "_CONFIG_PATH", tmp_path / "config.toml")
    yield
    set_user_config_instance(None)


def _set_user_config_with(**fields: object) -> None:
    set_user_config_instance(model_update(user_config_module.get_default_user_config_instance(), fields))


def _agent_config_for_created(response: httpx.Response, test_services: CompleteServiceCollection) -> object:
    task_id = TaskID(response.json()["id"])
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        task = test_services.task_service.get_task(task_id, transaction)
    assert task is not None
    assert isinstance(task.input_data, AgentTaskInputsV2)
    return task.input_data.agent_config


def test_create_agent_without_type_uses_mru_harness(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    isolated_user_config: None,
) -> None:
    """A prompt-less create with no agent_type resolves the user's stored MRU."""
    _set_user_config_with(last_used_agent_type="terminal")
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    response = _post_agent(client, workspace, {})
    assert response.status_code == 200, response.text
    assert isinstance(_agent_config_for_created(response, test_services), TerminalAgentConfig)
    assert response.json()["title"] == "Terminal 1"


def test_create_agent_records_explicit_type_as_mru(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    isolated_user_config: None,
) -> None:
    """An explicit agent_type is persisted as the new most-recently-used harness."""
    _set_user_config_with()  # no MRU yet
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    assert _post_agent(client, workspace, {"agentType": "terminal"}).status_code == 200
    assert user_config_module.get_user_config_instance().last_used_agent_type == "terminal"


def test_create_agent_without_type_defaults_to_bundled_claude_code_when_mru_unset(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    isolated_user_config: None,
    registrations_dir: Path,
) -> None:
    """A prompt-less create with no MRU defaults to the bundled claude-code agent."""
    (registrations_dir / "claude-code.toml").write_text('display_name = "Claude CLI"\nlaunch_command = "claude"\n')
    _set_user_config_with()  # no MRU
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    response = _post_agent(client, workspace, {})
    assert response.status_code == 200, response.text
    config = _agent_config_for_created(response, test_services)
    assert isinstance(config, RegisteredTerminalAgentConfig)
    assert config.registration_id == "claude-code"


def test_create_agent_without_type_falls_back_to_terminal_when_bundled_absent(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    isolated_user_config: None,
    registrations_dir: Path,
) -> None:
    """With no MRU and no bundled registration, creation falls back to a plain terminal (never throws)."""
    _set_user_config_with()  # no MRU; registrations_dir is empty
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    response = _post_agent(client, workspace, {})
    assert response.status_code == 200, response.text
    assert isinstance(_agent_config_for_created(response, test_services), TerminalAgentConfig)


# Terminal-agent registrations.


@pytest.fixture
def registrations_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(registry_module, "get_sculptor_folder", lambda: tmp_path)
    directory = tmp_path / "terminal_agents"
    directory.mkdir()
    return directory


def test_list_terminal_agent_registrations_rereads_per_request(client: TestClient, registrations_dir: Path) -> None:
    response = client.get("/api/v1/terminal-agent-registrations")
    assert response.status_code == 200
    assert response.json()["registrations"] == []

    # A file dropped between two calls appears without a restart (no caching).
    (registrations_dir / "claude-code.toml").write_text('display_name = "Claude Code"\nlaunch_command = "claude"\n')
    response = client.get("/api/v1/terminal-agent-registrations")
    assert response.status_code == 200
    listed = response.json()["registrations"]
    assert [r["registrationId"] for r in listed] == ["claude-code"]
    assert listed[0]["displayName"] == "Claude Code"


def test_list_terminal_agent_registrations_skips_bad_files(client: TestClient, registrations_dir: Path) -> None:
    (registrations_dir / "broken.toml").write_text("not [valid toml")
    (registrations_dir / "good.toml").write_text('display_name = "Good"\nlaunch_command = "good"\n')

    response = client.get("/api/v1/terminal-agent-registrations")

    assert response.status_code == 200
    assert [r["registrationId"] for r in response.json()["registrations"]] == ["good"]


def test_create_registered_agent_stamps_resolved_config_and_names_from_display_name(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    registrations_dir: Path,
) -> None:
    (registrations_dir / "claude-code.toml").write_text(
        """\
display_name = "Claude Code"
launch_command = "claude"
resume_command_template = "claude --resume {session_id}"
accepts_automated_prompts = true
"""
    )
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    response = _post_agent(client, workspace, {"agentType": "registered", "registrationId": "claude-code"})
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Claude Code 1"

    with user_session.open_transaction(test_services) as transaction:
        task = test_services.task_service.get_task(TaskID(response.json()["id"]), transaction)
    assert task is not None
    assert isinstance(task.input_data, AgentTaskInputsV2)
    config = task.input_data.agent_config
    assert isinstance(config, RegisteredTerminalAgentConfig)
    assert config.registration_id == "claude-code"
    assert config.display_name == "Claude Code"
    assert config.launch_command == "claude"
    assert config.resume_command_template == "claude --resume {session_id}"
    assert config.accepts_automated_prompts is True


def test_create_registered_agent_with_unknown_or_deleted_registration_fails(
    client: TestClient,
    test_services: CompleteServiceCollection,
    test_project: Project,
    registrations_dir: Path,
) -> None:
    user_session = authenticate_anonymous(test_services, RequestID())
    with user_session.open_transaction(test_services) as transaction:
        workspace = _create_workspace(transaction, test_services, test_project)

    assert _post_agent(client, workspace, {"agentType": "registered", "registrationId": "nope"}).status_code == 422

    # Menu-raced deletion: the file existed when the menu listed it but is
    # gone by creation time.
    path = registrations_dir / "fleeting.toml"
    path.write_text('display_name = "Fleeting"\nlaunch_command = "x"\n')
    assert client.get("/api/v1/terminal-agent-registrations").json()["registrations"]
    path.unlink()
    response = _post_agent(client, workspace, {"agentType": "registered", "registrationId": "fleeting"})
    assert response.status_code == 422
    assert "fleeting" in response.json()["detail"]
