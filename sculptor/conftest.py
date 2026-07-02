import os
import tempfile
import time
from pathlib import Path
from typing import Any
from typing import Generator

import pytest
from _pytest.junitxml import xml_key
from syrupy.assertion import SnapshotAssertion

from sculptor.config.settings import SculptorSettings
from sculptor.config.settings import TEST_LOG_PATH
from sculptor.foundation.async_monkey_patches_test import explode_on_error  # noqa: F401
from sculptor.foundation.concurrency_group import ConcurrencyGroup
from sculptor.foundation.fixtures import empty_temp_git_repo
from sculptor.foundation.fixtures import initial_commit_repo
from sculptor.utils.logs import setup_default_test_logging
from sculptor.utils.shutdown import GLOBAL_SHUTDOWN_EVENT
from sculptor.web.middleware import shutdown_event

# It is important that these fixtures are imported, so that tests in subdirectories have access to them.
# This line is necessary to prevent the formatter from deleting the import statements
EXPLICITLY_IMPORTED_FIXTURES = (empty_temp_git_repo, initial_commit_repo)


# Session budget: fail remaining tests when time runs out so pytest exits
# cleanly and writes JUnit XML. Controlled by SESSION_TIMEOUT_SECONDS env var.
#
# Must be in the root conftest (not a subdirectory conftest imported via
# `import *`) so hooks are registered before pytest_sessionstart fires.
_SESSION_START_ENV_KEY = "_PYTEST_SESSION_START_TIME"


def pytest_sessionstart(session: pytest.Session) -> None:
    # Set the start time once (on the controller). Workers inherit it via env.
    # Uses time.time() (wall clock) so it survives xdist worker restarts.
    if _SESSION_START_ENV_KEY not in os.environ:
        os.environ[_SESSION_START_ENV_KEY] = str(time.time())


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Fail remaining tests if the session time budget is exhausted.

    Also sets the JUnit XML name to the full test ID for exact matching.
    """
    budget = int(os.environ.get("SESSION_TIMEOUT_SECONDS", "0"))
    if budget > 0:
        start_time_str = os.environ.get(_SESSION_START_ENV_KEY)
        if start_time_str is not None:
            elapsed = time.time() - float(start_time_str)
            if elapsed >= budget:
                pytest.fail(f"Session budget exhausted ({elapsed:.0f}s >= {budget}s)")

    xml = item.config.stash.get(xml_key, None)
    if xml is not None:
        xml.node_reporter(item.nodeid).add_attribute("name", item.nodeid)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "external_deps: test requires external services (e.g. network access)")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sculptor-launch-mode",
        choices=["browser", "electron"],
        default="browser",
        help="Frontend launch mode for integration tests: 'browser' (headless Chromium) or 'electron' (Electron dev server via CDP).",
    )
    parser.addoption(
        "--sculptor-trace-to",
        type=str,
        default=None,
        help="If set, pass --trace-to=<path> to the backend launched by the integration harness so the run produces a combined Chrome JSON trace at <path>. Off by default — tracing is heavy-weight, so the harness only enables it when explicitly asked. See docs/development/tracing.md.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    launch_mode = config.getoption("--sculptor-launch-mode", default="browser")
    if launch_mode == "browser":
        for item in items:
            if (
                item.get_closest_marker("electron") is not None
                and item.get_closest_marker("browser_and_electron") is None
            ):
                item.add_marker(pytest.mark.skip(reason="This test requires --sculptor-launch-mode=electron"))
    elif launch_mode == "electron":
        for item in items:
            if item.get_closest_marker("electron") is None and item.get_closest_marker("browser_and_electron") is None:
                item.add_marker(pytest.mark.skip(reason="This test requires --sculptor-launch-mode=browser"))


@pytest.fixture
def is_updating_snapshots_(snapshot: SnapshotAssertion) -> bool:
    return snapshot.session.update_snapshots


@pytest.fixture
def database_url() -> Generator[str, None, None]:
    """
    Fixture to provide a database URL for tests.
    This will create a temporary SQLite database file for each test function.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        database_path = tmp_file.name
    database_url = f"sqlite:///{database_path}"
    try:
        yield database_url
    finally:
        # Clean up the temporary database file
        Path(database_path).unlink(missing_ok=True)


@pytest.fixture
def test_settings(database_url: str, tmp_path: Path) -> SculptorSettings:
    settings = SculptorSettings(
        DATABASE_URL=database_url,
        LOG_PATH=str(TEST_LOG_PATH),
        LOG_LEVEL="TRACE",
        SESSION_TOKEN=None,
    )
    return settings


@pytest.fixture(autouse=True)
def always_explode_on_error(explode_on_error: Any) -> Generator[None, None, None]:  # noqa: F811
    """
    Ensures that we do not log errors or exceptions during testing.

    If your test is checking error handling behavior (and you expect to see a log_exception call),
    use the `expect_exact_logged_errors` decorator to suppress the logging of those errors.
    """
    yield


@pytest.fixture(autouse=True, scope="session")
def configure_logging() -> None:
    setup_default_test_logging()


@pytest.fixture()
def test_root_concurrency_group() -> Generator[ConcurrencyGroup, None, None]:
    with ConcurrencyGroup(name="test_root") as concurrency_group:
        yield concurrency_group


@pytest.fixture(autouse=True)
def reset_shutdown_event() -> Generator[None, None, None]:
    # Without this, the shutdown event remains set after the first test that uses it.
    yield
    shutdown_event().clear()
    GLOBAL_SHUTDOWN_EVENT.clear()
