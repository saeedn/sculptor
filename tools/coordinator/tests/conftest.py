"""Shared fixtures for coordinator tests."""

import pytest


@pytest.fixture(autouse=True)
def _no_ambient_sculpt_signaling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never signal a real Sculptor agent from tests.

    The dev environment often runs these tests INSIDE a Sculptor agent
    shell (sculpt on PATH + SCULPT_AGENT_ID set); an accidental
    `sculpt signal session-id` would overwrite that agent's real session
    id. Tests that want signaling re-set the env var explicitly against
    a fake sculpt binary.
    """
    monkeypatch.delenv("SCULPT_AGENT_ID", raising=False)
    monkeypatch.delenv("SCULPT_WORKSPACE_ID", raising=False)
