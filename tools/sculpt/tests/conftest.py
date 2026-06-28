"""Shared test fixtures for sculpt CLI tests."""

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def unset_sculpt_env_vars() -> Iterator[None]:
    """Unset SCULPT_ env vars to ensure tests use defaults."""
    env_vars = ["SCULPT_API_PORT", "SCULPT_WORKSPACE_ID", "SCULPT_AGENT_ID", "SCULPT_PROJECT_ID"]
    old_values = {key: os.environ.pop(key, None) for key in env_vars}
    yield
    for key, value in old_values.items():
        if value is not None:
            os.environ[key] = value
