"""Fake registered terminal-agent harness for integration tests.

This is the deterministic, test-only **registered terminal agent** that the
surviving integration tests use as their vehicle to mutate workspace/git state.
It is the productized, reusable version of the inline shell snippet in
``test_registered_terminal_agent.py`` — a real TOML registration whose
``launch_command`` runs ``fake_terminal_agent_runner.py`` (a pure-stdlib program
that drives the real ``sculpt signal`` CLI for lifecycle).

What it does:
  * registers a fake terminal agent by writing a ``.toml`` (and copying its
    runner program) into a ``terminal_agents`` directory;
  * exposes a small side-effecting command DSL — ``write_file``, ``edit_file``,
    ``bash``, ``multi_step``, ``wait_for_file``, ``sleep`` — whose builders
    return plain JSON-able dicts a test sends to the running agent at runtime;
  * drives the agent end-to-end from a Playwright test via
    ``start_fake_terminal_agent``.

What it deliberately does NOT do: there is **no chat surface**. It does not
emit JSONL, tool pills, MCP control messages, or ask-user-question blocks — the
slim-down triage confirmed no surviving test needs any of those, and they are
being removed. Resist re-creating ``FakeClaude``'s breadth here.

Usage (integration test)::

    from sculptor.testing.fake_terminal_agent import (
        start_fake_terminal_agent, send_fake_agent_command, write_file, bash,
    )

    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"
    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir)
    send_fake_agent_command(agents_dir, write_file("hello.txt", "hi"))
    # ...assert the diff viewer reflects hello.txt, the tab dot tracks busy→idle.

The unit test ``fake_terminal_agent_test.py`` covers DSL/.toml generation; the
integration test ``test_fake_terminal_agent_harness.py`` is the canonical
end-to-end example every REWRITE task copies.
"""

import json
import shutil
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import expect

from sculptor.testing import fake_terminal_agent_runner
from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.elements.terminal import get_agent_terminal_panel
from sculptor.testing.elements.terminal import wait_for_xterm_substring
from sculptor.testing.pages.task_page import PlaywrightTaskPage
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready

DEFAULT_REGISTRATION_ID = "fake-terminal-agent"
DEFAULT_DISPLAY_NAME = "Fake Terminal Agent"
READY_BANNER = "FAKE-TERMINAL-AGENT-READY"

_TERMINAL_AGENTS_PLACEHOLDER = "{terminal_agents_directory}"
_SESSION_ID_PLACEHOLDER = "{session_id}"


# --- Side-effecting command DSL ------------------------------------------------
# Each builder returns a plain JSON-able dict the runner understands. Field names
# mirror the side-effecting handlers in ``agents/testing/fake_claude_commands.py``
# (write_file/edit_file/bash/sleep/wait_for_file/multi_step) so the semantics
# stay familiar; the chat-surface commands are intentionally absent.


def write_file(file_path: str, content: str) -> dict:
    """Write ``content`` to ``file_path`` (relative to the agent's cwd)."""
    return {"op": "write_file", "file_path": file_path, "content": content}


def edit_file(file_path: str, old_string: str, new_string: str) -> dict:
    """Replace the first occurrence of ``old_string`` with ``new_string``."""
    return {"op": "edit_file", "file_path": file_path, "old_string": old_string, "new_string": new_string}


def bash(command: str) -> dict:
    """Run ``command`` in a shell at the agent's cwd."""
    return {"op": "bash", "command": command}


def sleep(seconds: float) -> dict:
    """Stay busy for ``seconds`` (wall-clock)."""
    return {"op": "sleep", "seconds": seconds}


def wait_for_file(path: str, timeout_seconds: float = 120.0) -> dict:
    """Block (staying busy) until ``path`` exists — gate busy→idle on an event.

    Prefer this over ``sleep`` when a test needs to observe the running dot
    deterministically: the agent holds busy until the test creates the sentinel
    (see ``release_fake_agent_wait``), instead of racing a wall-clock timer.
    """
    return {"op": "wait_for_file", "path": path, "timeout_seconds": timeout_seconds}


def multi_step(steps: list[dict]) -> dict:
    """Run an ordered list of the above commands as a single busy→idle turn."""
    return {"op": "multi_step", "steps": steps}


# --- Registration --------------------------------------------------------------


def _runner_filename(registration_id: str) -> str:
    return f"{registration_id}__runner.py"


def commands_dir_for(terminal_agents_dir: Path, registration_id: str = DEFAULT_REGISTRATION_ID) -> Path:
    """The directory the test drops command files into / the runner polls."""
    return terminal_agents_dir / f"{registration_id}__commands"


def register_fake_terminal_agent(
    terminal_agents_dir: Path,
    *,
    registration_id: str = DEFAULT_REGISTRATION_ID,
    display_name: str = DEFAULT_DISPLAY_NAME,
    accepts_automated_prompts: bool = True,
) -> str:
    """Write the fake terminal agent's ``.toml`` + runner into ``terminal_agents_dir``.

    Returns the ``registration_id`` (also the ``.toml`` filename stem). The
    runner program is copied next to the ``.toml`` so the registration is
    self-contained and references it via ``{terminal_agents_directory}``.
    ``accepts_automated_prompts`` defaults to ``True`` so babysitter /
    automated-prompt tests can drive it, matching the bundled ``claude-code``
    registration.
    """
    terminal_agents_dir.mkdir(parents=True, exist_ok=True)
    commands_dir_for(terminal_agents_dir, registration_id).mkdir(parents=True, exist_ok=True)

    runner_dest = terminal_agents_dir / _runner_filename(registration_id)
    shutil.copyfile(fake_terminal_agent_runner.__file__, runner_dest)

    runner_ref = f'"{_TERMINAL_AGENTS_PLACEHOLDER}/{_runner_filename(registration_id)}"'
    commands_ref = f'"{_TERMINAL_AGENTS_PLACEHOLDER}/{registration_id}__commands"'
    session_id = f"{registration_id}-session"
    common = f"python3 {runner_ref} --commands-dir {commands_ref} --session-id {session_id} --banner "
    launch_command = common + READY_BANNER
    # The fake has no real session to resume; relaunching the runner with the
    # reported {session_id} as its banner proves the resume path renders the id.
    resume_command = common + f"RESUMED-{_SESSION_ID_PLACEHOLDER}"

    toml_lines = [
        f'display_name = "{display_name}"',
        f"launch_command = {json.dumps(launch_command)}",
        f"resume_command_template = {json.dumps(resume_command)}",
        f"accepts_automated_prompts = {str(accepts_automated_prompts).lower()}",
    ]
    (terminal_agents_dir / f"{registration_id}.toml").write_text("\n".join(toml_lines) + "\n")
    return registration_id


# --- Runtime command delivery --------------------------------------------------


def send_fake_agent_command(
    terminal_agents_dir: Path,
    command: dict,
    *,
    registration_id: str = DEFAULT_REGISTRATION_ID,
) -> Path:
    """Drop ``command`` (a DSL dict) for the running agent to pick up.

    Writes a uniquely-named, name-ordered ``*.json`` file into the commands
    directory atomically (temp + rename) so the runner never reads a partial
    file. Returns the command-file path; ``<path>.done`` appears once the runner
    has finished executing it.
    """
    commands_dir = commands_dir_for(terminal_agents_dir, registration_id)
    commands_dir.mkdir(parents=True, exist_ok=True)
    index = len(list(commands_dir.glob("*.json")))
    final_path = commands_dir / f"{index:06d}.json"
    tmp_path = commands_dir / f".{index:06d}.json.tmp"
    tmp_path.write_text(json.dumps(command))
    tmp_path.rename(final_path)
    return final_path


def release_fake_agent_wait(
    terminal_agents_dir: Path,
    sentinel_path: str,
    *,
    registration_id: str = DEFAULT_REGISTRATION_ID,
) -> Path:
    """Create the sentinel a ``wait_for_file`` command is blocked on.

    The sentinel path is resolved relative to the commands directory unless it
    is absolute — keep test sentinels there so they never pollute the diff.
    """
    candidate = Path(sentinel_path)
    if not candidate.is_absolute():
        candidate = commands_dir_for(terminal_agents_dir, registration_id) / candidate
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("release")
    return candidate


def stop_fake_terminal_agent(
    terminal_agents_dir: Path,
    *,
    registration_id: str = DEFAULT_REGISTRATION_ID,
) -> None:
    """Ask the runner to exit cleanly (lands the shell at a usable prompt)."""
    commands_dir = commands_dir_for(terminal_agents_dir, registration_id)
    commands_dir.mkdir(parents=True, exist_ok=True)
    (commands_dir / fake_terminal_agent_runner.QUIT_SENTINEL_NAME).write_text("quit")


# --- Playwright entry point ----------------------------------------------------


def start_fake_terminal_agent(
    page: Page,
    terminal_agents_dir: Path,
    *,
    registration_id: str = DEFAULT_REGISTRATION_ID,
    workspace_name: str | None = None,
    prompt: str = "Say hello",
) -> tuple[PlaywrightTaskPage, PlaywrightAgentTabBarElement]:
    """Create a workspace, register the fake, and launch it as a new agent.

    Parallels ``start_task_and_wait_for_ready``: creates the workspace + first
    agent, registers the fake terminal agent, then selects it from the agent-type
    menu and waits for its terminal panel + ready banner. Returns the task page
    (for the changes/diff panel) and the agent tab bar POM.
    """
    task_page = start_task_and_wait_for_ready(page, prompt=prompt, workspace_name=workspace_name)
    register_fake_terminal_agent(terminal_agents_dir, registration_id=registration_id)

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    agent_tab_bar.open_agent_type_menu()
    registered_item = agent_tab_bar.get_agent_type_menu_item_registered(registration_id)
    expect(registered_item).to_be_visible()
    registered_item.click()

    expect(get_agent_terminal_panel(page)).to_be_visible()
    wait_for_xterm_substring(page, READY_BANNER)
    return task_page, agent_tab_bar
