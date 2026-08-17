"""The mechanical gate and git helpers.

The mechanical gate runs after EVERY task, non-negotiable: it re-runs
the manifest's verification commands (materialized from
``.sculptor/code.md`` at plan time), requires a new commit for the task
(unless ``no_change: true``), and requires a clean working tree
afterwards. "Turn ended" never means success — gates decide.

Verification commands are trusted content from the manifest the user
authored (the same trust level as a worker registration file); each is
run verbatim through the shell, with output streamed to a log file in
the attempt directory.
"""

import subprocess
from pathlib import Path

from coordinator.dag import Node
from coordinator.scheduler import GateOutcome

GATE_MECHANICAL = "mechanical"
GATE_AGENTIC = "agentic"
GATE_HUMAN = "human"
GATE_PHASE_REVIEW = "phase-review"

_FINDINGS_TAIL_LINES = 50
# Bounded so a wedged command (index.lock, a hung hook, a test suite
# waiting on input) fails the gate instead of wedging the whole run.
_GIT_TIMEOUT_SECONDS = 60.0
_VERIFICATION_TIMEOUT_SECONDS = 3600.0


class GitError(Exception):
    """A git helper failed; the message carries the command and stderr."""


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"git {' '.join(args)} failed (exit {e.returncode}): {e.stderr.strip()}") from e
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git {' '.join(args)} timed out after {_GIT_TIMEOUT_SECONDS:.0f}s") from e
    return result.stdout


def head_commit(cwd: Path) -> str:
    return _git(cwd, "rev-parse", "HEAD").strip()


def porcelain_status(cwd: Path) -> str:
    return _git(cwd, "status", "--porcelain")


def is_tree_clean(cwd: Path) -> bool:
    return porcelain_status(cwd) == ""


def restore_clean_tree(cwd: Path) -> None:
    """Discard all uncommitted changes, tracked and untracked."""
    _git(cwd, "checkout", "--", ".")
    _git(cwd, "clean", "-fd")


def commits_since(cwd: Path, base: str) -> list[str]:
    """Commit hashes after ``base`` up to HEAD, oldest first."""
    return _git(cwd, "rev-list", "--reverse", f"{base}..HEAD").split()


def _log_tail(log_path: Path) -> str:
    lines = log_path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-_FINDINGS_TAIL_LINES:])


def run_mechanical_gate(
    cwd: Path,
    node: Node,
    attempt_dir: Path,
    verification: list[str],
    *,
    expect_commit: bool,
    base_commit: str,
) -> GateOutcome:
    for index, command in enumerate(verification):
        log_path = attempt_dir / f"gate_mechanical_{index}.log"
        # Stream to the log file — verification commands can run for
        # minutes and produce a lot of output.
        with open(log_path, "wb") as log_file:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(cwd),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=_VERIFICATION_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                findings = (
                    f"verification command timed out after {_VERIFICATION_TIMEOUT_SECONDS:.0f}s: {command!r}\n"
                    f"log: {log_path}\n{_log_tail(log_path)}"
                )
                return GateOutcome(gate=GATE_MECHANICAL, passed=False, findings=findings)
        if result.returncode != 0:
            findings = (
                f"verification command failed: {command!r} (exit {result.returncode})\n"
                f"log: {log_path}\n{_log_tail(log_path)}"
            )
            return GateOutcome(gate=GATE_MECHANICAL, passed=False, findings=findings)

    head = head_commit(cwd)
    if expect_commit and head == base_commit:
        return GateOutcome(
            gate=GATE_MECHANICAL,
            passed=False,
            findings=f"task {node.node_id} produced no commit (HEAD still at {base_commit[:12]})",
        )
    if not expect_commit and head != base_commit:
        return GateOutcome(
            gate=GATE_MECHANICAL,
            passed=False,
            findings=f"task {node.node_id} is declared no-change but committed ({base_commit[:12]} -> {head[:12]})",
        )

    status = porcelain_status(cwd)
    if status:
        return GateOutcome(
            gate=GATE_MECHANICAL,
            passed=False,
            findings=f"working tree dirty after task {node.node_id}:\n{status}",
        )
    return GateOutcome(gate=GATE_MECHANICAL, passed=True)
