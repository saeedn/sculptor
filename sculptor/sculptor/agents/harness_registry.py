"""The harness registry — the one module that names every concrete `Harness`.

A new harness is added by importing its singleton and adding one `case`
branch to `get_harness_for_config`. See architecture §1.4–§1.5.
"""

from __future__ import annotations

from sculptor.agents.terminal_agent.harness import TERMINAL_HARNESS
from sculptor.foundation.errors import ExpectedError
from sculptor.interfaces.agents.agent import AgentConfigTypes
from sculptor.interfaces.agents.agent import RegisteredTerminalAgentConfig
from sculptor.interfaces.agents.agent import TerminalAgentConfig
from sculptor.interfaces.agents.harness import Harness


class UnknownAgentConfigError(ExpectedError):
    """Raised when an `AgentConfigTypes` value has no harness registered for it."""


def get_harness_for_config(config: AgentConfigTypes) -> Harness:
    """Return the `Harness` this config resolves to.

    The read-side resolver for harness-agnostic consumers that hold a stored
    `agent_config` (e.g. `web/derived.py`). See architecture §2.1.
    """
    match config:
        case TerminalAgentConfig() | RegisteredTerminalAgentConfig():
            return TERMINAL_HARNESS
        case _:
            raise UnknownAgentConfigError(f"Unknown agent config: {config}")
