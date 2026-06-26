"""
An Agent simply *is* a list of `Message`s.

The meaning of each of the message is defined below.
"""

from __future__ import annotations

import abc
import datetime
from enum import StrEnum
from typing import Annotated
from typing import Mapping

from pydantic import Field
from pydantic import Tag

from sculptor.foundation.pydantic_serialization import MutableModel
from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.pydantic_serialization import build_discriminator
from sculptor.foundation.secrets_utils import Secret
from sculptor.foundation.serialization import SerializedException
from sculptor.foundation.time_utils import get_current_time
from sculptor.interfaces.agents.artifacts import FileAgentArtifact
from sculptor.interfaces.agents.messages import EphemeralAgentMessage
from sculptor.interfaces.agents.messages import EphemeralMessage
from sculptor.interfaces.agents.tasks import TaskState
from sculptor.primitives.ids import AgentMessageID
from sculptor.primitives.ids import TaskID as TaskID
from sculptor.services.workspace_service.environment_manager.environments.local_environment import LocalEnvironment
from sculptor.state.claude_state import ParsedAgentResponsePassthrough
from sculptor.state.claude_state import ParsedToolResultResponse
from sculptor.state.messages import AgentMessageSource
from sculptor.state.messages import ChatInputUserMessage
from sculptor.state.messages import Message
from sculptor.state.messages import PersistentAgentMessage
from sculptor.state.messages import PersistentMessage

ParsedAgentResponseType = ParsedAgentResponsePassthrough | ParsedToolResultResponse


class Agent(MutableModel, abc.ABC):
    @abc.abstractmethod
    def pop_messages(self) -> list[MessageTypes]: ...

    @abc.abstractmethod
    def push_message(self, message: Message) -> None: ...

    @abc.abstractmethod
    def terminate(self, force_kill_seconds: float = 5.0) -> None: ...

    @abc.abstractmethod
    def poll(self) -> int | None: ...

    @abc.abstractmethod
    def wait(self, timeout: float) -> int:
        """
        Wait for the agent to finish running and return the exit code.

        Raises:
            AgentCrashed: If some part of the agent code failed with an unexpected exception.
            WaitTimeoutAgentError: If the agent did not finish within the specified timeout.
        """

    @abc.abstractmethod
    def start(
        self,
        secrets: Mapping[str, str | Secret],
    ) -> None: ...


EnvironmentTypes = LocalEnvironment


class EphemeralUserMessage(EphemeralMessage):
    """
    One of two base classes for messages sent from the user.
    Ephemeral user messages are not saved to the database.
    Ephemeral user messages are sent immediately to the agent and are not queued in the task runner.
    """

    # Override inherited fields
    object_type: str = Field(description="Type discriminator for user messages")
    message_id: AgentMessageID = Field(
        default_factory=AgentMessageID,
        description="Unique identifier for the user message",
    )
    source: AgentMessageSource = Field(default=AgentMessageSource.USER)
    approximate_creation_time: datetime.datetime = Field(
        default_factory=get_current_time,
        description="Approximate UTC timestamp when user message was created",
    )


class InterruptProcessUserMessage(EphemeralUserMessage):
    object_type: str = Field(default="InterruptProcessUserMessage")


class RemoveQueuedMessageUserMessage(EphemeralUserMessage):
    object_type: str = Field(default="RemoveQueuedMessageUserMessage")
    target_message_id: AgentMessageID = Field(description="ID of the message to be removed from the queue")


PersistentUserMessageUnion = Annotated[ChatInputUserMessage, Tag("ChatInputUserMessage")]
EphemeralUserMessageUnion = (
    Annotated[InterruptProcessUserMessage, Tag("InterruptProcessUserMessage")]
    | Annotated[RemoveQueuedMessageUserMessage, Tag("RemoveQueuedMessageUserMessage")]
)
UserMessageUnion = PersistentUserMessageUnion | EphemeralUserMessageUnion


class PersistentRunnerMessage(PersistentMessage):
    """Base class for messages sent from the runner."""

    source: AgentMessageSource = AgentMessageSource.RUNNER


class EphemeralRunnerMessage(EphemeralMessage):
    """Base class for messages sent from the runner."""

    source: AgentMessageSource = AgentMessageSource.RUNNER


class EnvironmentAcquiredRunnerMessage(EphemeralRunnerMessage):
    """Emitted when the task acquires an environment from its workspace."""

    object_type: str = "EnvironmentAcquiredRunnerMessage"
    # TODO(SCU-135): Remove this field when git/diff operations move to workspace level.
    # The environment will be accessed via WorkspaceService instead of this message.
    environment: EnvironmentTypes


class EnvironmentReleasedRunnerMessage(EphemeralRunnerMessage):
    """Emitted when the task handler releases the environment to the workspace."""

    object_type: str = "EnvironmentReleasedRunnerMessage"


class KilledAgentRunnerMessage(PersistentRunnerMessage):
    object_type: str = "KilledAgentRunnerMessage"


class ErrorMessage(SerializableModel):
    pass
    # TODO: remove the `error` field from the subclasses and enable it here.
    # this will require a schema migration
    # error: SerializedException


class AgentCrashedRunnerMessage(PersistentRunnerMessage, ErrorMessage):
    """
    Note that (like EnvironmentCrashedRunnerMessage and UnexpectedErrorRunnerMessage),
    this can happen before *or after* the agent has finished processing a given message.
    """

    object_type: str = "AgentCrashedRunnerMessage"
    exit_code: int | None
    error: SerializedException


class EnvironmentCrashedRunnerMessage(PersistentRunnerMessage, ErrorMessage):
    object_type: str = "EnvironmentCrashedRunnerMessage"
    error: SerializedException


class UnexpectedErrorRunnerMessage(PersistentRunnerMessage, ErrorMessage):
    object_type: str = "UnexpectedErrorRunnerMessage"
    error: SerializedException


class TaskStatusRunnerMessage(EphemeralRunnerMessage):
    object_type: str = "TaskStatusRunnerMessage"
    outcome: TaskState


class TerminalStatusSignal(StrEnum):
    """Status vocabulary a terminal-agent integration may signal.

    `files-changed` and `session-id` are events, not status — they never
    become one of these values.
    """

    BUSY = "BUSY"
    IDLE = "IDLE"
    WAITING = "WAITING"


class TerminalAgentSignalRunnerMessage(EphemeralRunnerMessage):
    """A status signal posted by a terminal agent's integration.

    Ephemeral on purpose: signals are run-scoped (they survive frontend
    reloads via the in-memory replay but vanish on backend restart) and
    never drive unread tracking.
    """

    object_type: str = "TerminalAgentSignalRunnerMessage"
    signal: TerminalStatusSignal


PersistentRunnerMessageUnion = (
    Annotated[KilledAgentRunnerMessage, Tag("KilledAgentRunnerMessage")]
    | Annotated[AgentCrashedRunnerMessage, Tag("AgentCrashedRunnerMessage")]
    | Annotated[EnvironmentCrashedRunnerMessage, Tag("EnvironmentCrashedRunnerMessage")]
    | Annotated[UnexpectedErrorRunnerMessage, Tag("UnexpectedErrorRunnerMessage")]
)
EphemeralRunnerMessageUnion = (
    Annotated[TaskStatusRunnerMessage, Tag("TaskStatusRunnerMessage")]
    | Annotated[EnvironmentAcquiredRunnerMessage, Tag("EnvironmentAcquiredRunnerMessage")]
    | Annotated[EnvironmentReleasedRunnerMessage, Tag("EnvironmentReleasedRunnerMessage")]
    | Annotated[TerminalAgentSignalRunnerMessage, Tag("TerminalAgentSignalRunnerMessage")]
)
RunnerMessageUnion = PersistentRunnerMessageUnion | EphemeralRunnerMessageUnion


class UpdatedArtifactAgentMessage(EphemeralAgentMessage):
    object_type: str = "UpdatedArtifactAgentMessage"
    artifact: FileAgentArtifact


class RequestCompleteAgentMessage(abc.ABC):
    request_id: AgentMessageID
    error: SerializedException | None


class PersistentRequestCompleteAgentMessage(PersistentAgentMessage, RequestCompleteAgentMessage, abc.ABC): ...


class RequestSuccessAgentMessage(PersistentRequestCompleteAgentMessage):
    object_type: str = "RequestSuccessAgentMessage"
    # pyrefly: ignore [bad-override]
    request_id: AgentMessageID
    # pyrefly: ignore [bad-override]
    error: None = None
    interrupted: bool = False


PersistentAgentMessageUnion = Annotated[RequestSuccessAgentMessage, Tag("RequestSuccessAgentMessage")]
EphemeralAgentMessageUnion = Annotated[UpdatedArtifactAgentMessage, Tag("UpdatedArtifactAgentMessage")]
AgentMessageUnion = PersistentAgentMessageUnion | EphemeralAgentMessageUnion
# this is necessary because pydantic won't let us use PersistentMessageTypes, which already has a discriminator, to make MessageTypes
PersistentMessageTypesUnannotated = (
    PersistentAgentMessageUnion | PersistentRunnerMessageUnion | PersistentUserMessageUnion
)
PersistentMessageTypes = Annotated[PersistentMessageTypesUnannotated, build_discriminator()]

EphemeralMessageTypes = EphemeralAgentMessageUnion | EphemeralRunnerMessageUnion | EphemeralUserMessageUnion

MessageTypes = Annotated[
    PersistentMessageTypesUnannotated | EphemeralMessageTypes,
    build_discriminator(),
]


class AgentConfig(SerializableModel):
    object_type: str


class TerminalAgentConfig(AgentConfig):
    object_type: str = "TerminalAgentConfig"


class RegisteredTerminalAgentConfig(AgentConfig):
    """A terminal agent that launches a registered program in its shell.

    Launch parameters are stamped at creation from the registration so the
    task stays self-describing even if the registration file later changes.
    """

    object_type: str = "RegisteredTerminalAgentConfig"
    registration_id: str
    display_name: str
    launch_command: str
    # May contain the literal placeholder `{session_id}`.
    resume_command_template: str | None = None
    accepts_automated_prompts: bool = False


AgentConfigTypes = Annotated[
    Annotated[TerminalAgentConfig, Tag("TerminalAgentConfig")]
    | Annotated[RegisteredTerminalAgentConfig, Tag("RegisteredTerminalAgentConfig")],
    build_discriminator(),
]

TERMINAL_AGENT_CONFIG_TYPES = (TerminalAgentConfig, RegisteredTerminalAgentConfig)


def is_terminal_agent_config(config: AgentConfigTypes) -> bool:
    return isinstance(config, TERMINAL_AGENT_CONFIG_TYPES)
