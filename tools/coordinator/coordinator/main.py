from pathlib import Path

import typer

app = typer.Typer(
    name="coordinator",
    help="Deterministic build coordinator that executes implementation plans with Claude Code workers.",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo("coordinator 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show the coordinator version.",
    ),
) -> None:
    """Deterministic build coordinator that executes implementation plans with Claude Code workers."""


@app.command()
def run(plan_dir: Path = typer.Argument(..., help="Path to the plan directory containing plan.yaml.")) -> None:
    """Execute a plan from the beginning."""
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    typer.echo("not yet implemented", err=True)
    raise typer.Exit(1)


@app.command()
def resume(run_id: str = typer.Argument(..., help="ID of the run to resume.")) -> None:
    """Resume a previously interrupted run."""
    typer.echo("not yet implemented", err=True)
    raise typer.Exit(1)


@app.command()
def status(plan_dir: Path = typer.Argument(..., help="Path to the plan directory containing plan.yaml.")) -> None:
    """Show the execution status of a plan."""
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    typer.echo("not yet implemented", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
