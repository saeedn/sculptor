import datetime
from typing import Any
from typing import Callable

from sculptor.config.settings import SculptorSettings
from sculptor.database.models import AgentTaskInputsV2
from sculptor.database.models import Task
from sculptor.foundation.concurrency_group import ConcurrencyGroup
from sculptor.foundation.event_utils import ReadOnlyEvent
from sculptor.interfaces.agents.agent import is_terminal_agent_config
from sculptor.services.data_model_service.data_types import DataModelTransaction
from sculptor.services.task_service.data_types import ServiceCollectionForTask
from sculptor.tasks.handlers.run_terminal_agent.v1 import run_terminal_agent_task_v1


def run_task(
    task: Task,
    services: ServiceCollectionForTask,
    task_deadline: datetime.datetime | None,
    settings: SculptorSettings,
    concurrency_group: ConcurrencyGroup,
    shutdown_event: ReadOnlyEvent,
    on_started: Callable[[], None] | None = None,
) -> Callable[[DataModelTransaction], Any] | None:
    """
    Calls the correct task function based on the type of the input_data.

    When `on_started` is provided, it will be called once the task has started processing and (in case of agents) is ready to accept messages.

    """
    data = task.input_data
    # Terminal agents are the only surviving task backend; the dispatch guard
    # stays explicit even though it is now trivially true.
    assert isinstance(data, AgentTaskInputsV2), f"Only agent task inputs are supported; got {type(data).__name__}"
    assert is_terminal_agent_config(data.agent_config), (
        f"Only terminal agent configs are supported; got {type(data.agent_config).__name__}"
    )
    return run_terminal_agent_task_v1(
        data, task, services, task_deadline, settings, concurrency_group, shutdown_event, on_started
    )
