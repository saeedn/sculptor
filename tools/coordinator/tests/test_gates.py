from pathlib import Path

from coordinator.dag import Node
from coordinator.gates import commits_since
from coordinator.gates import head_commit
from coordinator.gates import is_tree_clean
from coordinator.gates import run_mechanical_gate
from tests.fakes import make_git_repo
from tests.fakes import repo_commit_all


def make_node(node_id: str = "1.1") -> Node:
    return Node(node_id=node_id, kind="task", deps=frozenset())


def run_gate(repo: Path, tmp_path: Path, verification: list[str], *, expect_commit: bool, base_commit: str):
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir(exist_ok=True)
    return run_mechanical_gate(
        repo, make_node(), attempt_dir, verification, expect_commit=expect_commit, base_commit=base_commit
    )


def test_gate_passes_with_commit(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    (repo / "work.txt").write_text("done\n")
    repo_commit_all(repo, "task work")
    outcome = run_gate(repo, tmp_path, ["true"], expect_commit=True, base_commit=base)
    assert outcome.passed
    assert commits_since(repo, base) == [head_commit(repo)]


def test_gate_fails_on_failing_command_with_log_tail(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    outcome = run_gate(repo, tmp_path, ["echo hello-from-log && false"], expect_commit=False, base_commit=base)
    assert not outcome.passed
    assert outcome.findings is not None
    assert "echo hello-from-log && false" in outcome.findings
    assert "hello-from-log" in outcome.findings
    assert (tmp_path / "attempt" / "gate_mechanical_0.log").read_text() == "hello-from-log\n"


def test_gate_runs_commands_in_order_and_stops_at_first_failure(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    outcome = run_gate(repo, tmp_path, ["true", "false", "echo never"], expect_commit=False, base_commit=base)
    assert not outcome.passed
    assert (tmp_path / "attempt" / "gate_mechanical_1.log").exists()
    assert not (tmp_path / "attempt" / "gate_mechanical_2.log").exists()


def test_gate_fails_on_missing_commit(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    outcome = run_gate(repo, tmp_path, ["true"], expect_commit=True, base_commit=base)
    assert not outcome.passed
    assert outcome.findings is not None
    assert "produced no commit" in outcome.findings


def test_gate_fails_on_unexpected_commit_for_no_change_task(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    (repo / "surprise.txt").write_text("oops\n")
    repo_commit_all(repo, "unexpected")
    outcome = run_gate(repo, tmp_path, ["true"], expect_commit=False, base_commit=base)
    assert not outcome.passed
    assert outcome.findings is not None
    assert "no-change but committed" in outcome.findings


def test_gate_fails_on_dirty_tree_after_task(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    (repo / "work.txt").write_text("done\n")
    repo_commit_all(repo, "task work")
    (repo / "leftover.txt").write_text("uncommitted\n")
    outcome = run_gate(repo, tmp_path, ["true"], expect_commit=True, base_commit=base)
    assert not outcome.passed
    assert outcome.findings is not None
    assert "dirty" in outcome.findings
    assert "leftover.txt" in outcome.findings


def test_is_tree_clean(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    assert is_tree_clean(repo)
    (repo / "new.txt").write_text("x\n")
    assert not is_tree_clean(repo)


def test_commits_since_ordered_oldest_first(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    base = head_commit(repo)
    (repo / "a.txt").write_text("a\n")
    repo_commit_all(repo, "first")
    first = head_commit(repo)
    (repo / "b.txt").write_text("b\n")
    repo_commit_all(repo, "second")
    second = head_commit(repo)
    assert commits_since(repo, base) == [first, second]
