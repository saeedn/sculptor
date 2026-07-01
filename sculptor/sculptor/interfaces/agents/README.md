# `Agent` interface

An `Agent` is a terminal program — the user's coding CLI (e.g. Claude Code) —
run in a PTY inside a workspace. Sculptor launches it, streams its terminal to
the frontend, and lets the user drive it directly.

Key types (`agent.py`):

- **`AgentConfig`** — how to launch the agent. The two concrete configs are
  `TerminalAgentConfig` (the built-in terminal) and `RegisteredTerminalAgentConfig`
  (a user-authored registration; see `services/terminal_agent_registry`). The
  launch/resume commands and whether the agent accepts automated prompts come
  from the registration.
- **`*RunnerMessage`** — the messages the task runner emits over a task's life:
  environment acquire/release, task-status ticks (`TaskStatusRunnerMessage`),
  the terminal busy/idle/waiting signal (`TerminalAgentSignalRunnerMessage`),
  and the crash/error variants. `web/derived.py` computes a task's status and
  workspace-peek view from this log.

Notes:

- Terminal agents have **no structured message stream**. Their busy/idle/waiting
  state — including plan mode — is reported by shell hooks
  (`claude-code-hooks.json` → `sculpt signal`), not parsed from agent output.
- Agents run as idempotent, resumable tasks. A registration's resume command,
  keyed by the session id the hooks report, lets a restart resume the same
  session. Because a task may be re-run, consumers of the message log must
  tolerate duplicate messages (ids can differ between runs).
