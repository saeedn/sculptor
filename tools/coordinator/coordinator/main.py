import sys
from pathlib import Path
from typing import get_args

import typer

from coordinator.dag import build_graph
from coordinator.journal import ControlIntent
from coordinator.journal import ControlIntentName
from coordinator.journal import Journal
from coordinator.journal import load_snapshot
from coordinator.manifest import ManifestError
from coordinator.manifest import load_manifest
from coordinator.run import RunError
from coordinator.run import execute_plan
from coordinator.run import find_incomplete_plans
from coordinator.run import find_plan_by_run_id
from coordinator.statedir import ensure_state_dir
from coordinator.statedir import journal_path

_NODE_INTENTS = ("retry", "skip", "approve")

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


def _execute_plan_dir(plan_dir: Path, resume_run: bool, no_tui: bool) -> None:
    if no_tui or not sys.stdout.isatty():
        try:
            status = execute_plan(plan_dir, resume=resume_run, progress=typer.echo)
        except (ManifestError, RunError) as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
        if status != "completed":
            raise typer.Exit(1)
        return
    # Lazy import: the plain path must never pay Textual's startup cost.
    from coordinator.tui.app import CoordinatorApp

    try:
        dashboard = CoordinatorApp(plan_dir, resume=resume_run)
    except ManifestError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    dashboard.run()
    if dashboard.run_error is not None:
        typer.echo(f"Error: {dashboard.run_error}", err=True)
        raise typer.Exit(1)
    if dashboard.final_status != "completed":
        raise typer.Exit(1)


def _pick_incomplete_plan() -> Path:
    plans = find_incomplete_plans(Path.cwd())
    if not plans:
        typer.echo(f"No plans with incomplete runs found under {Path.cwd()}", err=True)
        raise typer.Exit(1)
    typer.echo("Plans with incomplete runs:")
    for index, plan in enumerate(plans, start=1):
        typer.echo(f"{index}. {plan.plan_dir} — {plan.completed}/{plan.total} passed (run {plan.run_id or '-'})")
    choice = typer.prompt("Resume which plan?", type=int)
    if not 1 <= choice <= len(plans):
        typer.echo(f"Error: choose a number between 1 and {len(plans)}", err=True)
        raise typer.Exit(1)
    return plans[choice - 1].plan_dir


@app.command()
def run(
    plan_dir: Path | None = typer.Argument(
        None,
        help="Path to the plan directory containing plan.yaml. Omit to pick from incomplete runs.",
    ),
    no_tui: bool = typer.Option(
        False,
        "--no-tui",
        help="Plain-text progress instead of the live dashboard (implied when stdout is not a tty).",
    ),
) -> None:
    """Execute a plan, showing a live dashboard (the default on a tty)."""
    if plan_dir is None:
        _execute_plan_dir(_pick_incomplete_plan(), resume_run=True, no_tui=no_tui)
        return
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    _execute_plan_dir(plan_dir, resume_run=False, no_tui=no_tui)


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="ID of the run to resume (see _state/run_id)."),
    no_tui: bool = typer.Option(
        False,
        "--no-tui",
        help="Plain-text progress instead of the live dashboard (implied when stdout is not a tty).",
    ),
) -> None:
    """Resume a previously interrupted run by its run id."""
    try:
        plan_dir = find_plan_by_run_id(Path.cwd(), run_id)
    except RunError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    _execute_plan_dir(plan_dir, resume_run=True, no_tui=no_tui)


@app.command()
def intent(
    plan_dir: Path = typer.Argument(..., help="Path to the plan directory containing plan.yaml."),
    intent_name: str = typer.Argument(..., metavar="INTENT", help="pause | resume | retry | skip | approve | abort"),
    node_id: str | None = typer.Argument(None, help="Node id (required for retry/skip/approve)."),
) -> None:
    """Append a control intent to the run's journal (works without the TUI).

    A running coordinator picks it up on its next loop iteration; a
    paused or killed run picks it up on its next start.
    """
    if not plan_dir.is_dir():
        typer.echo(f"Error: plan directory does not exist: {plan_dir}", err=True)
        raise typer.Exit(1)
    allowed = get_args(ControlIntentName)
    if intent_name not in allowed:
        typer.echo(f"Error: unknown intent {intent_name!r}; allowed: {', '.join(allowed)}", err=True)
        raise typer.Exit(1)
    if intent_name in _NODE_INTENTS and node_id is None:
        typer.echo(f"Error: intent {intent_name!r} requires a node id", err=True)
        raise typer.Exit(1)
    if node_id is not None:
        try:
            graph = build_graph(load_manifest(plan_dir))
        except ManifestError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
        if node_id not in graph.nodes:
            typer.echo(f"Error: unknown node {node_id!r}; known: {', '.join(graph.nodes)}", err=True)
            raise typer.Exit(1)
    ensure_state_dir(plan_dir)
    # pyrefly: ignore [bad-argument-type]  (intent_name is validated against the Literal above)
    Journal(journal_path(plan_dir)).append(ControlIntent(intent=intent_name, node_id=node_id))
    target = f" for node {node_id}" if node_id is not None else ""
    typer.echo(f"appended {intent_name} intent{target}")


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
