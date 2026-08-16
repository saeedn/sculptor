"""Opt-in smoke test against real Claude — excluded from CI.

PTY/hooks/billing behavior can drift with Claude Code versions; this
test proves the real mechanism end-to-end. Run it manually with:

    COORDINATOR_REAL_SMOKE=1 uv run --project tools/coordinator \\
        pytest -m real_claude tools/coordinator/tests/ -v

Requires the `claude` CLI on PATH and a logged-in subscription.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from coordinator.journal import SignalObserved
from coordinator.journal import load_snapshot
from coordinator.journal import replay
from coordinator.run import execute_plan
from coordinator.statedir import journal_path
from tests.fakes import make_git_repo

PLAN_YAML = """\
version: 1
defaults:
  worker: claude-sonnet
  verification:
    - "true"
phases:
  - id: 1
    name: Smoke
    review: none
    tasks:
      - id: "1.1"
        file: 01_01_create.md
      - id: "1.2"
        file: 01_02_append.md
        deps: ["1.1"]
"""

TASK_1 = """\
# Task 1.1: Create hello.txt

Create a file named `hello.txt` in the repository root containing
exactly the text `hello world` (one line). Commit it with the commit
message `task 1`.
"""

TASK_2 = """\
# Task 1.2: Append to hello.txt

Append the line `second line` to the existing `hello.txt`. Commit the
change with the commit message `task 2`.
"""


@pytest.mark.real_claude
def test_real_claude_two_task_plan(tmp_path: Path) -> None:
    if os.environ.get("COORDINATOR_REAL_SMOKE") != "1":
        pytest.skip("set COORDINATOR_REAL_SMOKE=1 to run the real-Claude smoke test")
    if shutil.which("claude") is None:
        pytest.skip("the `claude` CLI is not on PATH")

    repo = make_git_repo(tmp_path / "repo")
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan.yaml").write_text(PLAN_YAML)
    (plan_dir / "01_01_create.md").write_text(TASK_1)
    (plan_dir / "01_02_append.md").write_text(TASK_2)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add plan"], check=True)

    status = execute_plan(
        plan_dir,
        repo_root=repo,
        timeout_seconds=600.0,
        poll_interval=0.5,
        kill_grace_seconds=10.0,
        progress=print,
    )
    assert status == "completed"

    hello = (repo / "hello.txt").read_text()
    assert "hello world" in hello
    assert "second line" in hello
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%s"], capture_output=True, text=True, check=True
    ).stdout
    assert "task 1" in log
    assert "task 2" in log

    snapshot = load_snapshot(plan_dir)
    assert snapshot.nodes["1.1"].state == "passed"
    assert snapshot.nodes["1.2"].state == "passed"
    # Real hook signals were observed, including session ids.
    stop_signals = [e for e in replay(journal_path(plan_dir)) if isinstance(e, SignalObserved) and e.event == "Stop"]
    assert len(stop_signals) >= 2
    assert all(a.session_id for n in snapshot.nodes.values() for a in n.attempts)
