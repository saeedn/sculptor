import pytest

from sculptor.testing.playwright_conftest import *  # noqa: F401, F403


@pytest.fixture(scope="session")
def sculptor_launch_mode(request: pytest.FixtureRequest) -> str:
    """Return the launch mode selected via ``--sculptor-launch-mode``."""
    return request.config.getoption("--sculptor-launch-mode", default="electron")
