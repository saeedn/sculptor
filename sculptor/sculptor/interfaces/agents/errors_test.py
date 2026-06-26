from sculptor.foundation.serialization import SerializedException
from sculptor.interfaces.agents.errors import AgentCrashed


def test_serialization():
    try:
        raise AgentCrashed(
            "Agent exited with exit code 2.",
            exit_code=2,
            metadata={"stderr": "some data", "stdout": "some more data"},
        )
    except AgentCrashed as e:
        serialized_exception = SerializedException.build(e)
        # pyrefly: ignore [missing-attribute]
        assert serialized_exception.construct_instance().exit_code == 2
