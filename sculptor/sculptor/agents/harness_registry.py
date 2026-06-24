"""The harness registry — the one module that names every concrete `Harness`
and every concrete `Agent`. Owns each harness↔agent factory pair so harness
modules do not import agent modules and vice versa. See architecture §1.4–§1.5.

A new harness is added by importing its singleton and its concrete agent
here and adding one `case` branch to each function below.
"""

from __future__ import annotations

from sculptor.agents.terminal_agent.harness import TERMINAL_HARNESS
from sculptor.foundation.errors import ExpectedError
from sculptor.interfaces.agents.agent import Agent
from sculptor.interfaces.agents.agent import AgentConfigTypes
from sculptor.interfaces.agents.agent import RegisteredTerminalAgentConfig
from sculptor.interfaces.agents.agent import TerminalAgentConfig
from sculptor.interfaces.agents.harness import AgentRunContext
from sculptor.interfaces.agents.harness import Harness


class UnknownAgentConfigError(ExpectedError):
    """Raised when an `AgentConfigTypes` value has no harness registered for it."""


def get_harness_for_config(config: AgentConfigTypes) -> Harness:
    """Return the `Harness` whose agents construct for the given config.

    The read-side resolver for harness-agnostic consumers that hold a stored
    `agent_config` (e.g. `web/derived.py`). See architecture §2.1.
    """
    match config:
        case TerminalAgentConfig() | RegisteredTerminalAgentConfig():
            return TERMINAL_HARNESS
        case _:
            raise UnknownAgentConfigError(f"Unknown agent config: {config}")


def create_agent_for_run(context: AgentRunContext) -> Agent:
    """Construct the `Agent` for `context.task_data.agent_config`.

    Terminal configs (TerminalAgentConfig / RegisteredTerminalAgentConfig)
    never reach this function: they are dispatched to
    `run_terminal_agent_task_v1` in `tasks/api.py`. With the rich chat
    backends removed there is no constructable chat `Agent` left, so every
    config is rejected here — the function survives only as the explicit
    guard for that invariant.
    """
    raise UnknownAgentConfigError(f"Unknown agent config: {context.task_data.agent_config}")
