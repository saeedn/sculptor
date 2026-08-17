import subprocess
from pathlib import Path

from loguru import logger

# Run from the repo root so pyrefly's upward config search finds pyrefly.toml
# regardless of where pytest was invoked from.
_REPO_ROOT = Path(__file__).parents[2]


def test_pyrefly_type_checking() -> None:
    # --all-packages: pyrefly.toml checks tools/coordinator as well as sculptor,
    # and coordinator's imports (textual, the coordinator package) only resolve
    # when every workspace member is synced into the venv. Without it this passes
    # on a dev machine whose venv happens to have coordinator installed, and fails
    # on a cold CI runner.
    result = subprocess.run(
        ["uv", "run", "--all-packages", "pyrefly", "check"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )

    # stderr has progress/debugging info; stdout has the identified errors
    logger.debug("pyrefly stderr:\n{}", result.stderr)
    logger.debug("pyrefly stdout:\n{}", result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
