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
    assert (prepared.attempt_dir / "stop_guard.py").is_file()
    assert prepared.context_file is not None
    assert prepared.context_file.read_text() == "previous attempt failed lint"


def signal_commands(settings: dict, event: str) -> list[str]:
    return [hook["command"] for entry in settings["hooks"][event] for hook in entry["hooks"]]


def test_hooks_json_structure(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    settings = json.loads(prepared.hooks_file.read_text())
    assert settings["skipDangerousModePermissionPrompt"] is True
    assert set(settings["hooks"]) == EXPECTED_HOOK_EVENTS
    for event in EXPECTED_HOOK_EVENTS:
        # Every event records itself; Stop additionally runs the guard.
        recorder = signal_commands(settings, event)[0]
        assert recorder.endswith("|| true")
        assert str(prepared.signals_path.resolve()) in recorder
        assert event in recorder
    pre_tool_use = settings["hooks"]["PreToolUse"][0]
    assert pre_tool_use["matcher"] == "AskUserQuestion"


def test_stop_runs_the_guard_after_recording(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    settings = json.loads(prepared.hooks_file.read_text())
    commands = signal_commands(settings, "Stop")
    assert len(commands) == 2
    guard = commands[1]
    assert str((prepared.attempt_dir / "stop_guard.py").resolve()) in guard
    assert str((prepared.attempt_dir / "stop_blocks").resolve()) in guard
    # The guard's verdict travels on its own exit status and stdout.
    assert not guard.endswith("|| true")
    # Only Stop is guarded — nothing else can strand background work.
    assert all(len(signal_commands(settings, event)) == 1 for event in EXPECTED_HOOK_EVENTS - {"Stop"})


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


def run_guard(prepared, payload: dict | str, max_blocks: int | None = None):
    guard = prepared.attempt_dir / "stop_guard.py"
    blocks_path = prepared.attempt_dir / "stop_blocks"
    argv = [sys.executable, str(guard), str(blocks_path)]
    if max_blocks is not None:
        argv.append(str(max_blocks))
    return subprocess.run(
        argv,
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True,
        text=True,
    )


def stop_payload(*statuses: str) -> dict:
    return {
        "background_tasks": [
            {"id": f"bkg{index}", "status": status, "description": f"pytest -k slow{index}"}
            for index, status in enumerate(statuses)
        ]
    }


def test_stop_guard_blocks_on_a_running_task(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    result = run_guard(prepared, stop_payload("running", "completed"))
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    # Only the running task is named, and the reason says how to wait.
    assert "bkg0" in decision["reason"]
    assert "bkg1" not in decision["reason"]
    assert "foreground" in decision["reason"]
    # The reason names the remaining budget, so complying now has a point.
    assert "11 more time(s)" in decision["reason"]


def test_stop_guard_allows_a_clean_stop(tmp_path: Path) -> None:
    prepared = prepare(tmp_path)
    for payload in (stop_payload("completed"), {"background_tasks": []}, {}):
        result = run_guard(prepared, payload)
        assert result.returncode == 0
        assert result.stdout == ""
    assert not (prepared.attempt_dir / "stop_blocks").exists()


def test_stop_guard_stops_blocking_once_its_budget_is_spent(tmp_path: Path) -> None:
    # A background task that never finishes must not loop the worker
    # forever; the attempt ends and the launcher fails it instead.
    prepared = prepare(tmp_path)
    blocked = [run_guard(prepared, stop_payload("running"), max_blocks=2).stdout for _ in range(4)]
    assert [bool(output) for output in blocked] == [True, True, False, False]
    assert (prepared.attempt_dir / "stop_blocks").read_text() == "2"


def test_stop_guard_fails_open(tmp_path: Path) -> None:
    # A guard that cannot parse its input must never wedge a worker.
    prepared = prepare(tmp_path)
    for payload in ("", "not json {{{", '{"background_tasks": "nonsense"}'):
        result = run_guard(prepared, payload)
        assert result.returncode == 0
        assert result.stdout == ""


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
    assert "background task" in text.lower()
    assert "question tool" not in text.lower()
    assert "askuserquestion" not in text.lower()


def test_attempts_get_isolated_signals_files(tmp_path: Path) -> None:
    task_file = tmp_path / "01_01_task.md"
    task_file.write_text("# Task\n")
    first = prepare_attempt(tmp_path, make_node(), 0, task_file, None, None)
    second = prepare_attempt(tmp_path, make_node(), 1, task_file, None, None)
    assert first.signals_path != second.signals_path
    assert first.attempt_dir != second.attempt_dir
