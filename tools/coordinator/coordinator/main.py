from pathlib import Path

import typer

from coordinator.journal import load_snapshot
from coordinator.manifest import ManifestError
from coordinator.run import RunError
from coordinator.run import execute_plan

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
def run(
    plan_dir: Path = typer.Argument(..., help="Path to the plan directory containing plan.yaml."),
    no_tui: bool = typer.Option(
        False,
        "--no-tui",
        help="Plain-text progress instead of the TUI. (The TUI is not implemented yet; output is always plain.)",
    ),
) -> None:
    """Execute a plan from the beginning."""
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    try:
        status = execute_plan(plan_dir, progress=typer.echo)
    except (ManifestError, RunError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    if status != "completed":
        raise typer.Exit(1)


@app.command()
def resume(run_id: str = typer.Argument(..., help="ID of the run to resume.")) -> None:
    """Resume a previously interrupted run."""
    typer.echo("not yet implemented", err=True)
    raise typer.Exit(1)


@app.command()
def status(
    plan_dir: Path = typer.Argument(..., help="Path to the plan directory containing plan.yaml."),
    as_json: bool = typer.Option(False, "--json", help="Output the full snapshot as JSON."),
) -> None:
    """Show the execution status of a plan."""
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    snapshot = load_snapshot(plan_dir)
    if as_json:
        typer.echo(snapshot.model_dump_json(indent=2))
        return
    typer.echo(f"run: {snapshot.run_id or '-'}  status: {snapshot.run_status}")
    if snapshot.pause_reason:
        typer.echo(f"paused: {snapshot.pause_reason} ({snapshot.resume_hint or 'no hint'})")
    for node in snapshot.nodes.values():
        gates = " ".join(
            f"{gate.gate}={'pass' if gate.passed else 'FAIL' if gate.passed is False else 'running'}"
            for gate in node.gates
        )
        typer.echo(
            f"{node.node_id:<24} {node.state:<18} attempts={len(node.attempts)} commits={len(node.commits)} {gates}"
        )


if __name__ == "__main__":
    app()
