from __future__ import annotations

import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable
from typing import Final
from typing import Generator

import pytest
from loguru import logger
from playwright.sync_api import Playwright
from pytest_playwright.pytest_playwright import ArtifactsRecorder

from sculptor.config.user_config import UserConfig
from sculptor.constants import ElementIDs
from sculptor.foundation.concurrency_group import ConcurrencyGroup
from sculptor.foundation.concurrency_group import ConcurrencyGroupState
from sculptor.service_collections.service_collection import CompleteServiceCollection
from sculptor.services.user_config.user_config import save_config
from sculptor.testing.dependency_stubs import apply_stubs_from_request
from sculptor.testing.dependency_stubs import assert_no_stub_dependency_markers
from sculptor.testing.dependency_stubs import has_stub_dependency_marker_for
from sculptor.testing.dependency_stubs import install_default_claude_stub
from sculptor.testing.electron_frontend import ElectronFrontend
from sculptor.testing.frontend_utils import DEFAULT_TEST_LOCALE
from sculptor.testing.frontend_utils import DEFAULT_TEST_VIEWPORT
from sculptor.testing.frontend_utils import configure_page
from sculptor.testing.mock_repo import MockRepoState
from sculptor.testing.playwright_utils import expect_app_not_onboarding
from sculptor.testing.playwright_utils import navigate_to_frontend
from sculptor.testing.port_manager import PortManager
from sculptor.testing.repo_resources import get_test_project_state
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.sculptor_instance import SculptorInstanceFactory
from sculptor.testing.sculptor_instance import create_sculptor_instance_factory
from sculptor.testing.server_utils import SculptorServer
from sculptor.testing.server_utils import get_sculptor_command_backend_only
from sculptor.testing.server_utils import get_testing_environment
from sculptor.testing.server_utils import start_server_process_and_validate_readiness
from sculptor.testing.subprocess_utils import Forwarder
from sculptor.testing.test_repo_factory import TestRepoFactory

# Timeout for the initial SPA render after server startup (shared + factory instances).
# Longer than the default 30s to allow headroom for cold Electron starts on CI.
# Cold Electron startup on the contended shared CI runners (the
# ``integration_tests_electron`` job) regularly takes 50-60s.
_INITIAL_RENDER_TIMEOUT_MS = 90_000


def invalidate_shared_instance(config: pytest.Config) -> None:
    """Tear down the cached shared instance so the next test recreates it.

    Use from session-scoped fixtures that modify process-level state (e.g. env
    vars) which the shared Electron/backend process reads at startup.  The next
    call to ``sculptor_instance_`` will call ``_get_or_create_shared_instance``
    which will see ``None`` and build a fresh process with the current env.
    """
    cached: SculptorInstance | None = getattr(config, "_sculptor_instance", None)
    if cached is not None:
        logger.info("invalidate_shared_instance: tearing down cached instance")
        cached._teardown()
        setattr(config, "_sculptor_instance", None)


@pytest.fixture
def sculptor_instance_(
    request: pytest.FixtureRequest,
) -> Generator[SculptorInstance, None, None]:
    """Provides a shared Sculptor instance for tests, with per-test cleanup.

    The underlying SculptorInstance is session-scoped (cached on request.config) so
    the backend process and browser stay alive across tests.  Each test gets a fresh
    repo and clean UI state via _pre_test / _post_test hooks.
    """
    # The shared fixture doesn't honour @stub_dependency markers (the backend
    # process is session-scoped with a baked-in claude stub, and _empty_fake_bin_dir
    # re-installs the default between tests).  Fail loudly rather than silently
    # ignore a test's explicit preference — such tests must use the factory fixture.
    assert_no_stub_dependency_markers(request)

    instance = _get_or_create_shared_instance(request)

    # Start artifact recording (including Playwright tracing) *before* _pre_test
    # so that setup failures produce a trace.zip with network/DOM diagnostics.
    artifacts_recorder: ArtifactsRecorder = request.getfixturevalue("_artifacts_recorder")
    artifacts_recorder.on_did_create_browser_context(instance._browser_context)
    try:
        # Group _pre_test actions so the Trace Viewer shows them as a
        # collapsible section separate from the test body.
        instance._browser_context.tracing.group("_pre_test cleanup")
        try:
            instance._pre_test(request)
        finally:
            instance._browser_context.tracing.group_end()
        yield instance
    finally:
        artifacts_recorder.on_will_close_browser_context(instance._browser_context)

    instance._post_test(request)


def _create_initial_repo(name: str, tmp_path: Path) -> MockRepoState:
    """Create the initial test git repo with a single commit on a branch and no remote."""
    repo_dir = tmp_path / "initial_repo"
    initial_state = get_test_project_state()
    with ConcurrencyGroup(name=name) as cg:
        repo = MockRepoState.build_locally(state=initial_state, local_dir=repo_dir, concurrency_group=cg)
    repo.create_reset_and_checkout_branch("testing")
    repo.write_file("src/app.py", "import flask\n\nflask.run()")
    repo.commit("app.py commit", commit_time="2025-01-01T00:00:01")
    repo.write_file("stuff.txt", "stuff")
    repo.commit("Stuff", commit_time="2025-01-01T00:00:02")
    return repo


def _get_or_create_shared_instance(
    request: pytest.FixtureRequest,
) -> SculptorInstance:
    """Return the cached SculptorInstance, creating it on first call."""
    config = request.config
    cached: SculptorInstance | None = getattr(config, "_sculptor_instance", None)
    if cached is not None:
        return cached

    # -- First call: create all session-level resources --
    launch_mode = request.config.getoption("--sculptor-launch-mode", default="browser")
    use_electron = launch_mode == "electron"

    port_manager = PortManager()
    backend_port = port_manager.get_free_port()

    sculptor_folder = Path(tempfile.mkdtemp(prefix="sculptor_test_"))
    tmp_path = Path(tempfile.mkdtemp(prefix="sculptor_tmp_"))
    default_timeout_ms = _DEFAULT_TIMEOUT_MS

    # Temp directories
    # Create a fake bin directory and prepend it to PATH before spawning the
    # backend subprocess, so tests can drop fake CLIs (e.g. gh) into the
    # directory at any time and have the running backend find them via PATH
    # lookup without needing a process restart.
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()
    os.environ["PATH"] = f"{fake_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    # Pre-install the default claude stub and configure the user config to
    # point at it via its absolute path.  Using an absolute path (not a bare
    # command name) avoids PATH-ordering races: the PTY process prepends dirs
    # to PATH when spawning agent tasks, which can push the real claude binary
    # ahead of the stub in the search order.
    claude_stub_path = str(install_default_claude_stub(fake_bin_dir))

    _default_sculptor_folder_populator(sculptor_folder, claude_path=claude_stub_path)

    # Create initial repo
    initial_repo = _create_initial_repo("shared_instance_repo", tmp_path)
    repo_path = initial_repo.base_path

    playwright: Playwright = request.getfixturevalue("playwright")

    database_url = f"sqlite:///{sculptor_folder / 'sculptor.db'}"

    environment = get_testing_environment(
        database_url=database_url,
        sculptor_folder=sculptor_folder,
        tmp_path=tmp_path,
        hide_keys=True,
    )

    # Build command
    command = get_sculptor_command_backend_only(repo_path, port=backend_port)
    # Opt-in tracing: only the shared-fixture path consults
    # ``--sculptor-trace-to`` because the ``just test-tracing`` recipe targets a
    # single test that uses ``sculptor_instance_``. If a future tracing scenario
    # needs the factory path, plumb the flag through its command-building site
    # the same way.
    trace_to_path = request.config.getoption("--sculptor-trace-to", default=None)
    if trace_to_path:
        command = command + (f"--trace-to={trace_to_path}",)

    # Start the backend process
    t0 = time.monotonic()
    env = {k: str(v) for k, v in {**os.environ, **environment}.items() if v is not None}
    server_process = start_server_process_and_validate_readiness(command, env)
    forwarder = Forwarder(server_process)
    forwarder.start()
    server = SculptorServer(process=server_process, port=backend_port)
    logger.info("[timing] Backend startup: {:.2f}s", time.monotonic() - t0)

    # Launch the frontend (browser or Electron)
    t1 = time.monotonic()
    if use_electron:
        electron_frontend = ElectronFrontend(
            playwright=playwright,
            backend_port=backend_port,
            port_manager=port_manager,
            timeout_ms=default_timeout_ms,
        )
        browser_context, page = electron_frontend.__enter__()
        browser = None
    else:
        electron_frontend = None
        browser = playwright.chromium.launch()
        browser_context = browser.new_context(viewport=DEFAULT_TEST_VIEWPORT, locale=DEFAULT_TEST_LOCALE)
        page = browser_context.new_page()
        configure_page(page, timeout_ms=default_timeout_ms)
        navigate_to_frontend(page=page, url=server.url)
    logger.info(
        "[timing] Frontend launch ({}): {:.2f}s", "electron" if use_electron else "browser", time.monotonic() - t1
    )

    # Wait for the React SPA to render before interacting with the UI.
    # Use a longer timeout than the default 30s for this initial check to
    # allow headroom for cold Electron starts on CI.
    t2 = time.monotonic()
    add_ws_button = page.get_by_test_id(ElementIDs.ADD_WORKSPACE_BUTTON)
    try:
        expect_app_not_onboarding(page, add_ws_button, timeout=_INITIAL_RENDER_TIMEOUT_MS)
    except Exception:
        logger.warning("[timing] SPA render failed after {:.2f}s", time.monotonic() - t2)
        if electron_frontend is not None:
            electron_frontend.__exit__(None, None, None)
        raise
    logger.info("[timing] SPA initial render: {:.2f}s", time.monotonic() - t2)
    logger.info("[timing] Total instance startup: {:.2f}s", time.monotonic() - t0)

    # Capture the SPA's own origin (sculptor://app in Electron, the backend URL
    # in browser mode) now that it has rendered, so between-test resets navigate
    # to the renderer rather than the backend API URL.
    frontend_url = page.url.split("#")[0].rstrip("/")

    # Build the instance
    instance = SculptorInstance(
        server=server,
        page=page,
        frontend_url=frontend_url,
        repo=initial_repo,
        sculptor_folder=sculptor_folder,
        fake_bin_dir=fake_bin_dir,
        project_path=repo_path,
        browser_context=browser_context,
        browser=browser,
        default_timeout_ms=default_timeout_ms,
        forwarder=forwarder,
    )

    # Cache on config for session reuse
    config._sculptor_instance = instance
    if use_electron:
        config._electron_frontend = electron_frontend

    # Register session-level teardown via pytest finalizer (not atexit) so it
    # runs while Playwright's session fixtures are still alive.
    def _session_teardown() -> None:
        # _teardown() closes the current page and browser context.
        instance._teardown()
        if browser is not None:
            try:
                browser.close()
            except Exception:
                logger.debug("Browser already closed during teardown")
        if use_electron:
            electron_frontend_instance = getattr(config, "_electron_frontend", None)
            if electron_frontend_instance is not None:
                try:
                    electron_frontend_instance.__exit__(None, None, None)
                except Exception:
                    logger.debug("ElectronFrontend cleanup error during teardown")
        shutil.rmtree(sculptor_folder, ignore_errors=True)
        shutil.rmtree(tmp_path, ignore_errors=True)

    request.session.addfinalizer(_session_teardown)

    return instance


@pytest.fixture
def sculptor_instance_factory_(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[SculptorInstanceFactory, None, None]:
    """Provides a factory for creating isolated Sculptor instances.

    Each test gets fully independent resources (database, sculptor folder, repo,
    backend port).  Use this when a test needs to stop/restart Sculptor or
    requires custom configuration that cannot be shared.

    Mutually exclusive with sculptor_instance_.
    """
    if hasattr(request, "fixturenames") and "sculptor_instance_" in request.fixturenames:
        pytest.fail("Cannot use both sculptor_instance_ and sculptor_instance_factory_ in the same test")

    port_manager = PortManager()
    backend_port = port_manager.get_free_port()

    sculptor_folder = Path(tempfile.mkdtemp(prefix="sculptor_factory_test_"))
    folder_populator: CustomFolderPopulator = (
        _extract_marker_arg(request, custom_sculptor_folder_populator) or _default_sculptor_folder_populator
    )
    folder_populator(sculptor_folder)

    # Keep the DB path aligned with where the backend derives it by default
    # ({SCULPTOR_FOLDER}/internal/database.db, derived in get_sculptor_folder)
    # so populators that pre-seed a database keep working.
    database_url = f"sqlite:///{sculptor_folder / 'internal' / 'database.db'}"

    default_timeout_ms = _DEFAULT_TIMEOUT_MS

    base_repo = _create_initial_repo("factory_instance_repo", tmp_path)

    # Fake bin directory for test-owned CLI stubs; prepended to PATH so the
    # backend subprocesses this factory spawns find anything tests drop in.
    # The spawned backend subprocesses inherit PATH from os.environ, so we
    # actually do need to mutate the process-global value rather than
    # just building a local dict.  monkeypatch.setenv restores the
    # previous value at test teardown, so this is pollution-safe.
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{fake_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    # Pre-install the default claude stub so factory instances always see a
    # valid version, regardless of what's on PATH (the real binary may be
    # version-mismatched on CI runners).  Skip when the test overrides via
    # @stub_dependency("claude", ...) — apply_stubs_from_request installs its
    # own stub further down, and we must not clobber it.
    if not has_stub_dependency_marker_for(request, "claude"):
        install_default_claude_stub(fake_bin_dir)

    environment = get_testing_environment(
        database_url=database_url,
        sculptor_folder=sculptor_folder,
        tmp_path=tmp_path,
        hide_keys=True,
    )

    # Apply @stub_dependency markers to the environment
    apply_stubs_from_request(request, environment, tmp_path)

    factory = create_sculptor_instance_factory(
        environment=environment,
        port=backend_port,
        database_url=database_url,
        default_timeout_ms=default_timeout_ms,
        request=request,
        sculptor_folder=sculptor_folder,
        base_repo=base_repo,
        fake_bin_dir=fake_bin_dir,
    )

    yield factory


CustomFolderPopulator = Callable[[Path], None]
custom_sculptor_folder_populator = pytest.mark.custom_sculptor_folder


def _make_test_user_config(claude_path: str = "claude") -> UserConfig:
    """Create a UserConfig with test defaults."""
    return UserConfig()


def _default_sculptor_folder_populator(folder_path: Path, claude_path: str = "claude") -> None:
    internal_dir = folder_path / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    config_path = internal_dir / "config.toml"
    config = _make_test_user_config(claude_path=claude_path)
    save_config(config, config_path)


def _extract_marker_arg(request: pytest.FixtureRequest, marker: pytest.MarkDecorator) -> Callable | None:
    marker = request.node.get_closest_marker(marker.name)
    return marker.args[0] if marker else None


@pytest.fixture
def test_repo_factory_(
    tmp_path: Path, test_root_concurrency_group: ConcurrencyGroup
) -> Generator[TestRepoFactory, None, None]:
    """
    Factory fixture for creating test repositories on demand.

    This fixture provides a function that tests can call multiple times
    to create separate test repositories with different configurations.
    Each repository is created in a temporary directory that's automatically
    cleaned up after the test.

    Usage:
        def test_something(test_repo_factory):
            repo1 = test_repo_factory("project1", "main")
            repo2 = test_repo_factory("project2", "develop")
    """
    factory = TestRepoFactory(base_path=tmp_path, concurrency_group=test_root_concurrency_group)
    yield factory


_DEFAULT_TIMEOUT_MS: Final[int] = 30_000


class AlreadyRunningServiceCollection(CompleteServiceCollection):
    """Wraps an existing already-started CompleteServiceCollection to prevent multiple run_all calls.

    This makes re-using the same service collection in the same process through the FastAPI mock client possible,
    as otherwise the app's lifespan middleware would restart it repeatedly & fail due to our db lock (among other things).

    For single-process integration tests. For more e2e tests use sculptor_factory_ instead.
    """

    @classmethod
    def build(cls, from_collection: CompleteServiceCollection) -> "AlreadyRunningServiceCollection":
        assert from_collection.data_model_service.concurrency_group._state == ConcurrencyGroupState.ACTIVE
        return cls(
            settings=from_collection.settings,
            data_model_service=from_collection.data_model_service,
            workspace_service=from_collection.workspace_service,
            git_repo_service=from_collection.git_repo_service,
            task_service=from_collection.task_service,
            project_service=from_collection.project_service,
            pr_polling_service=from_collection.pr_polling_service,
            ci_babysitter_service=from_collection.ci_babysitter_service,
        )

    @contextmanager
    def run_all(self) -> Generator[None, None, None]:
        yield
