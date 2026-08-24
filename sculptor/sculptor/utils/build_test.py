import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sculptor.utils.build import AGENT_CLI_NAMES
from sculptor.utils.build import AgentCLIName
from sculptor.utils.build import build_agent_cli_path
from sculptor.utils.build import get_agent_cli_bin_dir


@pytest.mark.parametrize("cli_name", AGENT_CLI_NAMES)
def test_get_agent_cli_bin_dir_does_not_create_dangling_symlink_when_target_missing(
    tmp_path: Path, cli_name: AgentCLIName
) -> None:
    """In dev mode, if the source CLI target is missing, no symlink should be created.

    Regression test for SCU-1360: a dangling symlink in ``<cli_name>-bin/`` is silently
    skipped by PATH lookup, so the CLI falls through to the stale packaged binary
    with no signal. The directory must not contain a broken symlink.
    """
    internal = tmp_path / "internal"
    executable_parent = tmp_path / "venv-bin"
    executable_parent.mkdir()
    # NOTE: intentionally do NOT create executable_parent / cli_name — the target is missing,
    # exactly as in a dev venv where the source CLI was never installed.

    with patch("sculptor.utils.build.get_internal_folder", return_value=internal):
        result = get_agent_cli_bin_dir(cli_name, executable_parent=executable_parent, packaged=False)

    cli_link = result / cli_name
    assert not cli_link.is_symlink(), f"must not create a dangling symlink when the {cli_name} target is missing"


@pytest.mark.parametrize("cli_name", AGENT_CLI_NAMES)
def test_get_agent_cli_bin_dir_removes_stale_dangling_symlink_when_target_disappears(
    tmp_path: Path, cli_name: AgentCLIName
) -> None:
    """A previously-valid symlink whose target later disappears must be removed, not left dangling.

    Regression test for SCU-1360: ``uv sync`` can prune the editable install,
    leaving the materialized symlink pointing at a now-missing target. The next call must
    clean it up rather than leaving a broken PATH entry.
    """
    internal = tmp_path / "internal"
    executable_parent = tmp_path / "venv-bin"
    executable_parent.mkdir()

    cli_bin_dir = internal / f"{cli_name}-bin"
    cli_bin_dir.mkdir(parents=True)
    stale_link = cli_bin_dir / cli_name
    stale_link.symlink_to(executable_parent / cli_name)  # target does not exist
    assert stale_link.is_symlink() and not stale_link.exists()

    with patch("sculptor.utils.build.get_internal_folder", return_value=internal):
        result = get_agent_cli_bin_dir(cli_name, executable_parent=executable_parent, packaged=False)

    cli_link = result / cli_name
    assert not cli_link.is_symlink(), "must remove a stale dangling symlink when the target disappears"


@pytest.mark.parametrize("cli_name", AGENT_CLI_NAMES)
def test_get_agent_cli_bin_dir_warns_loudly_when_target_missing(tmp_path: Path, cli_name: AgentCLIName) -> None:
    """When the source CLI target is missing, a warning naming it must be emitted.

    Regression test for SCU-1360: the failure mode was silent. The fix must make it
    diagnosable by logging a loud warning instead of quietly falling back.

    The assertion goes through the module's ``logger`` rather than a sink, because
    the configured file sink blanks ``record["message"]`` as it writes, leaving any
    later-added sink with an empty message to match against.
    """
    internal = tmp_path / "internal"
    executable_parent = tmp_path / "venv-bin"
    executable_parent.mkdir()

    with patch("sculptor.utils.build.get_internal_folder", return_value=internal):
        with patch("sculptor.utils.build.logger") as mock_logger:
            get_agent_cli_bin_dir(cli_name, executable_parent=executable_parent, packaged=False)

    mock_logger.warning.assert_called_once()
    assert cli_name in str(mock_logger.warning.call_args), (
        f"the warning must name {cli_name} so the fallback is diagnosable"
    )


@pytest.mark.parametrize("cli_name", AGENT_CLI_NAMES)
def test_get_agent_cli_bin_dir_creates_symlink_when_target_present(tmp_path: Path, cli_name: AgentCLIName) -> None:
    """The happy path is unchanged: when the source CLI exists, link to it."""
    internal = tmp_path / "internal"
    executable_parent = tmp_path / "venv-bin"
    executable_parent.mkdir()
    target = executable_parent / cli_name
    target.write_text("#!/bin/sh\n")

    with patch("sculptor.utils.build.get_internal_folder", return_value=internal):
        result = get_agent_cli_bin_dir(cli_name, executable_parent=executable_parent, packaged=False)

    cli_link = result / cli_name
    assert cli_link.is_symlink()
    assert os.readlink(cli_link) == str(target)


@pytest.mark.parametrize("cli_name", AGENT_CLI_NAMES)
def test_get_agent_cli_bin_dir_when_packaged_is_a_resource_sibling_of_the_backend(
    tmp_path: Path, cli_name: AgentCLIName
) -> None:
    """Packaged, each CLI is its own extraResource dir next to the backend's."""
    backend_dir = tmp_path / "Resources" / "sculptor_backend"
    backend_dir.mkdir(parents=True)

    result = get_agent_cli_bin_dir(cli_name, executable_parent=backend_dir, packaged=True)

    assert result == tmp_path / "Resources" / cli_name


def test_build_agent_cli_path_covers_every_bundled_cli(tmp_path: Path) -> None:
    """The PATH prefix must expose each bundled CLI's directory, so a bare
    ``sculpt`` or ``coordinator`` in an agent shell resolves without an install."""
    executable_parent = tmp_path / "venv-bin"
    executable_parent.mkdir()
    for cli_name in AGENT_CLI_NAMES:
        (executable_parent / cli_name).write_text("#!/bin/sh\n")

    with patch("sculptor.utils.build.get_internal_folder", return_value=tmp_path / "internal"):
        path = build_agent_cli_path(executable_parent=executable_parent, packaged=False)

    entries = path.split(os.pathsep)
    assert len(entries) == len(AGENT_CLI_NAMES)
    for cli_name, entry in zip(AGENT_CLI_NAMES, entries, strict=True):
        assert (Path(entry) / cli_name).is_symlink()
