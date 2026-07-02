---
name: write-integration-test
description: |
  Instructions for writing new Sculptor frontend integration tests.
  Covers how to use the fake registered terminal agent for deterministic
  agent behavior, test file setup, and the available agent commands.
  Use when writing new integration tests or adding tests to existing files.
---

# Writing New Integration Tests

This skill explains how to write a new frontend integration test for Sculptor.

Sculptor's agents are terminal agents: an agent is a program running in a PTY,
and Sculptor learns its busy/idle state, session id, and file changes only from
the agent invoking the `sculpt signal` CLI. Tests therefore come in two
flavors: those that only need *an agent to exist* (use a plain Terminal agent),
and those that need to *control what the agent does* (use the fake registered
terminal agent).

## First Decision: Plain Terminal Agent vs Fake Terminal Agent

### Plain Terminal agent (prefer this when possible)

`start_task_and_wait_for_ready()` (from `sculptor.testing.playwright_utils`)
creates a workspace whose first agent is a plain **Terminal** — a bare shell.
It always launches in CI with no real `claude` binary and no special setup.

**Use a plain terminal agent when:** the test doesn't depend on agent behavior
— e.g., testing UI elements, workspace lists, settings pages, modals, panel
toggles, navigation, or any feature where it only matters that a workspace and
agent exist.

```python
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready

task_page = start_task_and_wait_for_ready(sculptor_instance_.page)
```

### Fake terminal agent (for controlled agent behavior)

If your test needs the agent to *do* things — write files, run bash commands,
stay busy while you assert on the running dot, survive a restart and resume —
use the **fake registered terminal agent**
(`sculptor/sculptor/testing/fake_terminal_agent.py`). It is a real registered
terminal agent (a `.toml` registration whose `launch_command` runs a
pure-stdlib runner program), so it exercises the same code paths as a real
`claude` registration: PTY launch, `sculpt signal` lifecycle events
(`busy`/`idle`/`files-changed`/`session-id`), and resume via
`resume_command_template`.

The test drives it at runtime by dropping JSON command files that the runner
polls and executes. Each command is one busy→idle turn.

**Use the fake terminal agent when:** the test asserts on file changes in the
diff viewer, agent busy/idle status dots, resume-after-restart behavior, or
anything else that requires deterministic agent side effects.

### Available fake-agent commands (the side-effecting DSL)

Builders in `sculptor.testing.fake_terminal_agent` return plain JSON-able
dicts; send them with `send_fake_agent_command(...)`:

| Builder | Description |
|---------|-------------|
| `write_file(file_path, content)` | Write a file (relative to the agent's cwd) |
| `edit_file(file_path, old_string, new_string)` | Replace the first occurrence of `old_string` |
| `bash(command)` | Run a shell command at the agent's cwd |
| `sleep(seconds)` | Stay busy for a wall-clock duration (avoid — see below) |
| `wait_for_file(path, timeout_seconds=120)` | Block (staying busy) until a sentinel file exists |
| `multi_step(steps)` | Run an ordered list of the above as a single busy→idle turn |

There is deliberately **no chat surface** (no text responses, tool pills, or
ask-user-question blocks) — the product has no rich chat UI. Resist extending
the DSL beyond side effects; if the UI you're testing can be driven by files,
bash, and lifecycle signals, that's all you need.

**Key helpers:**

- `start_fake_terminal_agent(page, terminal_agents_dir)` — creates a workspace,
  registers the fake, launches it, and waits for its ready banner. Returns
  `(task_page, agent_tab_bar)`.
- `add_registered_fake_terminal_agent(page, terminal_agents_dir)` — adds the
  fake as an *additional* agent to an existing workspace (for multi-agent
  tests).
- `send_fake_agent_command(terminal_agents_dir, command)` — queue a command;
  returns immediately.
- `send_fake_agent_command_and_wait(...)` — queue a command and block until the
  runner finished executing it (`<command>.done` marker). Use this before
  asserting on the side effect's result.
- `wait_for_file(...)` + `release_fake_agent_wait(terminal_agents_dir, path)` —
  hold the agent busy until the test creates the sentinel. **Always prefer this
  over `sleep`** when the test must observe a transient state (e.g. the running
  dot): a wall-clock sleep is asymptotically racy under CI load (see
  `no_wall_clock_in_fake_agent` in `docs/development/review/integration_tests.md`).
- `stop_fake_terminal_agent(terminal_agents_dir)` — ask the runner to exit
  cleanly, landing the shell at a usable prompt.

The `terminal_agents_dir` is always
`sculptor_instance_.sculptor_folder / "terminal_agents"`.

## CRITICAL: Use `/run-integration-test` to Run Tests

**You MUST use the `/run-integration-test` skill to run integration tests.** Do not run `pytest` or `just test-integration` directly — the skill handles background execution and timeout monitoring, which is required because integration tests can hang indefinitely on failure. Running in foreground will block you with no way to recover.

Any `just test-integration` commands shown in docs are for **human developers only**. As an agent, always use `/run-integration-test` instead.

## Step-by-Step: Writing a New Test

### Step 1: Write the test file

Create your test file in `sculptor/tests/integration/frontend/`. Follow the patterns in the existing README at `sculptor/tests/integration/frontend/README.md`.

Key conventions:
- Use `sculptor_instance_: SculptorInstance` fixture for tests using the shared instance
- Use `sculptor_instance_factory_: SculptorInstanceFactory` for tests that need multiple Sculptor instances (e.g., restart tests — see `test_restarts.py`)
- Use `@user_story("...")` decorator
- Use Playwright `expect()` for all assertions (auto-retrying)
- Access elements through the POM hierarchy, never raw `get_by_test_id()` in test code
- Use `only()` from `imbue_core.itertools` when expecting exactly one element
- Read `docs/development/review/integration_tests.md` to avoid common anti-patterns (flaky sleeps, snapshot races, missing waits)

#### Minimal example (plain terminal agent — no agent control needed):

```python
"""Integration tests for my new feature."""

from playwright.sync_api import expect

from sculptor.testing.elements.agent_tab import PlaywrightAgentTabBarElement
from sculptor.testing.playwright_utils import start_task_and_wait_for_ready
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story


@user_story("to verify my new feature works")
def test_my_feature(sculptor_instance_: SculptorInstance) -> None:
    """Test that my feature works correctly."""
    page = sculptor_instance_.page

    start_task_and_wait_for_ready(page, workspace_name="My Feature WS")

    agent_tab_bar = PlaywrightAgentTabBarElement(page)
    expect(agent_tab_bar.get_agent_tabs()).to_have_count(1)

    # ... your assertions on UI elements here ...
```

#### Controlled-behavior example (fake terminal agent):

This is a condensed version of the canonical harness test,
`test_fake_terminal_agent_harness.py::test_fake_terminal_agent_drives_diff_and_tab_dot`
— copy that file when in doubt:

```python
"""Integration tests that require controlled agent behavior."""

import re

from playwright.sync_api import expect

from sculptor.testing.elements.file_tree import get_changes_tree
from sculptor.testing.fake_terminal_agent import DEFAULT_DISPLAY_NAME
from sculptor.testing.fake_terminal_agent import multi_step
from sculptor.testing.fake_terminal_agent import release_fake_agent_wait
from sculptor.testing.fake_terminal_agent import send_fake_agent_command
from sculptor.testing.fake_terminal_agent import start_fake_terminal_agent
from sculptor.testing.fake_terminal_agent import wait_for_file
from sculptor.testing.fake_terminal_agent import write_file
from sculptor.testing.sculptor_instance import SculptorInstance
from sculptor.testing.user_stories import user_story

_CALM = re.compile(r"^(read|unread)$")


@user_story("to see the agent's file changes in the diff viewer")
def test_agent_creates_file(sculptor_instance_: SculptorInstance) -> None:
    page = sculptor_instance_.page
    agents_dir = sculptor_instance_.sculptor_folder / "terminal_agents"

    task_page, agent_tab_bar = start_fake_terminal_agent(page, agents_dir)
    terminal_tab = agent_tab_bar.get_agent_tab_by_name(f"{DEFAULT_DISPLAY_NAME} 1").first

    # Write a file, then hold busy on a sentinel so the running dot is observable.
    send_fake_agent_command(
        agents_dir,
        multi_step([write_file("hello.py", "print('hello')\n"), wait_for_file("release.sentinel")]),
    )
    expect(terminal_tab).to_have_attribute("data-dot-status", "running")

    task_page.activate_changes_panel()
    changes_tree = get_changes_tree(page)
    expect(changes_tree.get_tree_rows().filter(has_text="hello.py")).to_be_visible()

    # Release the wait — the turn finishes and the dot settles calm.
    release_fake_agent_wait(agents_dir, "release.sentinel")
    expect(terminal_tab).to_have_attribute("data-dot-status", _CALM)
```

#### Waiting for a side effect to land (send-and-wait):

`send_fake_agent_command` returns before the side effect has been applied. If
the next step reads workspace state (e.g. the Browse tree, or a commit made
via `bash`), use the blocking variant:

```python
from sculptor.testing.fake_terminal_agent import bash, send_fake_agent_command_and_wait

send_fake_agent_command_and_wait(
    agents_dir,
    bash("git add hello.py && git commit -m 'Add hello'"),
)
# The `.done` marker exists — the commit is on disk; now assert on the UI.
```

#### Custom registrations (advanced):

When the fake agent's DSL doesn't fit — e.g. testing automated prompt
delivery, or lifecycle edge cases — write a purpose-built registration TOML
whose `launch_command` is an inline shell program that emits the `sculpt
signal` events your test needs. See `test_ci_babysitter.py`
(`_FAKE_PROMPTS_COMMAND` + `_write_registration`) and
`test_registered_terminal_agent.py` for the pattern.

### Step 2: Run the test

Use `/run-integration-test` to run your test:

```
/run-integration-test sculptor/tests/integration/frontend/test_my_feature.py
```

Fake-terminal-agent tests require no special setup — no API keys, no real
`claude` binary. They run deterministically every time.

### Step 3: Commit the test

```bash
git add sculptor/tests/integration/frontend/test_my_feature.py
```

## Troubleshooting

If a test fails, use the `/debug-integration-test` skill. It covers common failure modes (Playwright timeouts, element state issues), how to read test logs, and investigation strategies.
