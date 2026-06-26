"""Shared setup + error-handling helpers for the terminal-agent task handler.

These were previously hosted in the (now-removed) rich `run_agent` handler;
the terminal handler is the only surviving consumer, so they live here.
"""

from loguru import logger

from sculptor.database.models import AgentTaskStateV2
from sculptor.database.models import Notification
from sculptor.database.models import NotificationID
from sculptor.database.models import NotificationImportance
from sculptor.database.models import Project
from sculptor.database.models import Task
from sculptor.foundation.async_monkey_patches import log_exception
from sculptor.foundation.common import is_live_debugging
from sculptor.foundation.concurrency_group import ConcurrencyExceptionGroup
from sculptor.foundation.concurrency_group import ConcurrentShutdownError
from sculptor.foundation.constants import ExceptionPriority
from sculptor.foundation.errors import ExpectedError
from sculptor.foundation.event_utils import CancelledByEventError
from sculptor.foundation.event_utils import ReadOnlyEvent
from sculptor.foundation.nested_evolver import assign
from sculptor.foundation.nested_evolver import chill
from sculptor.foundation.nested_evolver import evolver
from sculptor.foundation.serialization import SerializedException
from sculptor.interfaces.agents.agent import AgentCrashedRunnerMessage
from sculptor.interfaces.agents.agent import EnvironmentCrashedRunnerMessage
from sculptor.interfaces.agents.agent import KilledAgentRunnerMessage
from sculptor.interfaces.agents.agent import PersistentRequestCompleteAgentMessage
from sculptor.interfaces.agents.agent import PersistentRunnerMessageUnion
from sculptor.interfaces.agents.agent import RequestSuccessAgentMessage
from sculptor.interfaces.agents.agent import UnexpectedErrorRunnerMessage
from sculptor.interfaces.agents.errors import AgentCrashed
from sculptor.interfaces.environments.errors import EnvironmentFailure
from sculptor.primitives.ids import AgentMessageID
from sculptor.primitives.ids import TaskID
from sculptor.primitives.ids import UserReference
from sculptor.services.data_model_service.data_types import DataModelTransaction
from sculptor.services.task_service.data_types import ServiceCollectionForTask
from sculptor.services.task_service.errors import TaskError
from sculptor.services.task_service.errors import UserPausedTaskError
from sculptor.services.task_service.errors import UserStoppedTaskError
from sculptor.state.messages import PersistentUserMessage
from sculptor.utils.shutdown import GLOBAL_SHUTDOWN_EVENT


class AgentTaskFailure(TaskError):
    pass


class AgentHardKilled(ExpectedError):
    pass


class AgentShutdownCleanly(ExpectedError):
    pass


class AgentPaused(AgentShutdownCleanly):
    """
    The agent was paused by the user (typically via ctrl-c) and will be resumed when the process restarts.
    """


def _is_truly_processed_completion(message: PersistentRequestCompleteAgentMessage) -> bool:
    """True iff this completion represents the agent actually finishing the user message.

    An interrupted completion (``RequestSuccessAgentMessage(interrupted=True)``) does
    NOT count, because the agent didn't really finish processing the message. If we
    counted it here, dedup would treat the message as processed and silently drop it on
    the next run — which loses the user's typed input in the post-answer-shutdown
    scenario.
    """
    if isinstance(message, RequestSuccessAgentMessage) and message.interrupted:
        return False
    return True


def _reconcile_last_processed_from_history(
    task_state: AgentTaskStateV2,
    task_id: TaskID,
    services: ServiceCollectionForTask,
) -> AgentTaskStateV2:
    """Return task_state with last_processed_message_id derived from message history.

    Walks the persisted messages for this task, finds the latest user message whose
    ``message_id`` matches some ``PersistentRequestCompleteAgentMessage.request_id``
    where the completion represents truly-finished processing (see
    ``_is_truly_processed_completion``), and uses that as the effective
    ``last_processed_message_id``. Only upgrades the cursor (never downgrades), so a
    stale persisted value heals to the truth from the message log without ever
    moving backward.
    """
    with services.data_model_service.open_task_transaction() as transaction:
        all_messages = services.task_service.get_saved_messages_for_task(task_id, transaction)

    completed_request_ids: set[AgentMessageID] = set()
    for message in all_messages:
        if isinstance(message, PersistentRequestCompleteAgentMessage) and _is_truly_processed_completion(message):
            completed_request_ids.add(message.request_id)

    latest_completed_user_message_id: AgentMessageID | None = None
    for message in all_messages:
        if isinstance(message, PersistentUserMessage) and message.message_id in completed_request_ids:
            latest_completed_user_message_id = message.message_id

    if latest_completed_user_message_id is None:
        return task_state
    current = task_state.last_processed_message_id
    if current is not None and str(latest_completed_user_message_id) <= str(current):
        # Don't downgrade — current cursor is already at or ahead of what history shows.
        return task_state
    logger.debug(
        "Reconciled last_processed_message_id from {} to {} based on persisted completions",
        current,
        latest_completed_user_message_id,
    )
    mutable = evolver(task_state)
    assign(mutable.last_processed_message_id, lambda: latest_completed_user_message_id)
    return chill(mutable)


def load_initial_task_state(services: ServiceCollectionForTask, task: Task) -> tuple[AgentTaskStateV2, Project]:
    logger.debug("loading initial task state")
    with services.data_model_service.open_task_transaction() as transaction:
        task_row = transaction.get_task(task.object_id)
        assert task_row is not None, "Task must exist in the database"
        if task_row.current_state is None:
            # Tasks are created with current_state in start_task(), so this should never happen.
            raise RuntimeError(f"Task {task.object_id} has no current_state. All tasks must have initial state.")
        logger.debug("loading existing task state...")
        task_state = AgentTaskStateV2.model_validate(task_row.current_state)
        # load the project so that we can figure out the repo path as well
        project = transaction.get_project(task.project_id)
        assert project is not None, "Project must exist in the database"

        # Reconcile last_processed_message_id with persisted message history.
        # A SIGKILL / OOM / power loss between the success-path message write and
        # the cursor write can leave the DB with a persisted completion but a stale
        # last_processed cursor; reconcile from history so dedup heals.
        reconciled_state = _reconcile_last_processed_from_history(task_state, task.object_id, services)
        if reconciled_state.last_processed_message_id != task_state.last_processed_message_id:
            task_state = reconciled_state
            task_row = task_row.evolve(task_row.ref().current_state, task_state.model_dump())
            transaction.upsert_task(task_row)
    return task_state, project


def on_exception(
    e: Exception,
    task_id: TaskID,
    user_reference: UserReference,
    services: ServiceCollectionForTask,
    shutdown_event: ReadOnlyEvent,
) -> None:
    # During graceful shutdown, any ConcurrencyExceptionGroup is shutdown-related (whether it
    # contains one or many exceptions).  Check this BEFORE unwrapping single-exception groups,
    # because the unwrapped exception might not be a recognized shutdown type.
    if isinstance(e, ConcurrencyExceptionGroup) and (shutdown_event.is_set() or GLOBAL_SHUTDOWN_EVENT.is_set()):
        raise UserPausedTaskError() from e

    # For simple exceptions that bubble up wrapped in a ConcurrencyExceptionGroup, unwrap them.
    if isinstance(e, ConcurrencyExceptionGroup) and len(e.exceptions) == 1:
        e = e.exceptions[0]

    # ConcurrentShutdownError is raised when the ConcurrencyGroup is torn down during server
    # shutdown.  Treat it the same as AgentPaused so the task is re-queued, not failed.
    if isinstance(e, ConcurrentShutdownError):
        raise UserPausedTaskError() from e

    # this "exception" is expected in the sense that it was the user telling the task to stop
    # so it doesn't count as success
    if isinstance(e, CancelledByEventError) and (shutdown_event.is_set() or GLOBAL_SHUTDOWN_EVENT.is_set()):
        # Looks like the user cancelled the task even before the agent started.
        raise UserPausedTaskError() from e
    if isinstance(e, (AgentPaused, UserPausedTaskError)):
        raise UserPausedTaskError() from e
    if isinstance(e, AgentShutdownCleanly):
        raise UserStoppedTaskError() from e

    # if the agent has failed, we should notify the user
    is_expected = isinstance(e, ExpectedError)
    if is_expected:
        log_exception(
            exc=e,
            message="Agent runner failed with expected error",
            priority=ExceptionPriority.LOW_PRIORITY,
        )
    else:
        if is_live_debugging():
            raise
        log_exception(
            exc=e,
            message="Agent runner failed with unexpected error",
            priority=ExceptionPriority.MEDIUM_PRIORITY,
        )

    error = e

    # send a message to the user
    is_worth_notifying = True
    agent_error_message: PersistentRunnerMessageUnion
    match error:
        case AgentHardKilled():
            agent_error_message = KilledAgentRunnerMessage(message_id=AgentMessageID())
            # not worth notifying the user about this, they told it to stop
            is_worth_notifying = False
        case AgentCrashed():
            agent_error_message = AgentCrashedRunnerMessage(
                message_id=AgentMessageID(),
                exit_code=error.exit_code,
                error=SerializedException.build(error),
            )
        case EnvironmentFailure():
            agent_error_message = EnvironmentCrashedRunnerMessage(
                message_id=AgentMessageID(),
                error=SerializedException.build(error),
            )
        case _:
            agent_error_message = UnexpectedErrorRunnerMessage(
                message_id=AgentMessageID(),
                error=SerializedException.build(error),
            )

    def on_transaction(t: DataModelTransaction) -> None:
        services.task_service.create_message(agent_error_message, task_id, t)

        # and send a notification to the user if necessary
        if is_worth_notifying:
            task_row = services.task_service.get_task(task_id, t)
            assert task_row is not None
            t.insert_notification(
                Notification(
                    user_reference=user_reference,
                    object_id=NotificationID(),
                    message="Agent failed.",
                    importance=NotificationImportance.TIME_SENSITIVE,
                    task_id=task_row.object_id,
                ),
            )

    # During shutdown, any unrecognized exception should be treated as a pause rather than a failure.
    # This catches cases where exceptions from cleanup code (e.g., DB writes in finally blocks)
    # mask the original shutdown exception.
    if shutdown_event.is_set() or GLOBAL_SHUTDOWN_EVENT.is_set():
        raise UserPausedTaskError() from e

    # raising will ensure that unexpected Exceptions are logged, and that the task is marked as failed
    raise AgentTaskFailure(transaction_callback=on_transaction, is_user_notified=True)
