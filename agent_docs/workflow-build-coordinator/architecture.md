# Workflow Build Coordinator — Architecture

## Executive Summary

Replace the agentic Build coordinator in the Sculptor workflow pipeline
(Spec → Architect → Plan → Build → Review) with **coordinator**, a
deterministic Python program that parses the plan into a task DAG and
drives fresh-context worker agents through it — one worker per task
attempt, with mechanical, agentic, and human gates deciding success.
Today an LLM Build agent walks the plan in one ever-growing context and
stalls on long plans; after this lands, the coordinator runs as a registered
terminal agent in a Sculptor tab (and equally standalone outside
Sculptor), executes the DAG to completion, records durable execution
state on disk, and (in later increments) orchestrates the entire
pipeline as a graph.

## Current Architecture

```
 Sculptor workspace (one shared code/ checkout, N agent tabs)
 ┌────────────────────────────────────────────────────────────┐
 │  Spec tab ──spawn──▶ Architect tab ──spawn──▶ Plan tab     │
 │   (Q&A)               (Q&A)                    (Q&A)       │
 │                                                  │spawn    │
 │                                                  ▼         │
 │                                             Build tab      │
 │                                     (ONE agent, walks all  │
 │                                      task files in order)  │
 │                                                  │spawn    │
 │                                                  ▼         │
 │                                             Review tab     │
 └────────────────────────────────────────────────────────────┘
   every arrow = an LLM remembering to run `sculpt agent create…`
```

What exists today, and what this feature touches:

- **Workflow skills** live in `sculptor/sculptor-workflow/skills/`
  (spec, mock, architect, plan, build, review, fix-bug, setup-repo),
  shipped as a Claude Code plugin via `--plugin-dir` in the
  terminal-agent launch command. Each design skill runs a Q&A loop and
  at finalize spawns the next agent via the `sculpt` CLI. Every phase
  transition depends on an agent remembering to spawn the next agent.
- **The Build skill** (`skills/build/SKILL.md` +
  `implement_task.md`) is a single LLM agent that reads
  `00_overview.md`, builds a TODO list, and executes every task file
  in one conversation, re-reading `implement_task.md` before each
  task as a discipline defense. On long plans it drifts, worries
  about context, or pauses without finishing. Verification and Review
  spawning are the plan's two mandatory `99_*` tasks — enforced only
  by convention.
- **The Plan skill** (`skills/plan/SKILL.md`) emits a folder of
  human-readable task files plus `00_overview.md`, whose Task Index
  table is the only machine-adjacent structure (a markdown table an
  LLM parses). There is no dependency information — order is implied
  by file naming (`01_02_*`).
- **Terminal-agent registrations**
  (`sculptor/sculptor/services/terminal_agent_registry/registry.py`)
  are one TOML file per registration under
  `<sculptor folder>/terminal_agents/`, with `launch_command`,
  optional `resume_command_template` (with `{session_id}`), and
  `accepts_automated_prompts`. The registration id is the filename
  stem. Placeholders are substituted at render time and unknown
  tokens are rejected at load. The sample registration
  (`samples/terminal_agents/claude-code/claude-code.toml`) launches
  the Claude Code TUI with a `--settings` hooks fragment.
- **`sculpt signal`** (`tools/sculpt/sculpt/commands/signal.py`)
  posts agent state to the backend: `busy`, `idle`, `waiting`
  (waiting-on-input), `files-changed`, and `session-id <id>` for
  resume-after-restart. The sample hooks fragment
  (`claude-code-hooks.json`) wires Claude Code hook events
  (SessionStart / UserPromptSubmit / Stop / Notification /
  PreToolUse / PostToolUse) to these signals — proof that hook-driven
  lifecycle detection works without screen parsing.
- **`tools/sculpt/`** is the precedent for a self-contained Python
  package in `tools/`: own `pyproject.toml`, typer CLI, unit tests
  wired into `just test-unit`, optional pyinstaller packaging.
- **Repo configs** (`.sculptor/code.md`, `.sculptor/testing.md`,
  `.sculptor/docs.md`) are prose read by agents — **not**
  machine-readable. A deterministic coordinator cannot parse them;
  anything the coordinator needs (verification commands, worker choices) must
  be materialized into a machine-readable artifact at plan time.

## Proposed Architecture

Increment 1 (REQ-INC-1) — the build-DAG executor:

```
 Plan tab (LLM, Q&A)                          Sculptor backend
 ┌───────────────────┐                        ┌───────────────┐
 │ writes plan/      │                        │ status, diff, │
 │  00_overview.md   │                        │ resume        │
 │  NN_MM_task.md …  │                        └───────▲───────┘
 │  plan.yaml (DAG)  │                                │ sculpt signal
 └─────────┬─────────┘                                │ (busy/waiting/
           │ finalize: creates coordinator tab        │  files-changed/
           │ launch args "run <plan-dir>"             │  session-id)
           ▼                                          │
 coordinator tab (registered terminal agent, NO LLM)  │
 ┌────────────────────────────────────────────────────┴──────┐
 │  coordinator CLI + Textual TUI dashboard                  │
 │                                                           │
 │  plan.yaml ──▶ DAG ──▶ scheduler (topological,            │
 │                          sequential in increment 1)       │
 │                          │                                │
 │                          ▼        per task attempt        │
 │                 ┌─────────────────────────────┐           │
 │                 │ spawn fresh worker process  │           │
 │                 │ (headless `claude -p`,      │           │
 │                 │  bootstrap prompt at launch,│           │
 │                 │  per-attempt hooks fragment)│           │
 │                 └──────────┬──────────────────┘           │
 │                            │ signals.jsonl (hook events)  │
 │                            │ + process lifecycle          │
 │                            ▼                              │
 │      gates: mechanical (every task) ▶ agentic (per        │
 │             phase by default) ▶ human (opt-in)            │
 │                    │ pass: commit exists, next task       │
 │                    │ fail: kill worker, retry w/ context  │
 │                    │       (2 base + 1 escalated), then   │
 │                    │       mark failed, continue branches │
 │                            ▼                              │
 │      plan/_state/: journal.jsonl (truth) + snapshot +     │
 │      per-attempt run dirs; TUI is a view; resume replays  │
 └───────────────────────────────────────────────────────────┘
```

The coordinator is a self-contained Python package at `tools/coordinator/`
(REQ-PKG-1..2). It has no import dependency on the Sculptor backend or
on `sculpt`; it *discovers* `sculpt` at runtime (REQ-PIPE-4) and, when
present, signals status (REQ-COORD-3). Inside Sculptor it runs as a
registered terminal agent (REQ-COORD-2); outside Sculptor the same CLI
runs in any terminal (`coordinator run <plan-dir>`).

### Delivery phases (REQ-FLOW-1)

Matching the spec's increments, each with its own plan folder,
coordinator run, and review (REQ-FLOW-2):

1. **Increment 1 — build-DAG executor** (REQ-INC-1): everything in
   the diagram above, plus the Plan-skill manifest emission and the
   skill cleanup that rides along (REQ-SKILL-1..2, REQ-SKILL-4). The
   right-sized first increment: it replaces `/build` outright and is
   independently useful.
2. **Increment 2 — pipeline orchestration** (REQ-INC-2): interactive
   nodes (Spec/Mock/Architect/Plan) in the graph, sculpt-tab spawning
   with dynamic discovery, finalize-signal contract (REQ-SKILL-3),
   phase re-entry and graph expansion (REQ-PIPE-1..3, REQ-FLOW-4).
   Review becomes an autonomous node the coordinator runs itself, so the
   post-build review fires automatically outside Sculptor too.
3. **Increment 3 — parallel execution** (REQ-INC-3): concurrent
   independent DAG branches in git worktrees with merge-back
   (REQ-PAR-2).

The node/manifest schema accommodates all three from day one
(REQ-INC-4); increment 1 only executes autonomous build nodes.

## Component Deep Dives

### Coordinator core (DAG engine + scheduler)

Parses `plan.yaml` into a task DAG, validates it (acyclic, all task
files exist, all referenced worker registrations resolvable, gate
policies well-formed), and executes tasks in topological order —
sequentially in increment 1 (REQ-PAR-1), in the shared working tree.
The scheduler is a state machine per task: `pending → running →
gate-checking → passed | failed | waiting-human`, with every
transition appended to the journal before it takes effect elsewhere
(write-ahead discipline, REQ-STATE-1). The scheduler consumes control
intents (pause, retry, skip, approve, abort) from the same journal,
so TUI actions and state changes share one ordered history.

### Worker launcher (per-attempt lifecycle)

Each task attempt spawns one fresh worker process (REQ-COORD-5,
REQ-WORKER-2): a headless Claude Code session (`claude -p`) on pipes,
bootstrap prompt passed at launch, permissions pre-granted
(`--dangerously-skip-permissions` + the skip-disclaimer setting, as
the sample registration does). The coordinator never renders or parses
a worker's screen. Worker PIDs are recorded in the journal so a resumed
coordinator can reap orphans.

Headless workers exit the instant their turn ends, so a worker that
backgrounds work and stops to await a completion notification is
waiting for something that can never arrive. A Stop guard hook vetoes
such a turn and sends the worker back to drain the work in the
foreground; a turn that ends that way regardless fails the attempt
(`stopped-with-pending-background`) rather than passing half-done work
to the gates.

**Worker registrations** are one YAML file per harness+model
combination (e.g. `claude-sonnet.yaml`, `claude-opus.yaml`), each a
command template with placeholders rendered per attempt — the same
idea as terminal-agent registrations, validated the same way
(unknown placeholders rejected at load). Discovery is layered, by
registration name, nearest wins: built-in defaults shipped in the
package (common Claude registrations, so a bare repo works) →
user-level config dir → repo-level `.sculptor/workers/` (checked in,
team-shared). The manifest references registrations by name
(REQ-MODEL-1); adding a harness/model is a new file, not code
(REQ-WORKER-1). Reviewer agents for the agentic gate use the same
registration mechanism — a reviewer is just a worker with a
different prompt.

**Prompt delivery:** the launch argv carries only a short bootstrap
prompt ("read and execute the task at `<task-file>` following the
process at `<process-file>`; retry context, if any, at
`<context-file>`") — the real content lives in files in the attempt
directory. This avoids argv length limits when failure history grows
and keeps every attempt's exact inputs on disk for diagnosis. The
process file is the evolved `implement_task.md` (REQ-SKILL-2),
shipped as data inside the coordinator package and overridable per plan
via a manifest field; it drops all "ask the user" language — workers
never wait on input (REQ-WORKER-6): they either complete and let
gates judge, or their blocked state is a failed attempt.

**Signal channel (decided):** filesystem journal. The coordinator creates a
per-attempt run directory; the generated hooks fragment's commands
append JSON lines (event, timestamp, session id / transcript path
where present) to a `signals.jsonl` file in it. The coordinator polls the
file. No server, crash-safe, portable, and the raw signal log
survives per attempt for diagnosis (REQ-COORD-6). Events mirror what
the sample `claude-code-hooks.json` proves works: session start,
session id and transcript path (from hook stdin JSON), turn end
(Stop), waiting-on-input (Notification / AskUserQuestion PreToolUse).
"Turn ended" only hands off to gates — it is never success by itself
(REQ-WORKER-4); process exit without a completion signal is a failed
attempt (REQ-WORKER-3). Session IDs land in the execution journal
for later inspection or resume of any attempt (REQ-WORKER-5).

**Rate-limit handling (REQ-WORKER-7):** the hooks report the
worker's transcript path; on a failed or stalled attempt the coordinator
inspects the transcript tail (a file, not the screen) for rate-limit
markers. A rate-limited attempt does not burn retry budget: coordinator
enters a paused state, signals `waiting`, and surfaces the resume
time in the TUI.

### Gate runner

Three gate kinds, declared in the manifest (REQ-GATE-4):

- **Mechanical** (REQ-GATE-1): coordinator re-runs verification commands
  and requires a new commit for the task (unless the task declares
  itself no-change). Commands come from the manifest (materialized at
  plan time from `.sculptor/code.md`, which coordinator cannot parse),
  plus per-task checks.
- **Agentic review** (REQ-GATE-2): a fresh reviewer worker — never the
  implementer session — gets the scope's task file(s) and diff,
  returns a pass/fail verdict with findings written to a designated
  verdict file in its attempt directory; findings seed the retry.
- **Human** (REQ-GATE-3): pauses the branch, signals `waiting`,
  presents the diff in the TUI for approval.

**Default policy (decided):** mechanical after every task,
non-negotiable. Agentic review defaults to **phase boundaries** — the
manifest groups tasks into phases, and coordinator inserts a phase-review
node depending on all of the phase's tasks, reviewing the phase's
combined diff. Per-task agentic review is opt-in, set by the Plan
agent when it judges a task especially complex or risky. Human gates
are always opt-in per task or phase. A failed phase-review maps
findings to the offending task(s) and re-opens them as retries with
the findings as seed context.

### Failure / escalation ladder

Gate failure kills the worker and spawns a fresh attempt seeded with
the failure context, up to the per-task retry budget (REQ-FAIL-1).
Budget exhausted → escalated attempt on the configured stronger
registration with full failure history (REQ-FAIL-2). Escalation
fails → task marked failed; independent DAG branches continue; when
nothing runnable remains coordinator signals `waiting` with a
consolidated failure report (REQ-FAIL-3).

**Defaults (decided):** 2 attempts on the task's base registration
(initial + one context-seeded retry), then 1 escalated attempt — at
most three worker sessions per task before it surfaces as failed.
Both numbers and the escalation registration are configurable
plan-wide and overridable per task (REQ-FAIL-4).

### Execution state store

**Location and shape (decided):** `<plan-folder>/_state/`, containing
an append-only JSONL event journal (the source of truth) plus a
derived snapshot for fast load, and the per-attempt run directories
(signals journal, generated hooks fragment, prompt files, captured
worker output). The directory writes its own `.gitignore` (containing
`*`) on creation, so run state never pollutes the repo and no
repo-level gitignore edit is needed. State sits next to the plan it
executes — trivially discoverable on resume, identical inside and
outside Sculptor.

Contents: per-task status, attempt history, worker session IDs and
PIDs (REQ-COORD-6, REQ-WORKER-5), gate results, commits produced
(REQ-STATE-1). A killed coordinator resumes by replaying the journal,
discarding any mid-flight attempt and reaping recorded worker PIDs
(REQ-STATE-2). The TUI renders from this state only (REQ-UX-4).

### TUI dashboard

**Stack (decided):** Python + Textual. Python matches REQ-PKG-1 and
reuses the repo toolchain (`uv`, `ruff`, `pyrefly`, `pytest`,
`just check`/`test-unit`) plus the `tools/sculpt` precedent —
including its pyinstaller packaging path for standalone shipping
(REQ-PKG-2). Textual provides widgets, key bindings, and drill-down
screens, and its Pilot test harness lets the dashboard be unit-tested
in `just test-unit`.

Full-tab dashboard (REQ-UX-1..3): task/DAG view with states and
attempt counts, per-task drill-down (gate findings, attempt history,
session IDs, transcript access), controls (pause, resume, retry,
skip, approve human gate, abort). The TUI expresses controls as
intents appended to the journal, which the scheduler consumes —
keeping the TUI a pure view over the state (REQ-UX-4).

### Sculptor integration

The coordinator ships a terminal-agent registration sample (installed like
`claude-code.toml`): `launch_command` is `coordinator {args}` and
`resume_command_template` runs `coordinator resume {session_id}`.

**Launch-args plumbing (decided):** the terminal-agent contract
gains an `{args}` placeholder. A registration opts in by including
`{args}` in its `launch_command`; `sculpt agent create` (and the
backend create-agent API) accepts caller args for terminal agents,
and the command renderer substitutes them **shell-quoted per
argument** at render time. The Plan skill's finalize creates the
coordinator tab with args `run <plan-dir>`; standalone users type the
identical `coordinator run <plan-dir>` — one CLI contract in both
environments, no typed-prompt timing games
(`accepts_automated_prompts` stays false for the coordinator). Launched with
no args, the coordinator scans the repo's spec location for `plan.yaml`
files with incomplete state and offers a picker.

The coordinator mints a run id per execution, reports it via `sculpt signal
session-id`, and maps it back to the plan's `_state/` dir on resume —
so the terminal-agent resume path (crash/restart scenario,
REQ-STATE-2) reuses Sculptor's existing machinery unchanged.

At runtime the coordinator probes for `sculpt` on PATH plus the
`SCULPT_AGENT_ID` environment (REQ-PIPE-4): if present it signals
`busy` while tasks run, `waiting` on human gates and failure reports,
and `files-changed` after each task commit (REQ-COORD-3); if absent,
all signaling is skipped and behavior is otherwise identical.

At the end of a successful run, the coordinator spawns the Review agent tab
via `sculpt` (Review spawning becomes coordinator code, REQ-SKILL-1),
seeding it exactly as the plan's old `99_02_launch_review.md` task
did. Outside Sculptor, increment 1 prints the equivalent
instructions as a stopgap; in increment 2 Review becomes an
autonomous node in the pipeline graph (REQ-PIPE-2 classes Review
with the headless workers, not the interactive nodes), so the coordinator
runs it itself — automatically in both environments — and the
stopgap disappears.

### Plan manifest (emitted by the Plan skill)

**Format (decided):** YAML — `plan.yaml` in the plan folder. YAML is
the idiomatic format for DAG/CI-style configs and comfortable to
hand-edit (retry overrides, gate tweaks); the `pyyaml` dependency
stays inside the self-contained coordinator package (REQ-PKG-2).

The Plan skill emits the manifest alongside the unchanged
human-readable task files (REQ-PLAN-1). The coordinator parses only the
manifest; humans and workers read only the task files. The schema
accommodates all increments' node kinds from day one (REQ-INC-4) —
see Data Model Changes.

## Data Model Changes

One small Sculptor-side change: the terminal-agent registration
schema admits an `{args}` placeholder in `launch_command` (validated
like the existing placeholders — at most once, rejected elsewhere),
and the create-agent API + `sculpt agent create` accept optional
launch args for registered terminal agents, substituted shell-quoted
at command-render time. No database migration — the args live on the
agent's config like the rest of the registration snapshot.

Otherwise, three new on-disk schemas, all owned by the coordinator:

**`plan.yaml`** (written by the Plan skill, REQ-PLAN-1..2):

```yaml
version: 1
defaults:
  worker: claude-sonnet          # registration name
  escalation_worker: claude-opus
  attempts: 2                    # base attempts before escalation
  verification:                  # materialized from .sculptor/code.md
    - just format
    - just check
    - just test-unit
phases:
  - id: 1
    name: Core executor
    review: agentic              # phase-boundary default
    tasks:
      - id: "1.2"
        file: 01_02_manifest_parser.md
        deps: ["1.1"]
        worker: claude-opus      # optional override (REQ-MODEL-1)
        gates: [mechanical, agentic]   # optional per-task override
        attempts: 3              # optional override (REQ-FAIL-4)
        no_change: false         # true for tasks expected to not commit
```

Node kinds beyond build tasks (interactive nodes, review nodes) are
part of the schema's `kind` vocabulary from day one but only emitted/
executed from increment 2 (REQ-INC-4).

**Execution journal** (`_state/journal.jsonl`): append-only typed
events — run-started, task-state-changed, attempt-started (worker
registration, PID), signal-observed (session id, transcript path),
gate-started/gate-result (findings), commit-recorded, control-intent
(pause/retry/skip/approve/abort/extend), run-paused (rate limit). Snapshot
(`_state/state.json`) is derived and disposable.

**Worker registration** (`.sculptor/workers/<name>.yaml`, layered
with user-level and built-in copies): display name, launch command
template with placeholders (`{prompt}`, `{settings_file}`,
`{attempt_dir}`, `{cwd}`), and optional environment. Unknown
placeholders rejected at load, mirroring the terminal-agent registry.

## Migration Strategy

No data migration. The `/build` agent skill is deleted in increment 1
(REQ-SKILL-2) — no fallback path; the Plan skill's finalize spawns a
coordinator tab instead of a Build agent. `implement_task.md` survives,
evolved, as the per-task process document shipped inside the coordinator package.
Plans authored before the manifest existed are not supported; re-run
`/plan` (or hand-write a `plan.yaml`) for in-flight features. The
`99_01_verify_all_tests` / `99_02_launch_review` mandatory tasks
disappear from new plans — final verification is a built-in coordinator
gate and Review spawning is coordinator code (REQ-SKILL-1).

## Files to Modify / Create / Delete

Create:

- `tools/coordinator/pyproject.toml` — package metadata (pyyaml, textual,
  typer), console script, pytest config; mirrors `tools/sculpt`.
- `tools/coordinator/coordinator/` — the package: CLI entry (`run`, `resume`,
  `status`), manifest parsing/validation, DAG + scheduler, journal
  state store, worker registration loading + PTY launcher + hooks
  fragment generation, gate runner (mechanical/agentic/human),
  escalation ladder, transcript-based rate-limit detection, sculpt
  discovery/signaling, Textual dashboard, built-in worker
  registrations and the evolved per-task process doc as package data.
- `tools/coordinator/tests/` — unit tests (see Testing Strategy).
- `samples/terminal_agents/coordinator/coordinator.toml` — Sculptor
  registration sample (launch + resume commands,
  `accepts_automated_prompts = false` — launch args carry everything;
  nothing types into the Textual app's terminal).
- `sculptor/sculptor-workflow/skills/_shared/qa-ritual.md` — the
  deduplicated Q&A-ritual reference (REQ-SKILL-4).
- `.sculptor/workers/` — this repo's checked-in worker registrations.

Modify:

- `sculptor/sculptor-workflow/skills/plan/SKILL.md` — emit
  `plan.yaml` (with phases, deps, gate policy, verification commands
  materialized from `.sculptor/code.md`), drop the two mandatory
  `99_*` tasks, finalize spawns the coordinator tab and sends
  `run <plan-dir>` (REQ-SKILL-1).
- `sculptor/sculptor-workflow/skills/{spec,mock,architect,plan,review,fix-bug}/SKILL.md`
  — point Q&A boilerplate at the shared reference; refresh stale
  context-management guidance in the same edits (REQ-SKILL-4).
- `sculptor/sculptor-workflow/skills/review/SKILL.md` — accept
  seeding from coordinator (unchanged marker format).
- `justfile` — wire `tools/coordinator` into `test-unit` / `check` the
  same way `tools/sculpt` is wired.
- Backend bundled-registration installer
  (`sculptor/sculptor/services/terminal_agent_registry/bundled.py`)
  — install the coordinator registration alongside `claude-code`.
- `sculptor/sculptor/services/terminal_agent_registry/registry.py` —
  admit the `{args}` placeholder in `launch_command` (opt-in, at most
  once).
- The terminal-session command renderer
  (`sculptor/sculptor/tasks/handlers/run_terminal_agent/terminal_session.py`)
  and the create-agent API path (`sculptor/sculptor/web/app.py`) —
  carry optional launch args and substitute them shell-quoted.
- `tools/sculpt/` — `agent create` / `run` gain a launch-args option
  for terminal agents.

Delete:

- `sculptor/sculptor-workflow/skills/build/` — SKILL.md replaced by
  coordinator (REQ-SKILL-2); `implement_task.md` content moves into
  coordinator's package-data process doc.

## Alternatives Considered

- **Socket/CLI signal channel** (hooks call a `coordinator signal` CLI
  against a unix socket, like `sculpt signal`): push latency instead
  of polling, but adds a server lifecycle, a PATH dependency, and a
  weaker crash/resume story. Rejected for the filesystem journal.
- **TOML or JSON manifest:** TOML would be zero-dep (stdlib tomllib)
  and match the terminal-agent registration convention; JSON is
  stdlib both ways. YAML chosen as the idiomatic DAG-config format
  and the friendliest to hand-edit; the pyyaml dep is contained.
- **Execution state in Sculptor's per-agent state dir:** keeps the
  repo pristine, but breaks portability outside Sculptor
  (REQ-PIPE-4) and decouples state from the plan it belongs to.
  Rejected for the self-gitignoring `_state/` dir in the plan folder.
- **SQLite execution state:** transactional, but opaque to eyeball
  diagnosis and overkill for a sequential increment-1 run. JSONL
  journal chosen.
- **Rust + ratatui coordinator:** single static binary, no
  interpreter — but it would be the only Rust in the repo (new
  toolchain, CI, lint, packaging), slows the agent-driven build loop,
  and contradicts REQ-PKG-1; pyinstaller already covers standalone
  distribution. Python + Textual chosen.
- **rich Live + hand-rolled key handling:** lighter than Textual, but
  drill-down screens, focus, and approval controls would be
  hand-built without a test harness. Rejected.
- **Automated-prompt handoff to coordinator** (Plan types
  `run <plan-dir>` into the tab via `accepts_automated_prompts`):
  works with zero backend changes, but parsing typed input before a
  Textual app owns the terminal is fragile, and Sculptor vs
  standalone would behave differently. Rejected for the `{args}`
  placeholder.
- **Env-var launch args** (`SCULPT_AGENT_ARGS` exported into the
  session): injection-safe with no renderer changes, but invisible in
  the registration file and a second args channel to document. The
  `{args}` placeholder keeps the contract visible in the registration
  itself; the renderer shell-quotes each arg to close the injection
  surface.
- **Agentic review after every task by default:** maximum scrutiny,
  but one reviewer session per task is costly and most tasks are
  small; phase-boundary review with per-task opt-in chosen.
- **Sculptor agent/tab per task:** ruled out by the spec (Non-Goals,
  REQ-COORD-4) — plans can reach hundreds of tasks.

## Risks and Mitigations

- **A worker ends its turn with work unfinished:** a headless session
  exits at turn end, so backgrounded work dies with it and its
  completion notification never arrives. Mitigation: a Stop guard hook
  vetoes the turn and sends the worker back to drain it in the
  foreground; an attempt that ends that way anyway fails and retries
  with the abandoned tasks named in its retry context.
- **Hook fragment interplay with user settings:** Claude Code merges
  hooks across settings sources, so a developer's global hooks also
  fire inside workers. Signals are still isolated (per-attempt
  absolute paths); worst case is duplicate side effects from the
  user's own hooks. Documented, not blocked.
- **Rate limits burning retry budget** (REQ-WORKER-7): transcript
  inspection classifies rate-limited attempts; coordinator pauses instead
  of retrying, and resumes on schedule.
- **`{args}` substitution as an injection surface:** caller args are
  spliced into a command that runs in a login shell. Mitigation: the
  renderer shell-quotes each argument individually (never raw
  interpolation), the placeholder is opt-in per registration and
  allowed at most once, and args come only from the authenticated
  create-agent API.
- **Zombie workers after a coordinator crash:** worker PIDs are journaled
  at spawn; resume kills any recorded PID still alive (process-group
  kill) before discarding the mid-flight attempt.
- **Flaky verification commands failing good work:** gate results
  record full command output in the attempt dir; the retry seed says
  which command failed, and the TUI's per-task retry lets a human
  re-run a gate without a fresh worker.
- **Phase-review re-open loops** (review fails → tasks retried →
  review fails again): re-opened tasks keep their attempt history, so
  the ladder still bounds total attempts; a review may hand back
  `defaults.phase_review_rounds` rounds of findings (per-phase
  `review_rounds` overrides it, default 2) before it escalates to a
  human gate. `coordinator extend <plan> <node>` grants more mid-run —
  review rounds for a review node, ladder attempts for a task — so a
  loop that is visibly converging can keep going on a human's call.
- **Workers touching files outside their task's scope** in the shared
  working tree: sequential execution (increment 1) means each task's
  gate sees exactly that task's diff; coordinator refuses to start a run
  on a dirty tree, and the agentic reviewer flags out-of-scope edits.
- **User edits the tree mid-run:** same dirty-tree check between
  tasks; a surprise diff pauses the run with a clear report rather
  than folding user edits into a task's commit.

## Testing Strategy

- **Unit tests** (in `tools/coordinator/tests/`, run by `just test-unit`):
  manifest parsing/validation (bad DAGs, unknown registrations, cycle
  detection), scheduler transitions and topological order, journal
  append/replay/resume (including mid-flight attempt discard), gate
  policy resolution (defaults vs overrides), escalation ladder
  arithmetic, worker-registration layering and placeholder rendering,
  hooks-fragment generation.
- **Fake-worker end-to-end tests:** a test worker registration whose
  launch command is a script that emits scripted `signals.jsonl`
  events and makes scripted commits in a temp git repo — exercising
  the full run loop (pass, gate-fail-retry, escalate, resume after
  kill) deterministically, with no LLM and no network.
- **TUI tests** via Textual's Pilot: dashboard renders a given state
  snapshot; controls append the right intents to the journal.
- **Backend unit tests** for the `{args}` placeholder: registry
  validation (opt-in, at most once), renderer shell-quoting, and the
  create-agent path carrying args — alongside the existing
  terminal-agent registry and session tests.
- **One real-worker smoke test** (manual / opt-in, not CI): a
  two-task toy plan against a real Claude session, validating the
  PTY + hooks + billing assumptions early in increment 1.

## Open Questions

- Exact rate-limit markers in transcripts across Claude Code versions
  — resolve during the increment-1 spike task.
- Interactive-node UX outside Sculptor (increment 2): terminal
  handover vs tmux-style panes.
- Finalize-signal contract details for interactive skills
  (increment 2, REQ-SKILL-3, REQ-PIPE-2).
- Graph mutation semantics for manifest expansion / phase re-entry
  (increment 2, REQ-PIPE-3).
- Worktree merge-back conflict policy details (increment 3,
  REQ-PAR-2).
