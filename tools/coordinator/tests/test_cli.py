from typer.testing import CliRunner

from coordinator.main import app

runner = CliRunner()


def test_version_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "coordinator" in result.output


def test_run_nonexistent_plan_dir_exits_nonzero() -> None:
    result = runner.invoke(app, ["run", "/nonexistent"])
    assert result.exit_code != 0


def test_status_nonexistent_plan_dir_exits_nonzero() -> None:
    result = runner.invoke(app, ["status", "/nonexistent"])
    assert result.exit_code != 0
