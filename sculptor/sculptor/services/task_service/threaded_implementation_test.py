import os
import queue
import time
from pathlib import Path
from typing import cast

import pytest
from loguru import logger

from sculptor.database.models import AgentTaskInputsV2
from sculptor.database.models import Project
from sculptor.database.models import Task
from sculptor.database.models import TaskID
from sculptor.foundation.git import get_repo_base_path
from sculptor.interfaces.agents.agent import MessageTypes
from sculptor.interfaces.agents.agent import TerminalAgentConfig
from sculptor.primitives.ids import RequestID
from sculptor.service_collections.service_collection import CompleteServiceCollection
from sculptor.services.task_service.api import TaskMessageContainer
from sculptor.services.task_service.conftest import get_user_input_message
from sculptor.services.task_service.threaded_implementation import LocalThreadTaskService
from sculptor.state.messages import Message
from sculptor.web.auth import UserSession
from sculptor.web.auth import authenticate_anonymous


@pytest.fixture
def specimen_project(test_service_collection: CompleteServiceCollection) -> Project:
    project_path: str | Path | None = os.getenv("PROJECT_PATH")
    if isinstance(project_path, str):
        project_path = Path(project_path)
    if not project_path:
        project_path = get_repo_base_path()
    user_session = authenticate_anonymous(test_service_collection, RequestID())
    with user_session.open_transaction(test_service_collection) as transaction:
        project = test_service_collection.project_service.initialize_project(
            project_path=project_path,
            organization_reference=user_session.organization_reference,
            transaction=transaction,
        )
    test_service_collection.project_service.activate_project(project)
    assert project is not None, "By now, the project should be initialized."
    return project


def get_simple_task(user_session: UserSession, project: Project) -> Task:
    # Terminal agents are the only surviving task type; the agent runs until the
    # task service shuts it down, which is what these machinery tests exercise.
    return Task(
        object_id=TaskID(),
        user_reference=user_session.user_reference,
        organization_reference=user_session.organization_reference,
        project_id=project.object_id,
        input_data=AgentTaskInputsV2(
            agent_config=TerminalAgentConfig(),
        ),
    )


def assert_message_is_in_update(
    message_queue: queue.Queue[TaskMessageContainer], message: Message, task_id: TaskID, timeout: float = 30.0
) -> None:
    start_time = time.time()
    logger.trace("Searching for message: {}", message)
    while time.time() - start_time < timeout:
        try:
            received_message_container = message_queue.get(timeout=1)
            logger.trace("Received message: {}", received_message_container)
            if any(received_message[0] == message for received_message in received_message_container.messages):
                return
        except queue.Empty:
            continue

    assert False, f"Did not receive expected message within {timeout}s: {message}"


def test_simple_task(test_service_collection: CompleteServiceCollection, specimen_project: Project) -> None:
    user_session = authenticate_anonymous(test_service_collection, RequestID())
    service = test_service_collection.task_service
    assert isinstance(service, LocalThreadTaskService)
    task = get_simple_task(user_session, specimen_project)
    with user_session.open_transaction(test_service_collection) as transaction:
        service.create_task(task, transaction)


def test_subscribe_to_complete_tasks_for_user(
    test_service_collection: CompleteServiceCollection,
    specimen_project: Project,
) -> None:
    user_session = authenticate_anonymous(test_service_collection, RequestID())
    service = test_service_collection.task_service
    task = get_simple_task(user_session, specimen_project)
    with user_session.open_transaction(test_service_collection) as transaction:
        service.create_task(task, transaction)
    first_user_message = get_user_input_message(task.object_id, "Hello, world!")
    with user_session.open_transaction(test_service_collection) as transaction:
        service.create_message(cast(MessageTypes, first_user_message), task.object_id, transaction)
    with service.subscribe_to_all_tasks_for_user(user_reference=task.user_reference) as message_queue:
        assert_message_is_in_update(message_queue, first_user_message, task.object_id)
        second_user_message = get_user_input_message(task.object_id, "Goodbye, world!")
        with user_session.open_transaction(test_service_collection) as transaction:
            service.create_message(cast(MessageTypes, second_user_message), task.object_id, transaction)
        assert_message_is_in_update(message_queue, second_user_message, task.object_id)
