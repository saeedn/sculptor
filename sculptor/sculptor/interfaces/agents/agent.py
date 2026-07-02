"""
An Agent simply *is* a list of `Message`s.

The meaning of each of the message is defined below.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Tag

from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.pydantic_serialization import build_discriminator
from sculptor.foundation.serialization import SerializedException
from sculptor.interfaces.agents.messages import EphemeralMessage
from sculptor.primitives.ids import TaskID as TaskID
from sculptor.services.workspace_service.environment_manager.environments.local_environment import LocalEnvironment
from sculptor.state.messages import AgentMessageSource
from sculptor.state.messages import PersistentMessage


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
    environment: LocalEnvironment


class EnvironmentReleasedRunnerMessage(EphemeralRunnerMessage):
    """Emitted when the task handler releases the environment to the workspace."""

    object_type: str = "EnvironmentReleasedRunnerMessage"


class EnvironmentCrashedRunnerMessage(PersistentRunnerMessage):
    object_type: str = "EnvironmentCrashedRunnerMessage"
    error: SerializedException


class UnexpectedErrorRunnerMessage(PersistentRunnerMessage):
    object_type: str = "UnexpectedErrorRunnerMessage"
    error: SerializedException


class TaskStatusRunnerMessage(EphemeralRunnerMessage):
    """Carries no payload: it exists to poke task-update subscribers when a task's outcome changes."""

    object_type: str = "TaskStatusRunnerMessage"


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
    Annotated[EnvironmentCrashedRunnerMessage, Tag("EnvironmentCrashedRunnerMessage")]
    | Annotated[UnexpectedErrorRunnerMessage, Tag("UnexpectedErrorRunnerMessage")]
)
EphemeralRunnerMessageUnion = (
    Annotated[TaskStatusRunnerMessage, Tag("TaskStatusRunnerMessage")]
    | Annotated[EnvironmentAcquiredRunnerMessage, Tag("EnvironmentAcquiredRunnerMessage")]
    | Annotated[EnvironmentReleasedRunnerMessage, Tag("EnvironmentReleasedRunnerMessage")]
    | Annotated[TerminalAgentSignalRunnerMessage, Tag("TerminalAgentSignalRunnerMessage")]
)
# this is necessary because pydantic won't let us use PersistentMessageTypes, which already has a discriminator, to make MessageTypes
PersistentMessageTypesUnannotated = PersistentRunnerMessageUnion
PersistentMessageTypes = Annotated[PersistentMessageTypesUnannotated, build_discriminator()]

EphemeralMessageTypes = EphemeralRunnerMessageUnion

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
