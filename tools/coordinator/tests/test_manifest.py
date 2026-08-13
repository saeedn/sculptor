from pathlib import Path

import pytest

from coordinator.manifest import ManifestError
from coordinator.manifest import load_manifest

EXAMPLE_MANIFEST = """\
version: 1
defaults:
  worker: claude-print
  escalation_worker: claude-print-opus
  attempts: 2
  verification:
    - just format
    - just check
    - just test-unit
phases:
  - id: 1
    name: Core executor
    review: agentic
    tasks:
      - id: "1.1"
        file: 01_01_scaffold.md
      - id: "1.2"
        file: 01_02_manifest_parser.md
        deps: ["1.1"]
        worker: claude-opus
        gates: [mechanical, agentic]
        attempts: 3
        no_change: false
"""


def write_plan(tmp_path: Path, manifest_text: str, task_files: list[str]) -> Path:
    (tmp_path / "plan.yaml").write_text(manifest_text)
    for name in task_files:
        (tmp_path / name).touch()
    return tmp_path


def test_load_example_manifest(tmp_path: Path) -> None:
    plan_dir = write_plan(tmp_path, EXAMPLE_MANIFEST, ["01_01_scaffold.md", "01_02_manifest_parser.md"])
    manifest = load_manifest(plan_dir)
    assert manifest.version == 1
    assert manifest.defaults.worker == "claude-print"
    assert manifest.defaults.verification == ["just format", "just check", "just test-unit"]
    assert len(manifest.phases) == 1
    task = manifest.phases[0].tasks[1]
    assert task.id == "1.2"
    assert task.deps == ["1.1"]
    assert task.gates == ["mechanical", "agentic"]
    assert task.attempts == 3


def test_unquoted_task_ids_are_coerced_to_str(tmp_path: Path) -> None:
    manifest_text = """\
version: 1
defaults:
  worker: w
  verification: []
phases:
  - id: 1
    name: P
    tasks:
      - id: 1.1
        file: a.md
      - id: 2
        file: b.md
        deps: [1.1]
"""
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md", "b.md"])
    manifest = load_manifest(plan_dir)
    assert manifest.phases[0].tasks[0].id == "1.1"
    assert manifest.phases[0].tasks[1].id == "2"
    assert manifest.phases[0].tasks[1].deps == ["1.1"]


def test_reserved_kind_parses(tmp_path: Path) -> None:
    manifest_text = """\
version: 1
defaults:
  worker: w
  verification: []
phases:
  - id: 1
    name: P
    tasks:
      - id: "1.1"
        file: a.md
        kind: review
"""
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    manifest = load_manifest(plan_dir)
    assert manifest.phases[0].tasks[0].kind == "review"


def minimal_manifest(task_lines: str, defaults_attempts: str = "", version: str = "1", review: str = "agentic") -> str:
    return f"""\
version: {version}
defaults:
  worker: w
  verification: []
{defaults_attempts}phases:
  - id: 1
    name: P
    review: {review}
    tasks:
{task_lines}
"""


def load_expecting_error(plan_dir: Path) -> ManifestError:
    with pytest.raises(ManifestError) as exc_info:
        load_manifest(plan_dir)
    return exc_info.value


def test_missing_manifest_file(tmp_path: Path) -> None:
    error = load_expecting_error(tmp_path)
    assert "manifest not found" in str(error)


def test_unknown_dep(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n        deps: ["9.9"]')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "'9.9'" in str(error)


def test_duplicate_task_id(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n      - id: "1.1"\n        file: b.md')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md", "b.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1: duplicate task id" in str(error)


def test_missing_task_file(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: missing.md')
    plan_dir = write_plan(tmp_path, manifest_text, [])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "does not exist" in str(error)


def test_absolute_task_file_path(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: /etc/passwd')
    plan_dir = write_plan(tmp_path, manifest_text, [])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "absolute" in str(error)


def test_escaping_task_file_path(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (tmp_path / "outside.md").touch()
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: ../outside.md')
    write_plan(plan_dir, manifest_text, [])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "escapes" in str(error)


def test_bad_gate_name(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n        gates: [mechanical, bogus]')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "'bogus'" in str(error)


def test_bad_phase_review(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md', review="sometimes")
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "phase 1" in str(error)
    assert "'sometimes'" in str(error)


def test_bad_version(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md', version="2")
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "version: must be 1" in str(error)


def test_bad_kind(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n        kind: bogus')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1" in str(error)
    assert "'bogus'" in str(error)


def test_task_attempts_below_one(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n        attempts: 0')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1: attempts must be >= 1" in str(error)


def test_defaults_attempts_below_one(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md', defaults_attempts="  attempts: 0\n")
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "defaults.attempts: must be >= 1" in str(error)


def test_task_attempt_timeout_below_one(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md\n        attempt_timeout_minutes: 0')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "task 1.1: attempt_timeout_minutes must be >= 1" in str(error)


def test_defaults_attempt_timeout_below_one(tmp_path: Path) -> None:
    manifest_text = minimal_manifest(
        '      - id: "1.1"\n        file: a.md', defaults_attempts="  attempt_timeout_minutes: 0\n"
    )
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    error = load_expecting_error(plan_dir)
    assert "defaults.attempt_timeout_minutes: must be >= 1" in str(error)


def test_attempt_timeout_defaults_to_unset(tmp_path: Path) -> None:
    manifest_text = minimal_manifest('      - id: "1.1"\n        file: a.md')
    plan_dir = write_plan(tmp_path, manifest_text, ["a.md"])
    manifest = load_manifest(plan_dir)
    assert manifest.defaults.attempt_timeout_minutes is None
    assert manifest.phases[0].tasks[0].attempt_timeout_minutes is None


def test_all_problems_collected(tmp_path: Path) -> None:
    manifest_text = minimal_manifest(
        '      - id: "1.1"\n        file: missing.md\n        kind: bogus\n        deps: ["9.9"]'
    )
    plan_dir = write_plan(tmp_path, manifest_text, [])
    error = load_expecting_error(plan_dir)
    assert len(error.problems) == 3


def _manifest_with_process_doc(process_doc: str) -> str:
    return EXAMPLE_MANIFEST.replace("  attempts: 2\n", f"  attempts: 2\n  process_doc: {process_doc}\n")


def test_process_doc_must_stay_inside_the_plan_folder(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    write_plan(
        plan_dir, _manifest_with_process_doc("../outside.md"), ["01_01_scaffold.md", "01_02_manifest_parser.md"]
    )
    (tmp_path / "outside.md").write_text("# outside\n")
    with pytest.raises(ManifestError, match="escapes the plan folder"):
        load_manifest(plan_dir)


def test_missing_process_doc_rejected(tmp_path: Path) -> None:
    plan_dir = write_plan(
        tmp_path, _manifest_with_process_doc("no_such_process.md"), ["01_01_scaffold.md", "01_02_manifest_parser.md"]
    )
    with pytest.raises(ManifestError, match="does not exist"):
        load_manifest(plan_dir)
