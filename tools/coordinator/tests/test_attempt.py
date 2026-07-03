import json
import subprocess
import sys
from pathlib import Path

from coordinator.attempt import prepare_attempt
from coordinator.dag import Node

EXPECTED_HOOK_EVENTS = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd", "Notification", "PreToolUse"}


def make_node(node_id: str = "1.1") -> Node:
    return Node(node_id=node_id, kind="task", deps=frozenset())


def prepare(tmp_path: Path, seed_context: str | None = None, process_doc_path: Path | None = None):
    task_file = tmp_path / "01_01_task.md"
    task_file.write_text("# Task\n")
    return prepare_attempt(
        plan_dir=tmp_path,
        node=make_node(),
        attempt_index=0,
        task_file=task_file,
        process_doc_path=process_doc_path,
        seed_context=seed_context,
    )


def test_attempt_dir_contents(tmp_path: Path) -> None:
    prepared = prepare(tmp_path, seed_context="previous attempt failed lint")
    assert prepared.attempt_dir.is_dir()
    assert (prepared.attempt_dir / "hooks.json").is_file()
    assert (prepared.attempt_dir / "prompt.txt").is_file()
    assert (prepared.attempt_dir / "process.md").is_file()
    assert (prepared.attempt_dir / "append_signal.py").is_file()
    assert prepared.context_file is not None
    assert prepared.context_file.read_text() == "previous attempt failed lint"


def test_hooks_json_structure(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    settings = json.loads(prepared.hooks_file.read_text())
    assert settings["skipDangerousModePermissionPrompt"] is True
    assert set(settings["hooks"]) == EXPECTED_HOOK_EVENTS
    for event, entries in settings["hooks"].items():
        for entry in entries:
            for hook in entry["hooks"]:
                command = hook["command"]
                assert command.endswith("|| true")
                assert str(prepared.signals_path.resolve()) in command
                assert event in command
    pre_tool_use = settings["hooks"]["PreToolUse"][0]
    assert pre_tool_use["matcher"] == "AskUserQuestion"


def test_append_signal_helper_round_trip(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    helper = prepared.attempt_dir / "append_signal.py"
    payload = {"session_id": "sess-1", "transcript_path": "/t.jsonl"}
    result = subprocess.run(
        [sys.executable, str(helper), "Stop", str(prepared.signals_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    line = json.loads(prepared.signals_path.read_text())
    assert line["event"] == "Stop"
    assert line["payload"] == payload
    assert isinstance(line["ts"], float)


def test_append_signal_helper_tolerates_garbage_stdin(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    helper = prepared.attempt_dir / "append_signal.py"
    for stdin in ("", "not json {{{"):
        result = subprocess.run(
            [sys.executable, str(helper), "SessionStart", str(prepared.signals_path)],
            input=stdin,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
    lines = [json.loads(line) for line in prepared.signals_path.read_text().splitlines()]
    assert [line["payload"] for line in lines] == [None, None]


def test_prompt_contains_absolute_paths(tmp_path: Path) -> None:
    prepared = prepare(tmp_path, seed_context="context")
    task_file = (tmp_path / "01_01_task.md").resolve()
    assert str(task_file) in prepared.prompt
    assert str(prepared.process_doc.resolve()) in prepared.prompt
    assert prepared.context_file is not None
    assert str(prepared.context_file.resolve()) in prepared.prompt
    assert (prepared.attempt_dir / "prompt.txt").read_text().strip() == prepared.prompt


def test_prompt_without_context_says_none(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    assert prepared.context_file is None
    assert "retry context, if any, is at none" in prepared.prompt
    assert not (prepared.attempt_dir / "context.md").exists()


def test_process_doc_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom_process.md"
    custom.write_text("# Custom process\n")
    prepared = prepare(tmp_path, process_doc_path=custom)
    assert prepared.process_doc.read_text() == "# Custom process\n"


def test_default_process_doc_has_no_user_questions(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    text = prepared.process_doc.read_text()
    assert "SUCCESS" in text
    assert "BLOCKED" in text
    assert "Co-authored-by: Sculptor" in text
    assert "no pre-existing failures" in text.lower()
    assert "question tool" not in text.lower()
    assert "askuserquestion" not in text.lower()


def test_attempts_get_isolated_signals_files(tmp_path: Path) -> None:
    task_file = tmp_path / "01_01_task.md"
    task_file.write_text("# Task\n")
    first = prepare_attempt(tmp_path, make_node(), 0, task_file, None, None)
    second = prepare_attempt(tmp_path, make_node(), 1, task_file, None, None)
    assert first.signals_path != second.signals_path
    assert first.attempt_dir != second.attempt_dir
