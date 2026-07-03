import json
from pathlib import Path

import pytest

from coordinator.gates import head_commit
from coordinator.review import VerdictError
from coordinator.review import build_review_diff
from coordinator.review import format_findings
from coordinator.review import parse_verdict
from coordinator.review import prepare_review_attempt
from tests.fakes import make_git_repo
from tests.fakes import repo_commit_all


def write_verdict(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps(data))
    return path


def test_parse_verdict_pass(tmp_path: Path) -> None:
    verdict = parse_verdict(write_verdict(tmp_path, {"pass": True, "findings": []}))
    assert verdict.passed
    assert not verdict.blocks()


def test_parse_verdict_fail(tmp_path: Path) -> None:
    verdict = parse_verdict(write_verdict(tmp_path, {"pass": False, "findings": []}))
    assert verdict.blocks()


def test_warnings_alone_do_not_block(tmp_path: Path) -> None:
    verdict = parse_verdict(
        write_verdict(
            tmp_path,
            {"pass": True, "findings": [{"task_id": None, "severity": "warning", "summary": "meh"}]},
        )
    )
    assert not verdict.blocks()


def test_any_blocker_blocks_even_when_pass_true(tmp_path: Path) -> None:
    verdict = parse_verdict(
        write_verdict(
            tmp_path,
            {"pass": True, "findings": [{"task_id": "1.1", "severity": "blocker", "summary": "bad"}]},
        )
    )
    assert verdict.blocks()


def test_missing_verdict_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(VerdictError) as exc_info:
        parse_verdict(tmp_path / "verdict.json")
    assert "no verdict file" in str(exc_info.value)


def test_invalid_json_verdict_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text("I think it looks fine!")
    with pytest.raises(VerdictError):
        parse_verdict(path)


def test_wrong_schema_verdict_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(VerdictError):
        parse_verdict(write_verdict(tmp_path, {"verdict": "ship it"}))


def test_format_findings() -> None:
    verdict = parse_verdict_from_dict(
        {
            "pass": False,
            "findings": [
                {"task_id": "1.1", "severity": "blocker", "summary": "broken", "detail": "here is why"},
                {"task_id": None, "severity": "warning", "summary": "style"},
            ],
        }
    )
    text = format_findings(verdict)
    assert "[blocker] (task 1.1) broken: here is why" in text
    assert "[warning] style" in text


def parse_verdict_from_dict(data: dict):
    from coordinator.review import Verdict

    return Verdict.model_validate(data)


def test_build_review_diff_per_task_scope(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (repo / "one.txt").write_text("one\n")
    repo_commit_all(repo, "first")
    first = head_commit(repo)
    (repo / "two.txt").write_text("two\n")
    repo_commit_all(repo, "second")
    second = head_commit(repo)
    # Scope = only the second commit.
    diff = build_review_diff(repo, [second])
    assert "two.txt" in diff
    assert "one.txt" not in diff
    # Scope = both commits (a phase's combined diff).
    combined = build_review_diff(repo, [first, second])
    assert "one.txt" in combined
    assert "two.txt" in combined


def test_build_review_diff_empty_scope(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    assert "no commits" in build_review_diff(repo, [])


def test_build_review_diff_truncation(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (repo / "big.txt").write_text("line\n" * 5000)
    repo_commit_all(repo, "big")
    diff = build_review_diff(repo, [head_commit(repo)], max_bytes=1024)
    assert "truncated" in diff
    assert len(diff.encode()) < 2048


def test_prepare_review_attempt_layout(tmp_path: Path) -> None:
    task_file = tmp_path / "01_01_task.md"
    task_file.write_text("# Task\n")
    review = prepare_review_attempt(tmp_path, "1.2.review", 0, [task_file], "the diff\n")
    directory = review.prepared.attempt_dir
    assert directory == tmp_path / "_state" / "attempts" / "1.2.review" / "0"
    assert review.diff_path.read_text() == "the diff\n"
    assert not review.verdict_path.exists()
    assert (directory / "hooks.json").is_file()
    process_text = review.prepared.process_doc.read_text()
    assert "read-only" in process_text.lower()
    assert '"pass"' in process_text
    prompt = review.prepared.prompt
    assert str(task_file.resolve()) in prompt
    assert str(review.diff_path.resolve()) in prompt
    assert str(review.verdict_path.resolve()) in prompt
    # A second attempt gets a fresh directory.
    second = prepare_review_attempt(tmp_path, "1.2.review", 1, [task_file], "diff 2\n")
    assert second.prepared.attempt_dir != directory
