# Sculptor Slim — Remove Non-Core Features

## Overview

Sculptor has accumulated a wide surface area of features. Many of them
are not core to its main value-add and add complexity, reduce
reliability, and slow the app down. This effort removes that
non-core surface area to produce a simpler, more reliable, and snappier
product.

The **core value-add** that must remain intact:

- **Workspace management** with multiple agents per workspace.
- **Rich workflows** that come from our workflow skills.
- **PR status tracking.**
- **The CI Babysitter** for moving PRs forward.

Everything that distracts from those goals is a candidate for removal.

### Features slated for removal (from the initial request)

- **Remote/containerized backend.** No requirement to run the backend
  in a container or on a separate host — remove all explicit support.
- **In-place and clone workspaces.** Support **only** worktrees.
- **Rich Claude and Pi agent integrations.** Support **only** terminal
  agents (plain and registered).
- **Rich-chat-only features.** Everything that exists only within the
  rich chat interface (e.g. the `/btw` command — and others to be
  found during exploration).
- **All telemetry, bug reporting, and data uploads** of any kind.
- **Dependency management.** The user installs `claude` and `git`
  themselves.
- **The theme builder.**
- **Drag-and-drop panels.** Panels become fixed-position, toggle on/off
  only.
- **All experimental features.**

### Additional non-core features surfaced during exploration

Beyond the initial list, codebase exploration surfaced these
candidates — most are sub-cases of the categories above, called out
explicitly so nothing is missed:

- **"Report a problem" flow** — uploads a diagnostics zip to S3 and
  sends Sentry feedback + buffered session replay
  (`ReportProblemPopover.tsx`, `upload_diagnostics.py`,
  `/api/v1/upload-diagnostics`). A form of data upload → remove.
- **Onboarding wizard** — its installation step depends on dependency
  management, and its email-confirmation step feeds analytics
  identity (`onboarding-wizard/`, `OnboardingWizard.tsx`). Needs
  rethinking once deps + telemetry are gone.
- **Custom-backend-command setting** — lets the user point the
  Electron shell at an arbitrary backend process
  (`SETTINGS_CUSTOM_BACKEND_COMMAND`, Electron `SPAWN_CUSTOM_BACKEND_COMMAND`).
  This is the only "remote/other-host backend" hook → remove.
- **Frontend plugins system** — gated by an experimental flag
  (`enable_frontend_plugins`); panels can be plugin-contributed
  (`PanelRegistryProvider`, `plugins/`). Removed as experimental.
- **Pi agent** — the entire `sculptor/agents/pi_agent/` integration,
  plus `fake_pi`, `real_pi` tests, and `enable_pi_agent` flag.
- **Rich-chat-only chat affordances** — `/btw`, `/clear`, `/copy`
  pseudo-skills; ask-user-question & plan-mode interactive blocks;
  entity @-mentions; file attachments; message queue/edit/undo;
  chat search/navigation; effort/fast-mode/model selectors;
  smooth-streaming; the whole `chat-alpha/` render tree.
- **Other experimental flags** — `enable_review_all`,
  `enable_entity_mentions`, `enable_rich_markdown_rendering`,
  `is_always_interrupt_and_send`, `is_panel_layout_per_workspace`.
- **`HelloAgent`** — a test-double agent type, removable with the
  rich-agent cleanup.

### What stays (the core)

- Worktree-based workspace management; multiple agents per workspace.
- Terminal agents only: **plain** (`TerminalAgentConfig`) and
  **registered** (`RegisteredTerminalAgentConfig`, loaded from
  `~/.sculptor/terminal_agents/*.toml`).
- The workflow skills (run as Claude Code skills *inside* a terminal
  agent) — `/sculptor-workflow:*`, etc.
- PR status tracking and the CI Babysitter.
- Local git operations, the diff/file viewer, the terminal panel.

### Decisions made so far

- **No migration (clean break).** Legacy in-place/clone workspaces and
  Claude/Pi rich-chat agents are simply unsupported. No migration or
  best-effort-conversion code; the slimmed app assumes a fresh start.
- **No diagnostics path at all.** The entire "Report a problem" flow
  (S3 upload, Sentry feedback, session replay) is removed. Logs remain
  on disk for a user to find manually; there is no in-app export.
- **Auto-update removed.** No periodic manifest check, no outbound
  update calls. The only outbound network is to GitHub (PR status) and
  the Anthropic API (via the user's `claude`). Users update manually.
- **Onboarding = minimal one-screen check.** A single read-only screen
  verifies `claude` and `git` are on `PATH` (no install attempt), then
  enters the app. No email confirmation, no dependency installation,
  no telemetry consent.
- **Default agent ships a bundled `claude` registration.** The app
  includes a default registered terminal-agent registration so a new
  agent launches `claude` immediately and workflow skills run with zero
  setup. Plain shell and user-defined registrations remain available.
- **Panels keep resizing.** Drag-to-reorder and zone reassignment are
  removed; resize handles/splits stay so users can adjust the space a
  visible panel gets. The only per-panel control is show/hide.
- **Appearance keeps a simple light/dark/system toggle.** The theme
  builder (custom colors/fonts/radius/scaling) is deleted; a basic
  appearance setting survives, no longer sourced from the builder.

## User Scenarios

### First run (onboarding)
A user opens the slimmed app for the first time. A single screen
checks that `claude` and `git` are on `PATH`. Both present → they
proceed into the app. If `claude` is missing, the screen says so in
plain language and links to install instructions; there is no
in-app installer (REQ-ONB-1, REQ-ONB-2, REQ-DEP-1).

### Creating a worktree workspace
The user clicks "add workspace", picks a repo and a branch name, and
gets a git **worktree** off their repo. There is no mode selector —
worktree is the only kind. Branch name is required (REQ-WS-1,
REQ-WS-2). The add-workspace page no longer shows in-place or clone
options (REQ-WS-3).

### Running multiple agents in a workspace
Inside the workspace the user spawns several agents. By default a new
agent launches the bundled `claude` registered terminal agent and
drops straight into a terminal; the workflow skills (`/sculptor-workflow:*`)
work because they are Claude Code skills running in that terminal
(REQ-AGENT-1, REQ-AGENT-3, REQ-CORE-2). The user can also create a
plain shell agent, or register their own tool via a
`~/.sculptor/terminal_agents/*.toml` (REQ-AGENT-2). There is no rich
Claude or Pi chat agent option in the menu (REQ-AGENT-4).

### The terminal-only agent surface
Every agent renders as a terminal panel. There is no structured chat
UI: no `/btw` side-chat, no `/clear` or `/copy` pseudo-skills, no
ask-user-question/plan-mode blocks, no @-mentions, no file
attachments, no message queue/edit/undo, no chat search, no
effort/fast-mode/model selectors (REQ-CHAT-1, REQ-CHAT-2).

### PR tracking and the CI Babysitter still work
The user pushes a branch and watches PR status update in Sculptor;
the CI Babysitter continues to move the PR forward. These are
unchanged by the slim-down (REQ-CORE-3).

### Toggling and resizing panels
The user shows/hides individual panels. Panels sit in fixed slots —
they cannot be dragged to new positions or reordered — but the user
can still drag the splitters to resize visible regions (REQ-PANEL-1,
REQ-PANEL-2, REQ-PANEL-3).

### Settings, slimmed
Opening settings, the user sees a much shorter list: a light/dark/
system appearance toggle survives (REQ-THEME-2); the theme builder,
experimental section, dependencies section, telemetry/privacy
section, and the custom-backend/advanced controls are all gone
(REQ-THEME-1, REQ-EXP-1, REQ-DEP-2, REQ-TEL-3, REQ-BACKEND-2).

### No data leaves the machine
No telemetry, analytics, crash reports, session replay, diagnostics
uploads, or update pings are emitted. The only outbound traffic is to
GitHub (PR status) and to the Anthropic API via the user's `claude`
(REQ-TEL-1, REQ-TEL-2, REQ-UPD-1).

### Upgrading from an older install (clean break)
A user who previously had in-place/clone workspaces or Claude/Pi
agents upgrades. The slimmed app does not attempt to migrate or run
that legacy state; only worktree workspaces and terminal agents are
supported going forward. No crash, but legacy items are not
resurrected (REQ-WS-4, REQ-AGENT-5).

## Requirements

### Workspaces (REQ-WS)
- **REQ-WS-1** — The app MUST support creating only **worktree**
  workspaces. In-place and clone creation paths MUST be removed.
- **REQ-WS-2** — Workspace creation MUST require a branch name (the
  worktree branch); no mode that omits it.
- **REQ-WS-3** — The add-workspace UI MUST NOT present a workspace-mode
  selector; the `enable_in_place_workspaces` / `enable_clone_workspaces`
  flags and their settings toggles MUST be removed.
- **REQ-WS-4** — `WorkspaceInitializationStrategy` MUST be reduced to
  worktree-only (the `IN_PLACE` and `CLONE` enum values and their
  `clone_strategy` / in-place code paths removed). Legacy rows of other
  strategies MUST NOT crash the app, but need not be runnable.

### Local backend only (REQ-BACKEND)
- **REQ-BACKEND-1** — The app MUST run the backend only on the local
  host alongside the UI. The custom-backend-command mechanism
  (`SETTINGS_CUSTOM_BACKEND_COMMAND`, `SETTINGS_BACKEND_READINESS_TIMEOUT`,
  Electron `SPAWN_CUSTOM_BACKEND_COMMAND`) MUST be removed.
- **REQ-BACKEND-2** — The "advanced" settings controls for custom
  backend MUST be removed.
- **REQ-BACKEND-3** — Runtime container/remote tooling
  (`container/recipes/docker/`, container backend dockerfiles, download
  scripts) MUST be removed insofar as they support running the product
  backend remotely. (Build/CI infra is out of scope — see Non-Goals.)

### Agents (REQ-AGENT)
- **REQ-AGENT-1** — The app MUST support **plain** terminal agents
  (`TerminalAgentConfig`) and **registered** terminal agents
  (`RegisteredTerminalAgentConfig`) only.
- **REQ-AGENT-2** — Registered terminal agents MUST continue to load
  from `~/.sculptor/terminal_agents/*.toml`.
- **REQ-AGENT-3** — The app MUST ship a bundled default `claude`
  terminal-agent registration so creating an agent launches `claude`
  with no user setup, and MUST default new-agent creation to it.
- **REQ-AGENT-4** — The rich Claude integration
  (`ClaudeCodeSDKAgentConfig`, `ClaudeCodeHarness`, agent wrapper,
  `claude_state`, MCP sculptor server tools) and the Pi integration
  (entire `sculptor/agents/pi_agent/`, `fake_pi`, `real_pi`,
  `enable_pi_agent`) MUST be removed. The `HelloAgent` test double MUST
  be removed.
- **REQ-AGENT-5** — `AgentTypeName` MUST be reduced to the
  terminal/registered set; `CLAUDE` and `PI` values and their dispatch
  arms MUST be removed. Legacy agent rows MUST NOT crash the app.

### Rich-chat surface (REQ-CHAT)
- **REQ-CHAT-1** — All rich-chat-only UI MUST be removed: the
  `chat-alpha/` render tree, `ChatInput` and its plan-mode/effort/
  fast-mode/model selectors, file attachments, queued-message edit/
  undo, chat search/navigation, entity @-mentions, and the
  ask-user-question / exit-plan-mode interactive blocks.
- **REQ-CHAT-2** — The `/btw`, `/clear`, and `/copy` pseudo-skills and
  the `btw_service` backend (and `/btw` endpoint) MUST be removed.
- **REQ-CHAT-3** — Backend chat state/message-conversion code that
  exists only to serve the rich chat UI MUST be removed; terminal
  agents MUST keep working via the PTY/terminal path.

### Telemetry & reporting (REQ-TEL)
- **REQ-TEL-1** — All telemetry/analytics (PostHog) MUST be removed:
  initialization, capture sites, `Telemetry.ts`/`Analytics.ts`, tokens
  and config, and the consent settings/flags.
- **REQ-TEL-2** — All crash/error reporting and session replay (Sentry)
  MUST be removed (`instrument.ts`, DSN config, `beforeSend`).
- **REQ-TEL-3** — The "Report a problem" flow MUST be removed entirely:
  the popover, the S3 diagnostics upload (`upload_diagnostics.py`,
  `/api/v1/upload-diagnostics`), and the telemetry settings/privacy
  section. No in-app diagnostics export replaces it.
- **REQ-TEL-4** — After removal, the app MUST make no outbound network
  calls except to GitHub (PR status) and the Anthropic API (via the
  user's `claude`).

### Auto-update (REQ-UPD)
- **REQ-UPD-1** — The auto-update manifest check and installer
  (`autoUpdater.ts`, `useInstallUpdate`, the 30-minute poll) MUST be
  removed. Users update manually.

### Dependency management (REQ-DEP)
- **REQ-DEP-1** — The dependency-management service and managed-binary
  download/install/auth machinery (`dependency_management_service.py`,
  `managed_tools.py`, `BinaryMode`, version-range checks) MUST be
  removed. The app MUST NOT install or manage `claude`, `git`, or
  runtimes.
- **REQ-DEP-2** — The dependencies settings section and onboarding
  installation step MUST be removed. `DependencyPaths` config MUST be
  reduced to (at most) plain user-supplied paths if still needed to
  locate `claude`/`git`, with no managed mode.

### Onboarding (REQ-ONB)
- **REQ-ONB-1** — First run MUST present a single read-only screen that
  checks `claude` and `git` are on `PATH` and then enters the app.
- **REQ-ONB-2** — If a required tool is missing, the screen MUST say so
  clearly and point to install instructions; it MUST NOT attempt to
  install anything. Email confirmation and telemetry consent MUST be
  removed from onboarding.

### Theme (REQ-THEME)
- **REQ-THEME-1** — The theme builder MUST be removed: the settings
  section, `themeBuilder` atoms/storage, color/font/radius/scaling
  pickers, hex overrides, and supporting `common/theme/` machinery used
  only by the builder.
- **REQ-THEME-2** — A simple light / dark / system appearance toggle
  MUST survive in settings, no longer sourced from the theme builder.

### Panels (REQ-PANEL)
- **REQ-PANEL-1** — Panels MUST occupy fixed positions; drag-to-reorder
  and zone reassignment (dnd-kit usage in `DockingLayout`) MUST be
  removed, along with the dnd-kit dependencies if otherwise unused.
- **REQ-PANEL-2** — Each panel MUST be individually toggleable on/off.
- **REQ-PANEL-3** — Resize handles/splits MUST remain so users can
  adjust the size of visible regions.

### Experimental (REQ-EXP)
- **REQ-EXP-1** — The experimental settings section and all
  experimental flags MUST be removed: `enable_review_all`,
  `enable_entity_mentions`, `enable_rich_markdown_rendering`,
  `is_always_interrupt_and_send`, `is_panel_layout_per_workspace`,
  `enable_frontend_plugins` (and the frontend plugins system /
  `PanelRegistryProvider` plugin path), plus the already-listed
  workspace/agent experimental flags.

### Core (preserved) (REQ-CORE)
- **REQ-CORE-1** — Worktree workspace management with multiple agents
  per workspace MUST remain fully functional.
- **REQ-CORE-2** — The workflow skills (`/sculptor-workflow:*` and the
  repo's other Claude Code skills) MUST keep working when run inside a
  terminal agent.
- **REQ-CORE-3** — PR-status tracking and the CI Babysitter MUST remain
  fully functional and unchanged in behavior.
- **REQ-CORE-4** — Local git operations, the diff/file viewer, and the
  terminal panel MUST remain functional.

## Non-Goals

- Removing or weakening the core: worktree workspaces, multi-agent
  per workspace, workflow skills, PR-status tracking, CI Babysitter.
- Migrating or preserving access to legacy workspace/agent types
  (explicit clean break).
- Keeping any in-app diagnostics/bug-report export (removed entirely).
- Reworking the build/release CI pipeline or developer-only
  `.devcontainer` setup (this effort targets the shipped product's
  runtime surface, not how Sculptor itself is built/tested).
- Redesigning the surviving UI — this is a removal/simplification
  effort, not a visual redesign.

## Open Questions

- Does `DependencyPaths` (or an equivalent) need to survive in any form
  so the backend can locate a non-`PATH` `claude`/`git`, or is `PATH`
  resolution sufficient?
- After the rich-chat removal, do any surviving surfaces (e.g. the
  workflow "Plan"/"AskUserQuestion" steps) still rely on the sculptor
  MCP server, or do they fall back cleanly to Claude Code's built-ins
  in terminal mode? (Exploration suggests fallback, to be confirmed.)
- Should the `sculpt` CLI's `agent create` lose its `--type claude/pi`
  options entirely, or keep terminal/registered only (assumed: keep
  terminal-only)?
