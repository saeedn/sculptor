import pytest

from sculptor.foundation.log_utils import ensure_core_log_levels_configured


@pytest.fixture(scope="session", autouse=True)
def setup_logging_and_secrets() -> None:
    ensure_core_log_levels_configured()
