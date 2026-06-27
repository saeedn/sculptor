import datetime
from enum import StrEnum

from pydantic import Field

from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.time_utils import get_current_time
from sculptor.primitives.ids import AgentMessageID


class AgentMessageSource(StrEnum):
    """
    Messages can come from the AGENT (in-container LLM), USER (chat messages & direct interactions), and RUNNER (the process controlling a task on the server.)
    """

    # Messages coming directly from the agent from inside the environment.
    AGENT = "AGENT"

    # Messages coming directly from a user interacting with the interface, ie chat
    USER = "USER"

    # Messages coming from the task runner wrapper, such as environment shutdown.
    RUNNER = "RUNNER"


class Message(SerializableModel):
    """Base class for all messages sent to or from the agent and user."""

    # used to dispatch and discover the type of message
    object_type: str
    # the unique ID of the message, used to track it across the system and prevent duplicates.
    message_id: AgentMessageID = Field(default_factory=AgentMessageID)
    # the source of the message, which can be either the agent, user, or runner.
    source: AgentMessageSource
    # roughly when the message was created, in UTC.
    # note that this is approximate due to clock skew -- these messages are created on different machines.
    # you should *not* sort by this field -- instead, rely on the order in which the messages are received.
    approximate_creation_time: datetime.datetime = Field(default_factory=get_current_time)

    # if the message is ephemeral, it will be logged but not saved to the database
    # if it is persistent, it will be logged AND saved to the database
    @property
    def is_ephemeral(self) -> bool:
        raise NotImplementedError("All messages must be subclassed off of PersistentMessage or EphemeralMessage")


class PersistentMessage(Message):
    @property
    def is_ephemeral(self) -> bool:
        return False
