import datetime
import json
from abc import ABC
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Generic
from typing import TypeVar
from typing import assert_never

from pydantic import PrivateAttr
from pydantic import Tag
from pydantic import ValidationError
from pydantic import computed_field

from sculptor.agents.harness_registry import get_harness_for_config
from sculptor.config.settings import SculptorSettings
from sculptor.database.models import AgentTaskInputsV2
from sculptor.database.models import AgentTaskStateV2
from sculptor.database.models import BaseTaskState
from sculptor.database.models import MustBeShutDownTaskInputsV1
from sculptor.database.models import NoOpTaskInputsV1
from sculptor.database.models import NoOpTaskStateV1
from sculptor.database.models import Notification
from sculptor.database.models import Project
from sculptor.database.models import Task
from sculptor.database.models import TaskID
from sculptor.database.models import TaskInputs
from sculptor.database.models import UserSettings
from sculptor.database.models import Workspace
from sculptor.foundation.itertools import only
from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.pydantic_serialization import build_discriminator
from sculptor.interfaces.agents.agent import EnvironmentAcquiredRunnerMessage
from sculptor.interfaces.agents.agent import EnvironmentReleasedRunnerMessage
from sculptor.interfaces.agents.agent import PersistentRequestCompleteAgentMessage
from sculptor.interfaces.agents.agent import RegisteredTerminalAgentConfig
from sculptor.interfaces.agents.agent import TerminalAgentSignalRunnerMessage
from sculptor.interfaces.agents.agent import TerminalStatusSignal
from sculptor.interfaces.agents.agent import UpdatedArtifactAgentMessage
from sculptor.interfaces.agents.artifacts import AgentTaskStatus
from sculptor.interfaces.agents.artifacts import ArtifactType
from sculptor.interfaces.agents.artifacts import TaskListArtifact
from sculptor.interfaces.agents.harness import Harness
from sculptor.interfaces.agents.harness import HarnessCapabilities
from sculptor.interfaces.agents.tasks import TaskState
from sculptor.primitives.ids import ProjectID
from sculptor.primitives.ids import WorkspaceID
from sculptor.state.messages import AgentMessageSource
from sculptor.state.messages import ChatInputUserMessage
from sculptor.state.messages import Message
from sculptor.utils.functional import first
from sculptor.web.data_types import PrApproval  # noqa: F401 — re-exported for existing import sites
from sculptor.web.data_types import PrComment  # noqa: F401 — re-exported for existing import sites
from sculptor.web.data_types import PrStatusInfo  # noqa: F401 — re-exported for existing import sites
from sculptor.web.data_types import PrStatusInfoCleared  # noqa: F401 — re-exported for existing import sites
from sculptor.web.data_types import TaskInterface
from sculptor.web.data_types import WorkspaceBranchInfo  # noqa: F401 — re-exported for existing import sites
from sculptor.web.data_types import WorkspaceTargetBranchesInfo  # noqa: F401 — re-exported for existing import sites


class TaskStatus(StrEnum):
    BUILDING = "BUILDING"  # Environment is being set up
    RUNNING = "RUNNING"  # Claude code process is actively running
    READY = "READY"  # Process completed successfully, idle
    WAITING = "WAITING"  # Agent signalled that it is waiting for input
    ERROR = "ERROR"  # Process encountered an error (stderr output)


class WorkspacePeekAgentStatus(StrEnum):
    WORKING = "WORKING"
    WAITING = "WAITING"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"
    IDLE = "IDLE"


def scan_terminal_signal_state(messages: Sequence[Message]) -> tuple[bool, TerminalStatusSignal | None]:
    """(run_started, latest_signal_this_run) from a task's live messages.

    The single home for the run-scoping subtleties shared by the status
    derivation below and the terminal-input endpoint:
    EnvironmentAcquiredRunnerMessage is the run-start anchor — both it and
    the signal messages are ephemeral, so the result reflects the live
    program, resets on every (re)start, and a relaunched program's hooks
    re-drive it. Scanned in reverse: the latest signal wins, but only if it
    arrived after the most recent run start. No anchor at all means the run
    hasn't started (still acquiring the environment).
    """
    latest_signal: TerminalStatusSignal | None = None
    for msg in reversed(messages):
        if latest_signal is None and isinstance(msg, TerminalAgentSignalRunnerMessage):
            latest_signal = msg.signal
        if isinstance(msg, EnvironmentReleasedRunnerMessage):
            # The most recent run has ended (and its environment released)
            # without a newer one acquiring yet — its signals are stale, so
            # treat the agent as not-yet-running rather than reviving them.
            return False, None
        if isinstance(msg, EnvironmentAcquiredRunnerMessage):
            return True, latest_signal
    return False, None


TaskInputType = TypeVar("TaskInputType", bound=TaskInputs)
TaskStateType = TypeVar("TaskStateType", bound=BaseTaskState)


class LimitedBaseTaskView(SerializableModel, Generic[TaskInputType, TaskStateType], ABC):
    """
    This class represents a view of the state of any task that is being executed.

    It is limited in that an implementor shouldn't necessarily _need_ messages

    Note that this class is mutable!  The messages are continually updated over time.
    """

    # the actual task object, wrapped in a list which we effectively use as a mutable reference
    _task_container: list[Task] = PrivateAttr(default_factory=list)

    @property
    def task(self) -> Task:
        return only(self._task_container)

    def update_task(self, task: Task) -> None:
        """Update the underlying task object with fresh data"""
        self._task_container[0] = task

    @property
    def task_input(self) -> TaskInputType:
        # pyrefly: ignore [bad-return]
        return self.task.input_data

    @property
    def task_state(self) -> TaskStateType | None:
        # pyrefly: ignore [bad-return]
        return self.task.current_state

    @computed_field
    @property
    def id(self) -> TaskID:
        return self.task.object_id

    @computed_field
    @property
    def project_id(self) -> ProjectID:
        return self.task.project_id

    @computed_field
    @property
    def created_at(self) -> datetime.datetime:
        return self.task.created_at

    @computed_field
    @property
    def task_status(self) -> TaskState:
        return self.task.outcome

    def _maybe_get_status_from_outcome(self) -> TaskStatus | None:
        """
        NOTE: This is almost always None because outcome is never set while task is running.
        """
        if self.task.outcome == TaskState.FAILED:
            return TaskStatus.ERROR
        if self.task.outcome == TaskState.QUEUED:
            return TaskStatus.BUILDING

        if self.task.outcome in (TaskState.SUCCEEDED, TaskState.CANCELLED, TaskState.DELETED):
            return TaskStatus.READY

        # otherwise, the task is running.
        assert self.task.outcome == TaskState.RUNNING, f"Unexpected task outcome: {self.task.outcome}"
        # if there's no image, we're still building
        if self.task_state is None:
            return TaskStatus.BUILDING
        return None


def _is_content_message(msg: Message) -> bool:
    """Return True if the message represents user-visible content for read/unread tracking.

    Content messages are those that create new visual elements in the chat UI
    (agent responses, errors, warnings, etc.). Non-content messages include:
    - Ephemeral messages (not persisted, recreated on restart)
    - Request lifecycle bookkeeping (RequestComplete)
    - User-initiated messages (the user already knows about their own actions)
    """
    if msg.is_ephemeral:
        return False
    if isinstance(msg, PersistentRequestCompleteAgentMessage):
        return False
    if msg.source == AgentMessageSource.USER:
        return False
    return True


# Maps raw exception class names to user-friendly error messages.
_FRIENDLY_ERROR_NAMES: dict[str, str] = {
    "KeyboardInterrupt": "Agent stopped unexpectedly",
    "SystemExit": "Agent stopped unexpectedly",
}


def _get_last_task_list_artifact(messages: list[Message]) -> TaskListArtifact | None:
    """Return the most recent v2 TaskListArtifact referenced by a PLAN update.

    Walks the message stream backwards looking for an UpdatedArtifactAgentMessage
    whose artifact.name == ArtifactType.PLAN, then reads + parses the on-disk
    file. Skips legacy / unsupported-version files so older artifacts don't
    masquerade as fresh ones.
    """
    for msg in reversed(messages):
        if not isinstance(msg, UpdatedArtifactAgentMessage):
            continue
        if msg.artifact.name != ArtifactType.PLAN:
            continue
        url_str = str(msg.artifact.url)
        if not url_str.startswith("file://"):
            return None
        path = Path(url_str.removeprefix("file://"))
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("object_type") != "TaskListArtifact" or data.get("version") != 2:
            continue
        try:
            return TaskListArtifact.model_validate(data)
        except ValidationError:
            continue
    return None


class TaskView(LimitedBaseTaskView[TaskInputType, TaskStateType], Generic[TaskInputType, TaskStateType], ABC):
    """
    This class represents a view of the state of any task that is being executed.

    The messages serialized and sent separately, but are logically part of the task's state.

    Note that this class is mutable!  The messages are continually updated over time.
    """

    object_type: str

    # our reference to settings (controls some serialized fields)
    _settings_container: list[SculptorSettings] = PrivateAttr(default_factory=list)

    # messages that were sent to or from the task.
    # this attribute is private because it enables easy serialization to the front end.
    _messages: list[Message] = PrivateAttr(default_factory=list)

    @property
    def settings(self) -> SculptorSettings:
        return only(self._settings_container)

    @computed_field
    @property
    def artifact_names(self) -> list[str]:
        artifact_messages = [x for x in self._messages if isinstance(x, UpdatedArtifactAgentMessage)]
        return list({x.artifact.name for x in artifact_messages})

    @computed_field
    @property
    def updated_at(self) -> datetime.datetime:
        if len(self._messages) == 0:
            return self.created_at
        # Only consider messages that represent user-visible content changes.
        # This excludes:
        # - Ephemeral messages (runner state transitions, environment lifecycle, artifact
        #   updates) which are not persisted and can be re-created on server restart.
        # - Request lifecycle messages (RequestStartedAgentMessage,
        #   PersistentRequestCompleteAgentMessage, RemoveQueuedMessageAgentMessage)
        #   which are bookkeeping and don't create visual content in the chat.
        # - User-initiated messages (source=USER) since the user already knows about
        #   their own actions.
        # Without this, updated_at can advance past last_read_at from bookkeeping
        # messages saved to the DB after the frontend's mark_read call, causing
        # previously-read tasks to appear unread after a server restart.
        for msg in reversed(self._messages):
            if _is_content_message(msg):
                return msg.approximate_creation_time
        # No content messages yet (e.g. freshly created task with only a user input)
        # — use the earliest message.
        return self._messages[0].approximate_creation_time

    def add_message(self, message: Message) -> None:
        """During each update, we add the new messages"""
        self._messages.append(message)


class CodingAgentTaskView(TaskView[AgentTaskInputsV2, AgentTaskStateV2]):
    """
    messages are the primary way of interacting with an agent.

    this class is simply a way of deriving the current state of the agent based on the message log.

    because agents are run as idempotent tasks, consumers MUST be able to handle duplicate messages.
    this is particularly tricky because you cannot deduplicate on message_id here --
    the ids may be different between two different runs
    (and that cannot be fixed because different things may have happened)
    consumers *may* process messages in a "task aware" manner, eg,
    by paying attention to the task start and stop messages in order to properly discard outdated messages.
    """

    object_type: str = "CodingAgentTaskView"

    _cache: dict[str, Any] = PrivateAttr(default_factory=dict)

    def add_message(self, message: Message) -> None:
        super().add_message(message)
        self._cache.clear()

    @property
    def _task_data(self) -> TaskListArtifact | None:
        if "task" not in self._cache:
            self._cache["task"] = _get_last_task_list_artifact(self._messages)
        return self._cache["task"]

    @computed_field
    @property
    def initial_prompt(self) -> str:
        return self.goal

    @computed_field
    @property
    def title_or_something_like_it(self) -> str:
        return self.title or self.initial_prompt

    @computed_field
    @property
    def interface(self) -> TaskInterface:
        return TaskInterface.API

    @computed_field
    @property
    def harness_capabilities(self) -> HarnessCapabilities:
        return self._resolve_harness().capabilities()

    @computed_field
    @property
    def accepts_automated_prompts(self) -> bool:
        # Stamped from the registration TOML at creation: only opted-in
        # registered terminal agents can receive automated prompts through
        # the terminal-input endpoint.
        agent_config = self.task_input.agent_config
        return isinstance(agent_config, RegisteredTerminalAgentConfig) and agent_config.accepts_automated_prompts

    @computed_field
    @property
    def is_deleted(self) -> bool:
        return self.task.is_deleted or self.task.is_deleting

    @computed_field
    @property
    def last_read_at(self) -> datetime.datetime | None:
        return self.task.last_read_at

    @computed_field
    @property
    def title(self) -> str | None:
        task_state = self.task_state
        if task_state is None:
            return None
        assert isinstance(task_state, AgentTaskStateV2)
        return task_state.title

    @computed_field
    @property
    def status(self) -> TaskStatus:
        task_from_outcome = self._maybe_get_status_from_outcome()
        if task_from_outcome is not None:
            return task_from_outcome

        # Every agent is a terminal agent: status comes from the latest signal
        # posted since the most recent run start. No signals this run → calm
        # neutral READY; signals never drive the unread dot. No run-start anchor
        # at all → still acquiring the environment.
        run_started, latest_signal = scan_terminal_signal_state(self._messages)
        if not run_started:
            return TaskStatus.BUILDING
        if latest_signal == TerminalStatusSignal.BUSY:
            return TaskStatus.RUNNING
        if latest_signal == TerminalStatusSignal.WAITING:
            return TaskStatus.WAITING
        return TaskStatus.READY

    def _resolve_harness(self) -> Harness:
        """Return the `Harness` this task's config resolves to."""
        return get_harness_for_config(self.task_input.agent_config)

    @computed_field
    @property
    def goal(self) -> str:
        # Get the first ChatInputUserMessage
        goal = first(x.text for x in self._messages if isinstance(x, ChatInputUserMessage))

        # NOTE: this is due to a quirk in the task subscription system.
        # goal should *rarely* be None, but it will be None for a single frame when the task is first created.
        if goal is None:
            return ""
        return goal

    @computed_field
    @property
    def workspace_id(self) -> WorkspaceID | None:
        """The workspace ID associated with this task.

        In Phase 1, workspaces are created implicitly 1:1 with tasks.
        """
        task_state = self.task_state
        if task_state is None:
            return None
        assert isinstance(task_state, AgentTaskStateV2)
        return task_state.workspace_id

    def _compute_workspace_peek_status(self) -> WorkspacePeekAgentStatus:
        if self.task.outcome == TaskState.SUCCEEDED:
            return WorkspacePeekAgentStatus.COMPLETED
        # For all other states, derive from TaskStatus which already handles WAITING.
        status_map: dict[TaskStatus, WorkspacePeekAgentStatus] = {
            TaskStatus.BUILDING: WorkspacePeekAgentStatus.WORKING,
            TaskStatus.RUNNING: WorkspacePeekAgentStatus.WORKING,
            TaskStatus.WAITING: WorkspacePeekAgentStatus.WAITING,
            TaskStatus.ERROR: WorkspacePeekAgentStatus.ERROR,
            TaskStatus.READY: WorkspacePeekAgentStatus.IDLE,
        }
        return status_map[self.status]

    @computed_field
    @property
    def workspace_peek_status(self) -> WorkspacePeekAgentStatus:
        if "wps" not in self._cache:
            self._cache["wps"] = self._compute_workspace_peek_status()
        return self._cache["wps"]

    @computed_field
    @property
    def task_completed(self) -> int:
        artifact = self._task_data
        if artifact is None:
            return 0
        return sum(1 for t in artifact.tasks if t.status == AgentTaskStatus.COMPLETED)

    @computed_field
    @property
    def task_total(self) -> int:
        artifact = self._task_data
        if artifact is None:
            return 0
        return len(artifact.tasks)

    @computed_field
    @property
    def current_task_subject(self) -> str | None:
        artifact = self._task_data
        if artifact is None:
            return None
        for task in artifact.tasks:
            if task.status == AgentTaskStatus.IN_PROGRESS:
                return task.subject
        return None

    @computed_field
    @property
    def error_detail(self) -> str | None:
        if self.status != TaskStatus.ERROR:
            return None
        error = self.task.error
        if error is not None:
            if error.args:
                first_arg = error.args[0]
                if isinstance(first_arg, str):
                    return first_arg
            return _FRIENDLY_ERROR_NAMES.get(error.exception, error.exception)
        return None


class NoOpTaskView(TaskView[NoOpTaskInputsV1, NoOpTaskStateV1]):
    object_type: str = "NoOpTaskView"


TaskViewTypes = Annotated[
    Annotated[CodingAgentTaskView, Tag("CodingAgentTaskView")] | Annotated[NoOpTaskView, Tag("NoOpTaskView")],
    build_discriminator(),
]


class UserUpdate(SerializableModel):
    user_settings: UserSettings | None = None
    projects: tuple[Project, ...] = ()
    workspaces: tuple[Workspace, ...] = ()
    settings: SculptorSettings | None = None
    notifications: tuple[Notification, ...] = ()


def create_initial_task_view(
    task: Task,
    settings: SculptorSettings,
) -> TaskViewTypes:
    task_view_class: type[TaskViewTypes]
    match task.input_data:
        case AgentTaskInputsV2():
            task_view_class = CodingAgentTaskView
        case NoOpTaskInputsV1():
            task_view_class = NoOpTaskView
        case MustBeShutDownTaskInputsV1():
            assert False, "MustBeShutDownTaskInputsV1 should only occur in testing"
        case _ as unreachable:
            assert_never(unreachable)
    instance = task_view_class()
    instance._task_container.append(task)
    instance._settings_container.append(settings)
    return instance
