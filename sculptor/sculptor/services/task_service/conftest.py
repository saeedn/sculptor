from sculptor.primitives.ids import AgentMessageID
from sculptor.primitives.ids import TaskID
from sculptor.state.messages import ChatInputUserMessage
from sculptor.state.messages import Message


def get_user_input_message(task_id: TaskID, message: str) -> Message:
    return ChatInputUserMessage(
        message_id=AgentMessageID(),
        text=message,
    )
