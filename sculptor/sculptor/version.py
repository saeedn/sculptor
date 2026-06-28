"""Version is the exposed interface for making available the version of this
project to internal files.
"""

import subprocess
import tomllib
from functools import cache
from importlib import resources

from packaging.version import Version


def dev_git_sha(is_short: bool = True) -> str:
    """Return the Git SHA that this version came from.

    Can only be run in dev mode!
    """
    # We want to run this on the local machine, at build time.
    # Note: do not migrate to using `run_blocking` as it will introduce a cyclic dependency
    #       this wouldn't even be run during product runtime!

    cmd = ["git", "rev-parse"]
    if is_short:
        cmd.append("--short")
    cmd.append("HEAD")

    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


@cache
def pyproject_version() -> str:
    """Return the Sculptor version from pyproject.toml.

    Only call this function when running Sculptor code from source, i.e. not in the packaged program.
    """
    pyproject = resources.files("sculptor").joinpath("../pyproject.toml")

    with resources.as_file(pyproject) as path, path.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def is_devrelease(version_str: str) -> bool:
    """Helper function that hides the string"""
    return Version(version_str).is_devrelease


def pep_440_to_semver(version: str) -> str:
    """Convert a version string to a semver-compatible version string, for use by Electron.

    This will convert the rc tag to a pre-release tag. This will fail for post because semver does not properly support it.
    """
    v = Version(version)
    major, minor, patch, pre, post = v.major, v.minor, v.micro, v.pre, v.post

    if post is not None:
        raise ValueError("Post releases cannot be converted to semver")
    if pre and v.dev is not None:
        raise ValueError("Versions with both pre-release and dev components cannot be converted to semver")

    pre_component = f"-{pre[0]}.{pre[1]}" if pre else ""
    dev_component = f"-dev.{v.dev}" if v.dev is not None else ""

    return f"{major}.{minor}.{patch}{pre_component}{dev_component}"


def _get_version_and_sha():
    try:
        return pyproject_version(), dev_git_sha(), None, None
    except FileNotFoundError:
        # Production mode: trust built _version.py
        from sculptor import _version  # type: ignore[reportMissingImports]

        return (
            _version.__version__,
            _version.__git_sha__,
            getattr(_version, "ci_job_id", None),
            getattr(_version, "ci_ref", None),
        )


__version__, __git_sha__, ci_job_id, ci_ref = _get_version_and_sha()
