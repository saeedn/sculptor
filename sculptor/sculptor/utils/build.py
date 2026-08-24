import os
import sys
from functools import cache
from pathlib import Path
from typing import Final
from typing import Literal
from typing import TYPE_CHECKING

from loguru import logger
from packaging.version import Version

import sculptor
from sculptor import version

if TYPE_CHECKING:
    from sculptor.primitives.ids import ProjectID
    from sculptor.primitives.ids import TaskID
    from sculptor.primitives.ids import WorkspaceID

SCULPTOR_FOLDER_OVERRIDE_ENV_FLAG: Final = "SCULPTOR_FOLDER"
SCULPTOR_WORKSPACES_FOLDER_OVERRIDE_ENV_FLAG: Final = "SCULPTOR_WORKSPACES_FOLDER"


# The CLIs Sculptor builds alongside itself and puts on the PATH of the shells it
# spawns: a PyInstaller bundle each in the packaged app, a venv entry point each
# when running from source.
AgentCLIName = Literal["sculpt", "coordinator"]
AGENT_CLI_NAMES: Final[tuple[AgentCLIName, ...]] = ("sculpt", "coordinator")


def get_agent_cli_bin_dir(
    cli_name: AgentCLIName, executable_parent: Path | None = None, *, packaged: bool | None = None
) -> Path:
    """Return the directory containing the bundled ``cli_name`` binary.

    Args:
        cli_name: The CLI to locate.
        executable_parent: The directory containing the running executable.
            Defaults to ``Path(sys.executable).parent``.
        packaged: Whether the app is running from a PyInstaller bundle.
            Defaults to ``is_packaged()``.

    In dev mode the server runs inside a uv-managed venv that has an editable
    install of each CLI's package; the binary lives in the venv's bin
    directory. We don't return the venv bin directly though — user shell init
    (conda, custom rc snippets) often demotes anything that looks like a venv
    bin to the back of PATH for Python isolation, which would let a packaged
    Sculptor's copy win over the dev one. Instead, we materialize a dedicated
    ``<cli_name>-bin/`` directory under the internal folder containing only a
    symlink to the venv's binary, so PATH lookup is robust to that demotion.
    If the venv's binary is missing we deliberately do NOT create the symlink
    (a dangling link would be silently skipped by PATH, letting the stale
    packaged binary win); instead we warn loudly so the fallback is
    diagnosable.

    In packaged mode each CLI is a PyInstaller ``--onedir`` bundle placed as an
    Electron extraResource alongside ``sculptor_backend``, i.e.
    ``<resources>/<cli_name>/``.
    """
    if executable_parent is None:
        executable_parent = Path(sys.executable).parent
    if packaged is None:
        packaged = is_packaged()
    if packaged:
        return executable_parent.parent / cli_name
    cli_bin_dir = get_internal_folder() / f"{cli_name}-bin"
    cli_bin_dir.mkdir(parents=True, exist_ok=True)
    cli_link = cli_bin_dir / cli_name
    cli_target = executable_parent / cli_name
    if not cli_target.exists():
        # The source CLI is not installed in the dev venv (e.g. uv only synced the
        # sculptor project so the workspace member was never installed, or a later
        # `uv sync` pruned the editable install). Symlinking to a missing target would leave
        # a dangling link that PATH lookup silently skips, falling through to the stale
        # packaged binary with no signal (SCU-1360). Remove any stale link and warn loudly
        # instead of failing silently.
        if cli_link.is_symlink() or cli_link.exists():
            cli_link.unlink()
        logger.warning(
            "Source {} not found at {}; dev agents will fall back to the stale packaged {} CLI.",
            cli_name,
            cli_target,
            cli_name,
        )
        return cli_bin_dir
    try:
        current_target = os.readlink(cli_link) if cli_link.is_symlink() else None
    except OSError:
        current_target = None
    if current_target != str(cli_target):
        if cli_link.is_symlink() or cli_link.exists():
            cli_link.unlink()
        cli_link.symlink_to(cli_target)
    return cli_bin_dir


def build_agent_cli_path(executable_parent: Path | None = None, *, packaged: bool | None = None) -> str:
    """The ``PATH`` prefix that makes Sculptor's bundled CLIs available to a shell.

    Every surface that spawns a shell for the user or an agent prepends this, so
    bare ``sculpt`` and ``coordinator`` invocations resolve to the binaries that
    ship with (or are built alongside) this Sculptor, not to whatever else the
    user happens to have installed.
    """
    return os.pathsep.join(
        str(get_agent_cli_bin_dir(cli_name, executable_parent, packaged=packaged)) for cli_name in AGENT_CLI_NAMES
    )


def build_sculpt_backend_env(
    *,
    backend_port: int,
    workspace_id: "WorkspaceID",
    project_id: "ProjectID",
    agent_id: "TaskID | None" = None,
) -> dict[str, str]:
    """The ``SCULPT_*`` identity vars a shell needs so a bare ``sculpt``
    invocation reaches this backend and resolves its workspace/project (and,
    when given, agent) without flags.

    Single source for the surfaces that expose these — the terminal-agent task
    handler and the workspace terminal manager — so the set cannot drift
    between them. ``PATH`` is intentionally NOT included: it is a separate
    concern with its own single source, ``build_agent_cli_path()``. Workspace
    terminals are not agent-scoped, so they omit ``agent_id``.
    """
    env = {
        "SCULPT_API_PORT": str(backend_port),
        "SCULPT_WORKSPACE_ID": str(workspace_id),
        "SCULPT_PROJECT_ID": str(project_id),
    }
    if agent_id is not None:
        env["SCULPT_AGENT_ID"] = str(agent_id)
    return env


def is_dev_build() -> bool:
    """Return True when running a dev release rather than a production build."""
    return Version(version.__version__).is_devrelease


def _get_repo_root() -> Path | None:
    """Find the repository root by looking for a .git directory.

    Returns None if we can't find a repository root (e.g., in a packaged build).
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def is_packaged() -> bool:
    """Return True when running inside a PyInstaller bundle (analogous to Electron's app.isPackaged)."""
    return hasattr(sys, "frozen")


def _find_macos_bundle(exe_path: Path) -> Path | None:
    """Walk up from the executable to find a macOS .app bundle root.

    Validates the bundle by checking for Contents/MacOS or Contents/Resources.
    """
    for parent in [exe_path, *exe_path.parents]:
        if parent.suffix == ".app" and (parent / "Contents" / "MacOS").is_dir():
            return parent
    return None


def _find_appimage_path() -> Path | None:
    """Return the AppImage file path when running inside a Linux AppImage."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return Path(appimage)
    return None


def get_install_path() -> Path:
    """Return the path to the sculptor installation.

    For macOS .app bundles, returns the bundle root (e.g. /Applications/Sculptor.app).
    For Linux AppImages, returns the AppImage file path.
    Otherwise returns the executable's parent directory or the sculptor package path.
    """
    if is_packaged():
        exe_path = Path(sys.executable).resolve()
        if sys.platform == "darwin":
            macos_bundle = _find_macos_bundle(exe_path)
            if macos_bundle is not None:
                return macos_bundle
        elif sys.platform == "linux":
            appimage_path = _find_appimage_path()
            if appimage_path is not None:
                return appimage_path
        return exe_path.parent
    return Path(sculptor.__file__).resolve().parent


@cache
def get_sculptor_folder() -> Path:
    """Return the root Sculptor data folder for the current build and environment."""
    # NOTE: The Electron shell of the packaged version of sculptor sometimes reads from this folder. Please keep any
    # changes you make here consistent with sculptor/frontend/src/electron/logger.ts getSculptorFolder
    path_from_env = os.environ.get(SCULPTOR_FOLDER_OVERRIDE_ENV_FLAG)
    if path_from_env:
        path = Path(path_from_env)
        logger.info("Sculptor folder: {} (from {} env var)", path, SCULPTOR_FOLDER_OVERRIDE_ENV_FLAG)
    elif not is_packaged():
        # Running from source: use the repo root so each checkout has its own data
        repo_root = _get_repo_root()
        if repo_root is not None:
            path = repo_root / ".dev_sculptor"
        else:
            path = Path.home() / ".dev-sculptor"
        logger.info("Sculptor folder: {} (running from source)", path)
    elif is_dev_build():
        # Packaged dev build (DMG/AppImage with .dev version)
        path = Path.home() / ".dev-sculptor"
        logger.info("Sculptor folder: {} (packaged dev build)", path)
    else:
        path = Path.home() / ".sculptor"
        logger.info("Sculptor folder: {} (production build)", path)
    return path


def get_internal_folder() -> Path:
    """Return the internal data folder used for Sculptor-managed state."""
    return get_sculptor_folder() / "internal"


def get_workspaces_folder() -> Path:
    """Return the folder under which agent workspaces are created."""
    # Workspace paths are persisted in the DB, so this override should stay stable across
    # launches of the same instance — pointing it elsewhere will leave existing workspace
    # rows referencing the previous location. Primary use case: nested dev Sculptor
    # instances, where redirecting workspaces to a flat path avoids deeply nested
    # ``.dev_sculptor/workspaces/<id>/code`` chains that exceed Claude's project-dir
    # path-length limit.
    path_from_env = os.environ.get(SCULPTOR_WORKSPACES_FOLDER_OVERRIDE_ENV_FLAG)
    if path_from_env:
        return Path(path_from_env)
    return get_sculptor_folder() / "workspaces"
