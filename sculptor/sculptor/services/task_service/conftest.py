from sculptor.interfaces.agents.agent import KilledAgentRunnerMessage
from sculptor.primitives.ids import AgentMessageID
from sculptor.primitives.ids import TaskID
from sculptor.state.messages import Message


def get_user_input_message(task_id: TaskID, message: str) -> Message:
    # A distinct persisted message for exercising message storage / stream
    # delivery in tests (terminal agents have no user-message type of their own).
    return KilledAgentRunnerMessage(message_id=AgentMessageID())
