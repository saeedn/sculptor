"""Unit/smoke test for the fake terminal-agent harness.

Verifies DSL builders, ``.toml`` generation (parses + validates against the
real ``TerminalAgentRegistration``), command delivery, and the runner's
side-effecting command execution — independent of the integration suite.
"""

import json
import tomllib
from pathlib import Path

import pytest

from sculptor.services.terminal_agent_registry.registry import TerminalAgentRegistration
from sculptor.testing import fake_terminal_agent as harness
from sculptor.testing.fake_terminal_agent_runner import execute_command


def test_dsl_builders_produce_expected_dicts() -> None:
    assert harness.write_file("a.txt", "hi") == {"op": "write_file", "file_path": "a.txt", "content": "hi"}
    assert harness.edit_file("a.txt", "x", "y") == {
        "op": "edit_file",
        "file_path": "a.txt",
        "old_string": "x",
        "new_string": "y",
    }
    assert harness.bash("ls") == {"op": "bash", "command": "ls"}
    assert harness.sleep(2) == {"op": "sleep", "seconds": 2}
    wait = harness.wait_for_file("done", timeout_seconds=5)
    assert wait == {"op": "wait_for_file", "path": "done", "timeout_seconds": 5}
    nested = harness.multi_step([harness.write_file("a.txt", "hi"), harness.bash("ls")])
    assert nested["op"] == "multi_step"
    assert [step["op"] for step in nested["steps"]] == ["write_file", "bash"]


def test_register_writes_valid_toml_and_runner(tmp_path: Path) -> None:
    agents_dir = tmp_path / "terminal_agents"
    registration_id = harness.register_fake_terminal_agent(agents_dir)
    assert registration_id == harness.DEFAULT_REGISTRATION_ID

    toml_path = agents_dir / f"{registration_id}.toml"
    runner_path = agents_dir / f"{registration_id}__runner.py"
    assert toml_path.exists()
    assert runner_path.exists()
    # The runner copy is the real runner source (has the ready loop entrypoint).
    assert "def main(" in runner_path.read_text()

    data = tomllib.loads(toml_path.read_text())
    # Constructing the real registration validates the placeholders are accepted
    # (only {terminal_agents_directory} / {session_id}) — a bad token would raise.
    registration = TerminalAgentRegistration(registration_id=registration_id, **data)
    assert registration.display_name == harness.DEFAULT_DISPLAY_NAME
    assert registration.accepts_automated_prompts is True
    assert harness._TERMINAL_AGENTS_PLACEHOLDER in registration.launch_command
    assert registration.resume_command_template is not None
    assert harness._SESSION_ID_PLACEHOLDER in registration.resume_command_template


def test_register_respects_accepts_automated_prompts_flag(tmp_path: Path) -> None:
    agents_dir = tmp_path / "terminal_agents"
    harness.register_fake_terminal_agent(agents_dir, registration_id="no-auto", accepts_automated_prompts=False)
    data = tomllib.loads((agents_dir / "no-auto.toml").read_text())
    assert TerminalAgentRegistration(registration_id="no-auto", **data).accepts_automated_prompts is False


def test_send_command_writes_ordered_json(tmp_path: Path) -> None:
    agents_dir = tmp_path / "terminal_agents"
    harness.register_fake_terminal_agent(agents_dir)
    first = harness.send_fake_agent_command(agents_dir, harness.write_file("a.txt", "1"))
    second = harness.send_fake_agent_command(agents_dir, harness.bash("ls"))
    assert first.name < second.name  # name-ordered so the runner runs them in order
    assert json.loads(first.read_text())["op"] == "write_file"
    assert json.loads(second.read_text())["op"] == "bash"


def test_execute_write_edit_and_multi_step(tmp_path: Path) -> None:
    changes: list[int] = []
    on_files_changed = lambda: changes.append(1)  # noqa: E731

    execute_command(harness.write_file("dir/a.txt", "hello"), tmp_path, on_files_changed)
    assert (tmp_path / "dir" / "a.txt").read_text() == "hello"

    execute_command(harness.edit_file("dir/a.txt", "hello", "world"), tmp_path, on_files_changed)
    assert (tmp_path / "dir" / "a.txt").read_text() == "world"

    execute_command(
        harness.multi_step([harness.write_file("b.txt", "x"), harness.bash("echo hi > c.txt")]),
        tmp_path,
        on_files_changed,
    )
    assert (tmp_path / "b.txt").read_text() == "x"
    assert (tmp_path / "c.txt").read_text().strip() == "hi"
    # write + edit + (write + bash) == 4 mutating leaf operations.
    assert len(changes) == 4


def test_edit_file_missing_old_string_raises(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    with pytest.raises(RuntimeError, match="old_string not found"):
        execute_command(harness.edit_file("a.txt", "absent", "x"), tmp_path)


def test_unknown_op_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown fake-terminal-agent command op"):
        execute_command({"op": "stream_text", "text": "nope"}, tmp_path)


def test_wait_for_file_returns_when_present_and_times_out(tmp_path: Path) -> None:
    (tmp_path / "ready").write_text("go")
    execute_command(harness.wait_for_file("ready"), tmp_path)  # returns immediately

    with pytest.raises(RuntimeError, match="wait_for_file timed out"):
        execute_command(harness.wait_for_file("never", timeout_seconds=0.1), tmp_path)
