"""Tests for the harness registry's read-side resolver.

Terminal-config resolution is covered in
`agents/terminal_agent/harness_test.py`; this file pins the registry's
behavior on an unknown config.
"""

import pytest

from sculptor.agents.harness_registry import UnknownAgentConfigError
from sculptor.agents.harness_registry import get_harness_for_config
from sculptor.interfaces.agents.agent import AgentConfig


def test_get_harness_for_config_rejects_unknown_config() -> None:
    unknown_config = AgentConfig(object_type="NotARealAgentConfig")
    with pytest.raises(UnknownAgentConfigError):
        # pyrefly: ignore [bad-argument-type]
        get_harness_for_config(unknown_config)
