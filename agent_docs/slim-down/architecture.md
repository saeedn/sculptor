# Sculptor Slim — Architecture

## Executive Summary

This is a **removal/simplification** effort, not a feature build. The
architecture's job is to identify the seams along which large
subsystems can be cut out of Sculptor — remote/containerized backends,
in-place/clone workspaces, the rich Claude/Pi chat agents, all
telemetry/diagnostics/auto-update, dependency management, the theme
builder, drag-and-drop panels, and every experimental flag — while
keeping the core intact: worktree workspaces, multiple terminal agents
per workspace, the workflow skills, PR-status tracking, and the CI
Babysitter.

The single most important finding from codebase analysis: **terminal
agents are already fully bifurcated from the rich-chat (Claude/Pi/Hello)
agents at the dispatch boundary.** `tasks/api.py::run_task` branches on
`is_terminal_agent_config(...)` *before* any agent is constructed and
routes terminal configs to a dedicated handler (`run_terminal_agent_task_v1`).
`TerminalHarness` declares every chat capability `False`. The terminal
agent never calls `create_agent_for_run`. Structurally, then, the
slim-down is **"delete the rich-chat half of an already-split system,"**
not "disentangle two woven code paths." That makes the backend cut far
lower-risk than the raw file counts suggest.

The defining *risk* is therefore not the backend but the **test suite**:
~131 of ~285 integration test files reference `FakeClaude`, plus a
`real_claude/` suite (18 files) and a `real_pi/` suite (17). REQ-TEST
mandates a deliberate per-test triage (delete vs. rewrite) and a small
**fake registered terminal agent** to replace `FakeClaude` for the tests
that survive. That triage is the center of gravity of this work.

## Current Architecture

```
                         ┌──────────────────────────────────────┐
                         │            Electron shell             │
                         │  spawns backend, auto-updater (30m),  │
                         │  SPAWN_CUSTOM_BACKEND_COMMAND override │
                         └───────────────┬──────────────────────┘
                                         │ HTTP + WS
                         ┌───────────────▼──────────────────────┐
                         │          React frontend               │
                         │  Sentry.init + PostHog init (Main.tsx)│
                         │  Onboarding(email→install→repo)        │
                         │  Settings: theme-builder, experimental,│
                         │   dependencies, telemetry, advanced    │
                         │  Panels: dnd-kit drag + resize + toggle│
                         │  ChatPanelContent ─┬─ AlphaChatInterface (chat-alpha/, 165 files)
                         │                    └─ AgentTerminalPanel (PTY)
                         └───────────────┬──────────────────────┘
                                         │
                         ┌───────────────▼──────────────────────┐
                         │            Python backend             │
                         │                                        │
                         │  tasks/api.py::run_task                │
                         │     match AgentTaskInputsV2:            │
                         │       is_terminal_agent_config? ──► run_terminal_agent_task_v1
                         │       else ───────────────────────► run_agent_task_v1
                         │                                        │     │
                         │  harness_registry: HELLO / CLAUDE /    │     │
                         │     PI / TERMINAL                      │     ▼
                         │  message_conversion (rich chat) ◄──────┘  create_agent_for_run
                         │  btw_service, /api/v1/upload-diagnostics  (Claude/Pi/Hello)
                         │  dependency_management_service +          │
                         │     managed_tools (download/install/auth) │
                         └────────────────────────────────────────┘

  AgentTypeName  = { CLAUDE, PI, TERMINAL, REGISTERED }   (web/data_types.py)
  AgentConfig    = { HelloAgentConfig, ClaudeCodeSDKAgentConfig, PiAgentConfig,
                     TerminalAgentConfig, RegisteredTerminalAgentConfig }
  WorkspaceInitializationStrategy = { IN_PLACE, CLONE, WORKTREE }
```

## Proposed Architecture

```
                         ┌──────────────────────────────────────┐
                         │            Electron shell             │
                         │  spawns local backend ONLY            │
                         │  (no auto-updater, no custom-cmd)     │
                         └───────────────┬──────────────────────┘
                                         │ HTTP + WS
                         ┌───────────────▼──────────────────────┐
                         │          React frontend               │
                         │  NO Sentry / NO PostHog (Main.tsx slim)│
                         │  Onboarding = single PATH-check screen │
                         │  Settings: appearance(light/dark/sys)  │
                         │   + surviving core sections only       │
                         │  Panels: resize + toggle (no dnd-kit)  │
                         │  ChatPanelContent ──► AgentTerminalPanel (PTY) only
                         └───────────────┬──────────────────────┘
                                         │
                         ┌───────────────▼──────────────────────┐
                         │            Python backend             │
                         │                                        │
                         │  tasks/api.py::run_task                │
                         │     match AgentTaskInputsV2:            │
                         │       (always terminal) ──► run_terminal_agent_task_v1
                         │                                        │
                         │  harness_registry: TERMINAL only       │
                         │  NO message_conversion / NO btw_service │
                         │  NO upload-diagnostics                  │
                         │  binary resolution = PATH (+ optional   │
                         │     explicit path), no managed mode     │
                         └────────────────────────────────────────┘

  AgentTypeName  = { TERMINAL, REGISTERED }
  AgentConfig    = { TerminalAgentConfig, RegisteredTerminalAgentConfig }
  WorkspaceInitializationStrategy = { WORKTREE }   (legacy values tombstoned — see Data Model)
  Bundled default: a shipped `claude` registered terminal-agent registration
```

The shape barely changes — the same three tiers remain. What changes is
that each tier sheds its non-core half: the frontend keeps only the
terminal render path, the backend keeps only the terminal task handler
and terminal harness, and the cross-cutting concerns
(telemetry/diagnostics/update/deps/custom-backend) are unhooked at their
bootstrap sites.

## Component Deep Dives

### Backend agent/task layer (REQ-AGENT, REQ-CHAT)

The cut line is the `run_task` match arm. Removing the `run_agent_task_v1`
branch and the `run_agent/` handler directory deletes the entire
rich-agent execution path in one move; the terminal branch is untouched.
Downstream of that:

- **`harness_registry.py`** collapses to a single `TERMINAL_HARNESS`
  case in both `get_harness_for_config` and `create_agent_for_run`;
  imports of the Hello/Claude/Pi harnesses and agents are dropped.
- **`agents/default/claude_code_sdk/`, `agents/pi_agent/`,
  `agents/hello_agent/`** are deleted wholesale, along with
  `claude_state`, the MCP sculptor-server tools, the agent wrapper, and
  `btw_process_manager`.
- **`AgentConfigTypes`** (the discriminated union in
  `interfaces/agents/agent.py`) drops the Hello/Claude/Pi tags, leaving
  the two terminal tags. `is_terminal_agent_config` becomes trivially
  true for every surviving config but is kept as the explicit guard.
- **`message_conversion.py`** and **`btw_service`** (REQ-CHAT-2/3) serve
  only the rich chat UI and are removed; the terminal path has no message
  stream to convert.
- **The sculptor MCP server** (`agents/default/claude_code_sdk/mcp_server.py`
  + `mcp_schemas.py` + `mcp_result_formatters.py`) lives *entirely inside*
  the rich-Claude directory and is deleted with it. Its only importers are
  within `claude_code_sdk/`, plus `state/claude_state.py` and
  `interfaces/agents/harness.py` (also pruned). **Consequence (resolves a
  spec Open Question):** terminal-mode `claude` is the user's vanilla CLI
  and does *not* connect to a sculptor MCP server; the workflow skills'
  Plan/AskUserQuestion steps fall back to Claude Code's **built-in**
  interactive tools, rendered in the terminal rather than as in-app
  blocks. The skills keep working (REQ-CORE-2); the interaction *surface*
  moves into the terminal.

  **Scope addition (Q&A):** because nothing terminal-side connects to a
  sculptor MCP server, the **bundled workflow skills themselves must be
  stripped of `mcp__sculptor__*` tool references** and rely on Claude
  Code's built-ins. This touches the shipped skill packs that the bundled
  registration loads via `--plugin-dir`: ~9 `sculptor/sculptor-workflow/
  skills/*/SKILL.md` (mock, plan, setup-repo, review, spec, fix-bug,
  architect, build + `build/implement_task.md`) and 2
  `sculptor/sculptor-experimental/skills/*` (restack, handoff). Each
  should drop the "use `mcp__sculptor__ask_user_question` if available"
  branch and call the built-in question/plan tools unconditionally.

### `sculpt` CLI agent creation (REQ-AGENT-1)

`sculpt agent create` must let a caller create either a **plain terminal**
agent or a **registered** terminal agent (selecting a registration such as
the bundled `claude-code`) — via a `--harness` selector. There are no
claude/pi harness options to drop (the CLI never exposed them). This keeps
the CLI's create surface aligned with the two surviving agent configs.

### Bundled default agent & registered-agent loading (REQ-AGENT-2/3)

**This mechanism already exists** and is *kept*, not built:
`services/terminal_agent_registry/registry.py` loads one TOML per
registration from `<sculptor folder>/terminal_agents/` (the
`registration_id` is the filename stem), and
`services/terminal_agent_registry/bundled.py` copies the shipped
`samples/terminal_agents/claude-code/` registration into that directory
once on first run (never overwriting user edits; a sentinel makes
deletion permanent). So REQ-AGENT-3's "ship a bundled `claude`
registration" is **already satisfied**. The remaining work is to make
**new-agent creation default to that registration** so a fresh agent
launches `claude` with zero setup. A `RegisteredTerminalAgentConfig`
carries `launch_command` / `resume_command_template` stamped at creation;
the terminal session renders placeholders (`{sculptor_directory}`,
`{terminal_agents_directory}`, `{session_id}`) at launch.

### CI Babysitter rewire (REQ-CORE-3 ⟂ REQ-AGENT-4)

The one place where "remove rich Claude" and "keep a core feature
unchanged" genuinely collide. `ci_babysitter_service/coordinator.py`
resolves which agent to drive into one of three results:

```
ResolvedBabysitterAgent = ChatAgent(ClaudeCodeSDK|Pi)   # drive via message queue  ── REMOVE
                        | DriveableTerminal(Registered)  # drive a registered PTY    ── KEEP
                        | Disabled(reason)               #                            ── KEEP
```

`DriveableTerminal` already drives a registered terminal agent that has
`accepts_automated_prompts = true` — and the bundled `claude-code`
registration already sets exactly that. So the surviving path works
today. What must change: the resolver currently **defaults to rich
Claude** — pinned `BabysitterAgentClaude`, and the MRU fallbacks
("no prior agent → `ChatAgent(ClaudeCodeSDKAgentConfig())`", and an
MRU-Claude/Pi → `ChatAgent`). With the rich agents gone, those arms,
the `ChatAgent` result type, and the `BabysitterAgentClaude` /
`BabysitterAgentPi` pin configs are removed. **Decision (Q&A): the
fallback is the bundled `claude` registration.** When there is no
driveable terminal MRU (empty workspace, or "no prior agent"), the
resolver returns `DriveableTerminal(bundled 'claude-code')` instead of a
`ChatAgent` — so the babysitter still spawns a `claude` to push the PR
forward, via the PTY instead of the message queue. An MRU that is a bare
`TerminalAgentConfig` (plain shell) stays `Disabled`, exactly as today.
This keeps REQ-CORE-3 behaviorally intact.

### Frontend render path (REQ-CHAT-1)

`ChatPanelContent.tsx` is the branch point. It currently selects
`AlphaChatInterface` vs `AgentTerminalPanel` via
`useTaskSupportsChatInterface`. After the cut it renders
`AgentTerminalPanel` unconditionally. The entire `chat-alpha/` tree
(~165 files + ~10 hooks + ~20 stories), `ChatInput.tsx` and its
selectors (plan-mode/effort/fast-mode/model), file-attachment UI,
queued-message edit/undo, chat search, `@`-mentions, `AskUserQuestion` /
`AlphaExitPlanModeBlock`, and `BtwPopup` are deleted. Shared task-state
hooks and `chatActionsAtom` (used by the Skills/Actions/PR panels and
the terminal path) are preserved.

### Telemetry / diagnostics / auto-update (REQ-TEL, REQ-UPD)

These are cross-cutting and unhooked at their **bootstrap sites**, which
is what makes removal safe:

- **Sentry**: `Main.tsx` `initializeSentry()` + `instrument.ts` init +
  `beforeSend` + replay buffer; the `@sentry/react` `ErrorBoundary` in
  `App.tsx` is swapped for a vanilla React error boundary.
- **PostHog**: `Main.tsx` `initializeTelemetry()` + `Telemetry.ts` /
  `Analytics.ts` + ~25 `posthog.capture()` call sites across ~11 files +
  the `/api/v1/telemetry_info` + `/api/v1/set-telemetry` handshake +
  consent atoms/flags.
- **Report-a-problem**: `ReportProblemPopover.tsx`, `reportProblem.ts`
  atoms, `web/upload_diagnostics.py`, and `POST /api/v1/upload-diagnostics`
  (S3 PUT) — the whole chain.
- **Auto-update**: `electron/main.ts` `initAutoUpdater()` call,
  `autoUpdater.ts` (`AutoUpdaterManager`, 30-min poll), the five IPC
  channels, `useInstallUpdate.ts`, and `AutoUpdateToasts.tsx`.

On-disk logging (`services/logging/`, electron `logger.ts`) is NOT
telemetry and survives. Result satisfies REQ-TEL-4: outbound traffic is
only GitHub (PR status) and the Anthropic API via the user's `claude`.

### Dependency resolution & onboarding (REQ-DEP, REQ-ONB)

`dependency_management_service.py` (~1100 lines) and `managed_tools.py`
(managed download/install/auth, version ranges, platform maps) are
removed. **Decision (Q&A): binary resolution is PATH-only** —
`shutil.which("claude")` / `shutil.which("git")` with **no config
field**; `DependencyPaths`/`BinaryMode` are deleted, not slimmed. A
non-`PATH` install is unsupported; users fix their `PATH`. The
install/auth HTTP routes are deleted; a single read-only status check may
survive to back onboarding. Onboarding collapses from email→install→repo
to a **single read-only screen** that runs `claude --version` /
`git --version` on `PATH`, reports found/missing with an install link,
and enters the app. The email-confirmation step (which fed analytics
identity) is removed entirely.

### Backend launch & container (REQ-BACKEND)

Electron always spawns the local packaged backend. The
`SPAWN_CUSTOM_BACKEND_COMMAND` path, `customBackendCommand` /
`backendReadinessTimeout` store keys, the `AdvancedSection.tsx` custom-
backend controls, and the IPC channels are removed. `container/recipes/
docker/` runtime artifacts that exist to run the *product backend*
remotely (Dockerfile, run-backend.py, download/entrypoint scripts) are
removed; build/CI/devcontainer infra is out of scope (Non-Goals).

### Settings, theme, panels, experimental (REQ-THEME, REQ-PANEL, REQ-EXP)

- **Settings** sections are registered in `pages/settings/sections.ts`;
  removing a section is a delete from the `SettingsSection` enum +
  `SETTINGS_SECTIONS` array + the matching render block in
  `SettingsPage.tsx`. Theme-builder, experimental, dependencies,
  telemetry/privacy, and advanced/custom-backend sections all go.
- **Theme**: the builder (color/font/radius/scaling pickers, hex
  overrides, `themeBuilder.ts` constants, `ThemeProvider`'s
  `buildHexOverrideStyles`) is removed. The surviving light/dark/system
  toggle keeps using the `appearance` field, `themeAppearanceAtom`, and
  `useResolvedTheme()` → Radix `<Theme appearance>`.
- **Panels**: `DockingLayout.tsx` loses its dnd-kit `DndContext` / drag
  handlers / `SidebarDropZone` / draggable `SidebarIcon`; the
  `ResizeHandle`/splitter code and the zone-visibility (show/hide) atoms
  stay. `@dnd-kit/*` deps are dropped if otherwise unused.
- **Experimental**: the section and all flags
  (`enable_review_all`, `enable_entity_mentions`,
  `enable_rich_markdown_rendering`, `is_always_interrupt_and_send`,
  `is_panel_layout_per_workspace`, `enable_frontend_plugins`,
  `enable_in_place_workspaces`, `enable_clone_workspaces`,
  `enable_pi_agent`) and the frontend `plugins/` system /
  `PanelRegistryProvider` plugin path are removed.

## Data Model Changes

**Decision (Q&A): there is no legacy DB.** The slimmed app assumes a
fresh start; the old database is discarded on upgrade, not read. This
removes the entire "don't crash on legacy rows" problem — there are no
legacy rows. Consequently the three enums are **hard-removed** to their
core values with **no tombstones and no defensive-deserialization
quarantine code**:

- `WorkspaceInitializationStrategy` (`database/workspace_enums.py`):
  reduced to `WORKTREE` only; `IN_PLACE`/`CLONE` deleted.
- `AgentTypeName` (`web/data_types.py`): reduced to `TERMINAL`,
  `REGISTERED`; `CLAUDE`/`PI` deleted.
- `AgentConfigTypes` union (`interfaces/agents/agent.py`): reduced to the
  two terminal tags; `HelloAgentConfig`/`ClaudeCodeSDKAgentConfig`/
  `PiAgentConfig` dropped.
- `BinaryMode`/`DependencyPaths`/`DependencyInfo` removed (see Dependency
  resolution — binary lookup is now PATH-only with no config field).

> **Spec note:** this relaxes REQ-WS-4 / REQ-AGENT-5, which were written
> as "legacy rows MUST NOT crash the app." Because we discard the old DB
> rather than read it, that robustness requirement is moot. The
> architecture satisfies the *intent* (a slimmed, worktree/terminal-only
> data model) by clean break rather than by defensive loading. Flagged in
> Open Questions for the user to confirm against the spec wording.

## Migration Strategy

Per spec and confirmed in Q&A: **none — and no legacy DB is read at all.**
On upgrade the prior database is discarded (fresh start); there is no
data migration, no best-effort conversion, and no legacy-row tolerance
code. The new schema/enums simply describe the only world the slimmed app
knows: worktree workspaces and terminal/registered agents.

## Files to Modify / Create / Delete

_(Draft — refined during Q&A. Grouped by action.)_

**Delete (backend):**
- `sculptor/sculptor/agents/default/claude_code_sdk/` (entire dir)
- `sculptor/sculptor/agents/pi_agent/` (entire dir)
- `sculptor/sculptor/agents/hello_agent/` (entire dir)
- `sculptor/sculptor/tasks/handlers/run_agent/` (entire dir)
- `sculptor/sculptor/web/message_conversion.py`
- `sculptor/sculptor/web/upload_diagnostics.py`
- `sculptor/sculptor/services/dependency_management_service.py`
- `sculptor/sculptor/services/managed_tools.py`
- `sculptor/sculptor/posthog_settings.py`, `sentry_settings.py`
- btw_service module(s)

**Delete (frontend / electron):**
- `sculptor/frontend/src/pages/workspace/components/chat-alpha/` (+ stories)
- `ChatInput.tsx`, `BtwPopup.tsx`, `AskUserQuestion.tsx`,
  `AlphaExitPlanModeBlock.tsx`, `QueuedMessages.tsx`
- `common/Telemetry.ts`, `common/Analytics.ts`,
  `components/ReportProblemPopover.tsx`, `state/atoms/reportProblem.ts`
- `electron/autoUpdater.ts`, `hooks/useInstallUpdate.ts`,
  `AutoUpdateToasts.tsx`
- `pages/settings/components/ThemeBuilderSection.*`,
  experimental section, dependencies/advanced sections
- `components/onboarding-wizard/InstallationStep.tsx`, `DependencyCard.tsx`
- `plugins/` (frontend plugin system), `PanelRegistryProvider`
- `components/panels/SidebarDropZone.tsx` (+ draggable `SidebarIcon`)

**Delete (container):**
- `container/recipes/docker/` runtime Dockerfile + run-backend.py +
  download/entrypoint scripts (product-backend-remote only)

**Modify:**
- `tasks/api.py` (drop the `run_agent_task_v1` arm)
- `agents/harness_registry.py` (terminal-only)
- `interfaces/agents/agent.py` (`AgentConfigTypes` → 2 tags)
- `web/data_types.py` (`AgentTypeName`; `BinaryMode`/`DependencyInfo`)
- `services/ci_babysitter_service/coordinator.py` (drop `ChatAgent` +
  Claude/Pi resolution arms; re-point the default at the bundled
  registration) and `config/user_config.py` `BabysitterAgent*` union
  (drop `BabysitterAgentClaude`/`BabysitterAgentPi`)
- `database/workspace_enums.py` (strategy enum)
- `config/user_config.py` (`DependencyPaths` simplification)
- `web/app.py` (drop deps/diagnostics/telemetry routes)
- `frontend Main.tsx`, `instrument.ts`, `App.tsx` (unhook bootstraps)
- bundled skill packs — strip `mcp__sculptor__*` references from
  `sculptor/sculptor-workflow/skills/*` (~9) and
  `sculptor/sculptor-experimental/skills/*` (2)
- `sculpt` CLI `agent create` (`--harness`: plain terminal | registered)
- `electron/main.ts` (drop auto-updater + custom-backend spawn)
- `ChatPanelContent.tsx` (terminal-only render)
- `pages/settings/sections.ts` + `SettingsPage.tsx` (section removals)
- `common/state/atoms/themeBuilder.ts`, `userConfig.ts` (flag/atom removal)
- `components/panels/DockingLayout.tsx` (de-dnd-kit)
- `onboarding-wizard/OnboardingWizard.tsx` (single PATH-check screen)

**Create:**
- A minimal onboarding PATH-check step component (replaces InstallationStep)
- A **fake registered terminal agent** test registration + scripted launch
  program (REQ-TEST-4), reusing the existing registry mechanism
- *(Not created — already exists)* the bundled `claude` registration
  (`samples/terminal_agents/claude-code/` + `terminal_agent_registry/
  bundled.py`); work is limited to defaulting new-agent creation to it.

**Delete (tests):** see Testing Strategy.

## Alternatives Considered

- **Delete the rich-agent path vs. gate it behind a disabled flag.**
  Chosen: delete outright. A dormant code path is a maintenance liability
  and keeps the very surface the spec exists to remove; the clean
  bifurcation at `run_task` makes deletion low-risk.
- **Legacy DB: tombstone enum values / defensive quarantine / clean
  break.** Chosen: clean break (no legacy DB read). The user confirmed a
  fresh-start assumption, which removes the need for tombstones or
  quarantine code entirely — the simplest end state. Tombstoning was the
  fallback if legacy DBs had to be tolerated.
- **Binary lookup: PATH-only vs. keep an explicit-path config field.**
  Chosen: PATH-only. Drops `DependencyPaths`/`BinaryMode` wholesale;
  matches the minimal onboarding check. The explicit-path field was the
  alternative for non-`PATH` installs, judged not worth the surface.
- **CI Babysitter fallback: bundled `claude` registration vs.
  drive-existing-terminal-only.** Chosen: fall back to the bundled
  `claude` registration so REQ-CORE-3 behavior is preserved; the
  terminal-only alternative would silently disable the babysitter on
  empty/shell workspaces — a behavior regression.
- **MCP-backed workflow steps vs. Claude Code built-ins.** Chosen: rely
  on Claude Code's native interactive tools in the terminal and strip
  `mcp__sculptor__*` from the bundled skills. Keeping a thin MCP bridge
  for in-app Plan/AskUserQuestion blocks was the alternative, rejected as
  re-introducing the rich surface the slim-down removes.
- **Tests: blanket-delete vs. per-test triage.** Per-test triage —
  mandated by REQ-TEST-1; blanket deletion is explicitly forbidden.
- **Onboarding: keep a slim email step vs. remove it.** Removed: the
  email step existed to feed analytics identity, which is gone; PR/commit
  attribution uses git/`gh` config, not the sculptor email, so nothing
  core depends on it.

## Risks and Mitigations

- **Test-suite blast radius (highest):** 131 FakeClaude files + 35
  real_claude/real_pi files. Mitigation (shape, not sequencing): a
  deliberate per-test delete/rewrite classification artifact, plus a
  minimal fake registered terminal agent as the replacement harness for
  surviving tests. (How the work is phased is a Plan concern.)
- **Hidden shared frontend code under chat-alpha:** some hooks/atoms are
  shared with the terminal panel (`chatActionsAtom`, task-state hooks).
  Mitigation: the explore pass mapped the dividing line; treat
  `ChatPanelContent` as the keep/cut boundary and verify imports before
  deleting.
- **Legacy DB rows crashing on startup:** Mitigation: the tombstone /
  defensive-deserialization decision (Open Questions) plus an alembic
  version-test for a legacy row.
- **Onboarding regression locking users out:** a too-strict PATH check
  could block valid setups. Mitigation: report-and-link, allow proceed
  semantics per REQ-ONB.

**Accepted behavioral changes (deliberate, not regressions):**

- **Setup-command reminder no longer auto-injected.** The first-message
  setup-reminder injection is SDK-only (`process_manager` `user_instructions`)
  and terminal agents have no first-message injection point. Decided in
  Q&A: drop it. The workspace **setup command still runs and its status
  card still shows**; only the automatic reminder text in the agent's
  first prompt goes away. (Drives the DELETE of
  `test_workspace_setup_system_reminder.py`.)
- **Plan/AskUserQuestion render in the terminal**, via Claude Code
  built-ins, not as in-app blocks (see the MCP-server deep dive).

## Testing Strategy

The integration suite is the highest-risk area. Current shape (~285
files): **211 frontend**, **37 regression**, **18 real_claude**, **17
real_pi**, 2 root. `FakeClaude` is referenced by **131** of them — **106
frontend + 22 regression + 3 real_claude**. `FakeClaude` imports from
`claude_code_sdk.harness`, so it is deleted with the rich agent and every
dependent test must be reclassified.

**How FakeClaude works (drives the triage + harness design).** It is a
*scripted* agent: a test sends a prompt carrying a command DSL —
`fake_claude:multi_step \`{"steps":[{"command":"write_file",…}]}\`` — and
the fake process interprets commands (`write_file`, `edit_file`, `bash`,
`stream_text`, `ask_user_question`, `task_create/list/update`, `sleep`,
`wait_for_file`, …) and emits Claude-JSONL for the rich message stream.
Two classes of command live in there:

- **Side-effecting** (`write_file`, `edit_file`, `bash`, `multi_step`,
  `wait_for_file`, `sleep`) — change the workspace/git state; the test
  then asserts on the diff viewer, PR status, babysitter, terminal, etc.
- **Chat-surface** (`stream_text`, `ask_user_question`, rich
  `task_*` blocks, MCP tool calls, JSONL/tool-pill emission) — drive the
  rich chat render tree being deleted.

**Triage decision rule (REQ-TEST-1/2):**

- **Subject is a removed surface** → **DELETE.** The test exists to verify
  rich chat / claude-pi specifics / telemetry / theme builder / deps /
  experimental / dnd panels. (e.g. `test_markdown_gfm.py` asserts GFM
  rendering *in the rich chat* — that render tree is gone.) This also
  covers the ~105 frontend tests that *don't* use FakeClaude but test
  removed UI (theme-builder, experimental, dependency, dnd-panel screens).
- **Subject survives, FakeClaude was only the vehicle** → **REWRITE**
  against the fake terminal agent, carrying over the side-effecting DSL.
  (PR-status tracking, babysitter, worktree lifecycle, diff/file viewer
  reacting to file changes, terminal, git ops.)

**Replacement harness (REQ-TEST-4) — simpler than FakeClaude.** Reuse the
existing registration mechanism: a test-only `.toml` whose `launch_command`
runs a scripted, controllable program. Crucially it needs **only the
side-effecting DSL** (write/edit/bash/multi_step/wait), plus the terminal
lifecycle signals the real registration emits (busy/idle/waiting/files-
changed via `sculpt signal`, and a session id for resume). It does **not**
reproduce JSONL streaming, tool-pill emission, MCP control, or
ask-user-question blocks — those surfaces no longer exist. So the fake
terminal agent is a deliberately *narrower* harness than FakeClaude, built
out only as far as the rewritten tests require.

**Removal of fakes (REQ-TEST-3).** Once no test depends on them, delete
`fake_claude*`, `fake_claude_pause`, `fake_pi`, and the entire
`real_claude/` (18) and `real_pi/` (17) suites. (real_claude/real_pi
exercise the deleted rich SDK agents; a single real-terminal-`claude`
smoke test is optional, not mandated — and these network/model tests are
already known-flaky.)

**Green gate (REQ-TEST-5).** `just test-unit` + the integration suite pass
with no references to removed agent types, fakes, or rich-chat surface.
Architecture-level e2e to preserve: create worktree workspace → spawn
bundled `claude` terminal agent → run a `/sculptor-workflow:*` skill;
push branch → PR status updates → CI Babysitter (driving the bundled
registration) advances it.

**The per-file classification is done** — see the companion
`test-triage.md` (the REQ-TEST-1 deliverable). Headline: of ~285 files,
**166 DELETE / 79 REWRITE / 34 KEEP** (~60% / 28% / 12%), all verdicts
firm (the six initially-ambiguous rows are resolved in §6). Crucially, this
**confirms the "narrower than FakeClaude" assumption**: every one of the 79
REWRITE files needs only the side-effecting DSL (write/edit/bash/git) plus
terminal lifecycle signals — none needs JSONL streaming, tool pills, MCP
control, or AUQ blocks. So the fake terminal-agent harness can be built to
that reduced surface with confidence. Sequencing remains a Plan concern.

## Open Questions

Resolved in Q&A (kept here as a record):

- ~~Legacy enum handling~~ → **No legacy DB.** Hard-remove the values;
  discard the old DB on upgrade; no quarantine code. *Relaxes the spec's
  REQ-WS-4 / REQ-AGENT-5 "must not crash on legacy rows" — confirm against
  spec wording.*
- ~~`DependencyPaths` survival~~ → **PATH-only**, no config field.

Resolved in Q&A:

- ~~Sculptor MCP server fate~~ → **removed** (lives inside the deleted
  `claude_code_sdk/`). Terminal `claude` uses Claude Code's built-in
  interactive tools, accepted as the intended UX; additionally the bundled
  workflow skills are stripped of `mcp__sculptor__*` references.
- ~~Bundled default registration shape~~ → **already exists**
  (`bundled.py` + `samples/terminal_agents/claude-code/`); only defaulting
  new-agent creation to it remains.
- ~~CI Babysitter fallback~~ → **bundled `claude` registration** (keeps
  REQ-CORE-3 intact; bare-shell MRU stays Disabled).
- ~~`sculpt` CLI create surface~~ → keep `--harness` (plain terminal |
  registered); no claude/pi options existed to drop.

Remaining for the user to confirm against the spec:

- The Data-Model clean break **relaxes REQ-WS-4 / REQ-AGENT-5** ("must not
  crash on legacy rows"): because the old DB is discarded, that
  robustness requirement is moot. Confirm the spec wording should be read
  as satisfied-by-clean-break, or update the spec in the Spec tab.
