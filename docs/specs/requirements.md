# Sculptor — Requirements

This document specifies the product's measurable targets, limits, compatibility bars, data and
integration contracts, and cross-cutting guarantees as they exist today.

## How to read this document

This is the requirements leg of the specification set. `SPEC.md` describes *what the product is and
how each feature behaves*; this document pins the **measurable and contractual** facts that prose
deliberately leaves out — numeric targets, version/platform bars, persistence and migration
guarantees, integration contracts, and where the product is intentionally configurable or currently
unspecified.

| Document | Answers | Layer |
|---|---|---|
| `SPEC.md` | *What is the product, and how does each feature behave?* | Functional behavior, in prose |
| `scenarios.md` | *What exactly happens on screen, action by action?* (Given/When/Then) | UI-level acceptance |
| `scenario_coverage.md` | *Which test demonstrates each scenario?* | Coverage / traceability to tests |
| **`requirements.md`** (this doc) | *What measurable targets, limits, and contracts does the product meet?* | Requirements |

**This document does not restate functional behavior.** Where a requirement is "behave as described,"
it points at the spec section and scenario area rather than re-deriving the behavior (which would
duplicate and drift). What it adds is everything the descriptive spec intentionally omits.

### Conventions

- **Requirement IDs** are stable (`REQ-<AREA>-NNN`) so tests, tickets, and reviews can cite them.
  Areas: `FUNC` (functional), `NFR` (non-functional, measurable), `COMPAT` (platform/deps),
  `DATA` (persistence/migration), `INT` (external integrations), `SEC` (security/privacy/telemetry).
- **RFC 2119 keywords**, scoped to the product: **MUST** = a guarantee the product always upholds;
  **SHOULD** = the product's default/expected behavior, with deliberate or configurable exceptions;
  **MAY** = optional or user-configurable.
- **Criticality** — how central a capability is to the product: **Core**, **Standard**, **Optional**.
- **Source values** are quoted from the current implementation with repo-relative `path:line`
  citations, so each number in this doc is verifiable. A requirement tagged **[Unspecified]** is one
  the product does **not** currently pin down — these are real gaps in the specification, collected in
  §7 (Open questions).
- Citations use repo-relative paths; line numbers are as of this writing and may drift — treat the
  symbol/constant name as the durable reference.

---

## 1. Functional requirements

The functional behavior lives in `SPEC.md` §7–§8 and is verified, action-by-action, by `scenarios.md`.
Rather than copy it, this section indexes the product's capabilities with a criticality rating and
pointers to their spec/scenario home.

| ID | Capability | Spec | Scenarios | Criticality |
|---|---|---|---|---|
| REQ-FUNC-001 | Onboarding & connecting a repo (PATH check for `claude` & `git`, repo add/init) | §7.1 | `ONB`, `ADDREPO` | Core |
| REQ-FUNC-002 | Workspaces: create (worktree), banner, setup command, lifecycle, delete | §7.2 | `ADDWS`, `WS` | Core |
| REQ-FUNC-005 | Terminal agents: plain **Terminal** (bare shell) and **registered** terminal agents (e.g. "Claude CLI"), driven in a PTY | §7.3 | `WS` | Core |
| REQ-FUNC-006 | Multiple agents per workspace: tabs, status dots, create/rename/reorder/delete, peek | §7.4 | `WS` | Core |
| REQ-FUNC-007 | Changes: Browse/Changes/Commits, diff view, scope picker, discard, commit | §7.5 | `PANEL` | Core |
| REQ-FUNC-008 | Pull/Merge requests: create, status dots, detail dropdown, retarget, CI babysitter toggle | §7.6 | `WS` | Core |
| REQ-FUNC-009 | Built-in workspace terminal(s) | §7.7 | `PANEL` | Standard |
| REQ-FUNC-010 | Skills & workflows: searchable library panel, `sculptor-workflow` pipeline, `fix-bug`, `setup-repo` (run as Claude Code skills inside a terminal agent) | §7.8 | `SKILL`, `CMDP` | Standard |
| REQ-FUNC-011 | Command palette & navigation: tabs, Cmd+K / Cmd+P, bottom bar, focus/zen mode, version popover | §7.9 | `SHELL`, `CMDP`, `HELP` | Core |
| REQ-FUNC-012 | Settings (the 8 sections: General/Appearance, Keybindings, Repositories, Git, CI, File Browser, Environment Variables, Actions) | §7.10 | `SET` | Core |
| REQ-FUNC-013 | Actions; path autocomplete in the add-repo path field | §7.11 | `ACT` | Optional |
| REQ-FUNC-015 | `sculpt` CLI: full command surface, `--json`, env-var defaults, cross-surface visibility | §8 | (CLI-level, see §5.4) | Standard |

- **REQ-FUNC-100 (MUST).** Every behavior enumerated in `scenarios.md` is a product requirement; that
  corpus — not the table above — is the exhaustive functional contract, and `scenario_coverage.md`
  measures how well each behavior is demonstrated by an automated test. The table only rates
  criticality.
- **REQ-FUNC-101 (MUST).** **Cross-surface consistency.** A Workspace or Agent created via `sculpt`
  MUST appear in the GUI, and vice versa, because both surfaces are clients of one local backend over
  one persisted store (`SPEC.md` §5, §8). _This is `SPEC.md` Open Issue #3 — it has no §9 guarantee
  there today; this requirement is its home._

---

## 2. Non-functional requirements (measurable)

`SPEC.md` §9 states the cross-cutting guarantees qualitatively ("the UI stays live," "durable,"
"make progress in parallel"). This section attaches the **measurable bars** the product holds to,
and flags the targets it does not currently define.

### 2.1 Responsiveness & live updates (→ SPEC §9.4)

- **REQ-NFR-001 (MUST).** Agent output, status changes, and file-change indicators appear in the UI
  without manual refresh, driven by the live update stream (full snapshot on connect, then deltas).
- **REQ-NFR-002 (SHOULD).** Default in-flight request timeout is **10 s**
  (`sculptor/frontend/src/common/state/requestTracking.ts`); a request exceeding it surfaces an error
  rather than hanging.
- **REQ-NFR-003 (SHOULD).** UI debounce/throttle budgets that shape perceived responsiveness:
  - in-file (diff) search: **150 ms** (`diffPanel/useInFileSearch.ts`, `MUTATION_DEBOUNCE_MS`)
  - branch-name preview: **250 ms**; branch-name collision check: **300 ms** (`add-workspace/hooks/useBranchNamePreview.ts`)
- **REQ-NFR-004 [Unspecified].** The product defines no explicit end-to-end **streaming latency**
  budget (model token emitted → rendered) or **interaction latency** (click → visible response) target.
  → OPEN-1 (§7).

### 2.2 Concurrency & scale (→ SPEC §9.2)

- **REQ-NFR-010 (MUST).** Many agents across many workspaces run concurrently and make independent
  progress. Agents in the **same** workspace share files with **no locking** — this is documented,
  accepted behavior, not a defect (`SPEC.md` §9.2, §7.4).
- **REQ-NFR-011 (SHOULD).** PR/CI status polling runs a bounded worker pool of **4** with a global
  minimum spacing of **1.5 s** between provider API calls across workers, so polling cannot stampede a
  provider (`sculptor/sculptor/web/pr_polling_service.py`).
- **REQ-NFR-012 [Unspecified].** The product enforces **no cap** on max concurrent agents or max
  workspaces (searched; none found). Whether these should be bounded — and the resource model that
  makes "uncapped" safe — is undefined. → OPEN-2 (§7).

### 2.3 Crash recovery & resumption (→ SPEC §9.3)

- **REQ-NFR-020 (MUST).** Quit/crash + reopen restores all workspaces, agents, and their terminal
  session history. A running terminal agent is reattached/resumed where possible.
- **REQ-NFR-021 (MUST).** Failures surface visibly (never silent); an errored agent SHOULD offer a
  restore/continue path unless its workspace was deleted.
- **REQ-NFR-022 (SHOULD).** Resumption uses the registered terminal agent's own session
  continuation: the agent reports its session id via `sculpt signal session-id <id>`, and on resume
  Sculptor launches the agent's `resume_command_template` with the captured `{session_id}`
  substituted (`sculptor/sculptor/tasks/handlers/run_terminal_agent/terminal_session.py`,
  `render_terminal_command`). A plain Terminal (bare shell) has no resume template. See REQ-INT-021.

### 2.4 Persistence & durability (→ SPEC §9.5)

- **REQ-NFR-030 (MUST).** Workspaces, agents, full conversation history, and settings persist locally
  and survive both restart and in-place upgrade to a newer app version. (Detailed data requirements:
  §4.)
- **REQ-NFR-031 (SHOULD).** The local DB runs in **WAL** journal mode with a **15 s** busy timeout to
  tolerate concurrent access (`sculptor/sculptor/database/core.py`).

### 2.6 Diff & input limits

- **REQ-NFR-050 (SHOULD).** A diff over **500 lines** is gated behind "Show full diff"
  (`.../diffPanel/LargeDiffGate.tsx`, `LARGE_DIFF_LINE_THRESHOLD`). Binary files and renames/deletes
  show an explanatory banner instead of a diff (`SPEC.md` §7.5).
- **REQ-NFR-051 (SHOULD).** Max single image upload is **20 MB**, restricted to image types
  (`.jpg/.jpeg/.png/.webp/.gif`), in the rich-text editor used to compose an Action's prompt
  (`sculptor/frontend/src/components/FileUploadUtils.ts`, `MAX_FILE_SIZE`).
- **REQ-NFR-053 (MAY).** Default file-browser split ratio is **50/50**; split-vs-unified, wrapping,
  and tab-close behavior are user-configurable (`sculptor/sculptor/config/user_config.py`; `SPEC.md` §7.10).

### 2.7 Polling & freshness defaults

- **REQ-NFR-060 (SHOULD).** PR/CI status polling defaults: interval **30 s**, floor **10 s**;
  closed-workspace multiplier **6×**; merged/closed (terminal) multiplier **10×**; not-ready retry
  **30 s**; provider rate-limit cooldown **60 s** (`sculptor/sculptor/config/user_config.py`,
  `sculptor/sculptor/web/pr_polling_service.py`). Interval and multiplier are user-configurable (`SPEC.md` §7.10).
- **REQ-NFR-061 (SHOULD).** Local workspace/remote-branch polling interval is **3 s**
  (`sculptor/sculptor/web/repo_polling_manager.py`,
  `_WORKSPACE_BRANCH_POLL_SECONDS` / `_WORKSPACE_TARGET_BRANCHES_POLL_SECONDS`).
- **REQ-NFR-062 (SHOULD).** CI babysitter defaults: **off** (`enabled` default `False`), retry cap
  **3** (`retry_cap` default `3`) (`sculptor/sculptor/config/user_config.py`).

---

## 3. Platform & dependency compatibility (→ SPEC §11)

`SPEC.md` §11 names the OS targets; this section pins the versions the product builds, runs, and
depends on.

### 3.1 Build & runtime platforms

- **REQ-COMPAT-001 (MUST).** Sculptor targets **macOS (Apple Silicon / arm64)**; macOS x64 is
  **not** a target (`SPEC.md` §11.1).
- **REQ-COMPAT-002 (SHOULD).** Sculptor targets **Linux x64**; **Linux arm64** is best-effort /
  non-blocking (`SPEC.md` §11.1).
- **REQ-COMPAT-003 [Unspecified].** The supported **minimum macOS version** is not stated as a
  product requirement (Electron 42's own floor applies), and the **minimum Linux glibc** is likewise
  unpinned. → OPEN-5 (§7).

### 3.2 Toolchain / framework baselines

The product is built against the following baselines (informational; relevant to anyone building or
packaging Sculptor):

| Component | Pinned value | Source |
|---|---|---|
| REQ-COMPAT-010 Python | **>=3.14, <3.15** (pinned 3.14) | `pyproject.toml`, `.python-version` |
| REQ-COMPAT-011 Node.js | **24.17.0** | `sculptor/frontend/.nvmrc` |
| REQ-COMPAT-012 Electron | **42.4.1** (Forge **7.11.2**) | `sculptor/frontend/package.json` |
| REQ-COMPAT-013 uv (Python pkg mgr) | **>=0.11.22** | `pyproject.toml` |
| REQ-COMPAT-014 TypeScript / React / Jotai / Radix Themes / Vite | **6.0 / 19.2 / 2.20 / 3.3 / 6.4** | `sculptor/frontend/package.json` |

### 3.3 Required external binaries

- **REQ-COMPAT-020 (MUST).** **Claude CLI** is required and is **user-installed and PATH-resolved**:
  Sculptor locates it via `shutil.which("claude")` (falling back to a bare `claude` invocation) and
  does **not** install, manage, or version-check it — there is no managed-binary install and no
  compatibility-window enforcement (`sculptor/sculptor/tasks/handlers/run_terminal_agent/v1.py`;
  onboarding PATH check, `SPEC.md` §7.1). A missing `claude` is reported by the onboarding screen
  (REQ-INT-023).
- **REQ-COMPAT-021 [Unspecified].** **Git** is required and is **PATH-resolved with no
  minimum-version check** (`shutil.which("git")`; no version gate found). The minimum supported git
  version is undefined (worktree support is the relevant capability). → OPEN-6 (§7).
- **REQ-COMPAT-023 (MUST, conditional).** The PR/MR surface requires the matching provider CLI —
  **`gh`** (GitHub) or **`glab`** (GitLab) — present and authenticated; absence/non-auth degrades to a
  documented error state, never a crash (§5.1, `SPEC.md` §7.6).

---

## 4. Data persistence, durability & migration (→ SPEC §9.5, §10.8)

`SPEC.md` quarantines SQLite/Alembic as implementation. They are first-class here because the product
makes durability and upgrade-survival guarantees (§9.5) that rest directly on this layer.

### 4.1 On-disk layout & store

- **REQ-DATA-001 (MUST).** User data lives in a single **Sculptor folder**: `~/.sculptor` (stable),
  `~/.dev-sculptor` (dev builds), or `<repo>/.dev_sculptor` (running from source), overridable via the
  `SCULPTOR_FOLDER` env var; the workspaces path is separately overridable via
  `SCULPTOR_WORKSPACES_FOLDER` (`sculptor/sculptor/utils/build.py`).
- **REQ-DATA-002 (MUST).** Within it: `internal/database.db` (SQLite), `internal/config.toml`
  (settings), `internal/logs/`, `internal/uploads/`, `internal/artifacts/`, `internal/sculpt-bin/`,
  and `workspaces/` (`sculptor/sculptor/utils/build.py`, `get_internal_folder` /
  `get_workspaces_folder`; `sculptor/sculptor/config/settings.py`). Startup bootstraps the
  `internal/` and `workspaces/` subdirectories idempotently
  (`sculptor/sculptor/utils/migration.py`, `ensure_sculptor_folder_ready`).
- **REQ-DATA-003 (MUST).** The store keeps a **single mutable table per entity**: writes are
  **UPSERTs** and monotonic fields are latched with `MAX()` so a value never regresses under a
  concurrent stale write (`_upsert_model` with `func.max(...)` latching in
  `sculptor/sculptor/services/data_model_service/sql_implementation.py`; the single mutable table per
  entity is created by `create_tables` in `sculptor/sculptor/database/automanaged.py`; WAL and
  migration setup in `sculptor/sculptor/database/core.py`). The externally-observable guarantee is
  that current state is read cheaply and persists durably.
- **REQ-DATA-004 (MUST).** Persisted entities: **UserSettings, Project, Workspace, Task,
  SavedAgentMessage, Notification** (`sculptor/sculptor/database/models.py`). _("Task" is the vestigial internal
  primitive backing an Agent — see `SPEC.md` §6; it is a storage concern, not a product concept.)_

### 4.2 Durability & upgrade survival

- **REQ-DATA-010 (MUST).** Settings, the database (projects/workspaces/agent history/messages),
  workspace directories, logs, and uploads survive an in-place app upgrade (covered by
  `test_migration.py`; `SPEC.md` §9.5).
- **REQ-DATA-011 (MUST).** Alembic migrations run automatically at startup, upgrading the DB to head;
  a detected **downgrade** (DB newer than app) fails with a clear, actionable error rather than
  corrupting data (`sculptor/sculptor/database/core.py`). Migrations are **forward-only** in practice
  (downgrade stubs are mostly no-ops).
- **REQ-DATA-012 (MUST).** The schema is squashed to **one initial migration**
  (`alembic/versions/4ddee12c1e07_initial_schema.py`). Every Alembic migration ships a **companion
  version test** under `sculptor/sculptor/database/alembic/version_tests/` (seed → migrate → verify),
  enforced by `test_every_migration_has_a_test_fixture()` (`sculptor/sculptor/database/README.md`) —
  the process guarantee that lets the schema evolve safely as future migrations are added.
- **REQ-DATA-013 (MUST).** Versioned JSON columns (e.g. `Task.input_data`, `SavedAgentMessage.message`,
  which store unions of agent-message/input variants) are guarded by a **frozen Pydantic-schema
  snapshot** (`alembic/frozen_pydantic_schemas.json`); a model change that isn't reflected fails a test
  until a migration is authored or the change is confirmed back-compatible (`alembic/utils.py`,
  `get_frozen_database_model_nested_json_schemas`).

### 4.3 Backward compatibility & folder migration

- **REQ-DATA-020 [Unspecified].** The product does not state a **back-compat horizon** — how far back
  older data folders / DB versions are guaranteed readable. The current posture is a **clean break**
  (no prior data folder is migrated or relocated), but whether any prior schema is guaranteed
  readable is not pinned. → OPEN-7 (§7).
- **REQ-DATA-022 (SHOULD).** Startup **bootstraps** the data folder rather than migrating it: it
  creates the `internal/` and `workspaces/` subdirectories if missing and is otherwise a no-op
  (`sculptor/sculptor/utils/migration.py`, `ensure_sculptor_folder_ready`). There is no
  folder-relocation/migration helper. Config loading tolerates a malformed `custom_actions` value by
  silently dropping it via a model validator rather than crashing
  (`sculptor/sculptor/config/user_config.py`, `_sanitize_custom_actions`).

---

## 5. External integration contracts (→ SPEC §5, §6, §7.6, §8)

Each external boundary is a contract the product upholds, **including its failure modes** — the spec
describes the happy path and the error *surfaces*; this section pins the contract and the degradation
rules behind them.

### 5.1 Git host providers

- **REQ-INT-001 (MUST).** The provider is detected from the `origin` remote hostname (parsing SSH and
  HTTP(S) forms): hostname containing **"github"** → GitHub via **`gh`**; containing **"gitlab"** →
  GitLab via **`glab`**. Any other host has **no** PR/MR surface and no target-branch concept
  (`SPEC.md` §7.6; `sculptor/sculptor/web/pr_polling_service.py`).
- **REQ-INT-002 (MUST).** Operations performed via the provider CLI: **list** requests for a branch,
  **view** a request's status-check/pipeline rollup, **reviews/approvals**, and **unresolved
  comments/discussions**; **push** the branch and **open** a request; poll status thereafter. (GitHub:
  `gh pr list/view`; GitLab: `glab mr list/view` + `glab api …/approvals` and `…/discussions`.)
- **REQ-INT-003 (MUST).** The failure taxonomy is classified and surfaced distinctly (not collapsed
  into "error"): the CLI status classifier yields **not_authenticated**, **no_access**,
  **rate_limited** (→ 60 s host cooldown), **network_error** (permanent), and **transient** (retried
  once); a missing provider binary is surfaced separately as a **cli_missing** error category on the
  PR/MR status (`sculptor/sculptor/web/cli_status_utils.py`, `pr_polling_service.py`). Each maps to the actionable
  warning/info button states in `SPEC.md` §7.6.

### 5.2 Terminal-agent process

- **REQ-INT-021 (MUST).** A terminal agent runs the user's CLI (e.g. `claude`) **in a PTY** — there
  is no message stream, JSONL protocol, or MCP bridge. The agent is started by running its
  `launch_command` and is resumed by running its `resume_command_template` with the captured
  `{session_id}` substituted (REQ-NFR-022, REQ-INT-030/031). Workflow skills' interactive steps
  (plan, ask-user-question) render in the terminal via Claude Code's built-in tools, not as in-app
  blocks. Sculptor learns the agent's busy/idle/waiting state and session id only from the agent
  calling `sculpt signal` (REQ-FUNC-005, `SPEC.md` §7.3).
- **REQ-INT-023 (MUST).** A missing required binary (`claude` or `git`, resolved via PATH) is
  surfaced by the onboarding PATH-check screen — it reports which tool is missing and links to
  install instructions rather than failing silently or attempting an install (`SPEC.md` §7.1).

### 5.3 Terminal-agent registration

- **REQ-INT-030 (SHOULD).** Registered terminal agents are TOML files under
  `<sculptor_folder>/terminal_agents/`, one per agent, keyed by **`registration_id` = filename stem**
  (must match `[a-z0-9][a-z0-9_-]*`), declaring **`display_name`** (required), **`launch_command`**
  (required), **`resume_command_template`** (optional), **`accepts_automated_prompts`** (optional,
  default false) (`sculptor/sculptor/services/terminal_agent_registry/registry.py`).
- **REQ-INT-031 (SHOULD).** Placeholders are substituted by literal replacement (not `.format()`):
  `{sculptor_directory}` and `{terminal_agents_directory}` in `launch_command`; those plus **at most
  one** `{session_id}` in `resume_command_template`; unknown placeholders are rejected. The directory
  is **re-read on demand** (no restart needed to add an agent), and launch params are **stamped onto the
  agent at creation** so it survives later edits/deletion of the file (`SPEC.md` §7.3; `registry.py`).

### 5.4 `sculpt` CLI ↔ backend

- **REQ-INT-040 (SHOULD).** `sculpt` reaches the local backend at `http://localhost:<port>` where port
  = **`SCULPT_API_PORT`** (default **5050**), or an explicit `--base-url`; it fetches a session token
  and sends it as the `x-session-token` header. A connection failure exits with a clear "could not
  connect to Sculptor server" message (`tools/sculpt/sculpt/auth.py`).
- **REQ-INT-041 (SHOULD).** The CLI client is **generated** from the backend OpenAPI schema (same
  contract as the GUI client) — see `SPEC.md` §10.7 and the Appendix. Env-var defaults
  (`SCULPT_WORKSPACE_ID`, `SCULPT_AGENT_ID`, `SCULPT_PROJECT_ID`) and short-prefix IDs work as in
  `SPEC.md` §8.

### 5.5 Environment-variable injection

- **REQ-INT-050 (SHOULD).** Sculptor loads a **global `~/.sculptor/.env`** and a **per-repo
  `.sculptor/.env`**, with **project values overriding global**, injecting them into agent/terminal
  environments; the format supports `KEY=value`, `export KEY=value`, quotes, and `#` comments
  (`sculptor/sculptor/services/workspace_service/environment_manager/env_file_parser.py`; `SPEC.md` §7.10). An
  override toggle governs whether these replace pre-existing variables.

---

## 6. Security, privacy & telemetry (→ SPEC §9.1, §9.6)

- **REQ-SEC-001 (MUST).** **Trust boundary.** An agent works only inside its isolated worktree
  workspace copy and MAY run real shell commands there; **nothing is pushed to a remote and no PR/MR
  is opened without an explicit user action** (`SPEC.md` §9.1). This boundary holds for both the GUI
  and `sculpt`.
- **REQ-SEC-002 (MUST).** **Local-first, single-user.** Code and secrets stay on the user's machine;
  Imbue does not store repositories or train on user code (`SPEC.md` §9.6). Secrets supplied via
  environment / `.env` files are injected into agent environments and not persisted to config
  (REQ-INT-050).
- **REQ-SEC-003 (MUST).** **No auto-update.** Sculptor performs no update check, manifest poll, or
  outbound update call; users update manually (`SPEC.md` §11.3). _(The CI/release pipeline — workflow
  definitions — is not present in this repository tree; the macOS signing/notarization config is
  (`sculptor/frontend/forge.config.ts`), while any signing credentials live with the release process,
  `SPEC.md` §11.2, not the product runtime.)_
- **REQ-SEC-004 (MUST).** **No telemetry, analytics, crash reporting, session replay, or diagnostics
  upload exists** — there is no Sentry, PostHog, "Report a problem" flow, or in-app diagnostics
  export. The only outbound network calls the product makes are to the **git host** (`gh`/`glab` PR
  status, REQ-INT-001/002) and to the **Anthropic API**, the latter only via the user's `claude`
  (`SPEC.md` §9.6).

---

## 7. Open questions & unspecified behaviors

Consolidated from the **[Unspecified]** tags above — points where the product currently pins **no**
value, so this specification is genuinely incomplete until each is decided and the relevant requirement
updated.

| ID | Open question | Requirement |
|---|---|---|
| OPEN-1 | Streaming & interaction **latency budgets** + how they're measured | REQ-NFR-004 |
| OPEN-2 | **Concurrency caps** (max agents / workspaces), or a documented "safe uncapped" resource model | REQ-NFR-012 |
| OPEN-5 | Supported **minimum macOS version** and **Linux glibc** floor | REQ-COMPAT-003 |
| OPEN-6 | **Minimum git version** | REQ-COMPAT-021 |
| OPEN-7 | **Data back-compat horizon** — which prior `~/.sculptor` DB/folder versions are guaranteed readable | REQ-DATA-020 |

These complement, and do not duplicate, `SPEC.md` §12 (which tracks the §9-product-vs-§10-substrate
line); resolving §12 may add or retire requirements here.

---

## Appendix — relationship to the test & quality substrate

The verification machinery the product depends on (the fake registered terminal agent for
deterministic agent behavior — `sculptor/sculptor/testing/fake_terminal_agent*.py` — the Playwright
POM + `ElementIDs` test-id contract, the fidelity tiers, ratchets, contract generation, migration
version tests, diagnosability) is documented in `SPEC.md` §10 and is **not** re-specified here — but note that
several requirements above are only *checkable* because that substrate exists: REQ-FUNC-100 (scenarios
as acceptance), REQ-DATA-012/013 (migration + frozen-schema tests), REQ-INT-041 / REQ-COMPAT-014
(generated cross-surface clients). Treat `SPEC.md` §10 as the binding companion to this document.
