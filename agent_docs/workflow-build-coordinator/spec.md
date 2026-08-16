# Workflow Build Coordinator

## Overview

Improve Sculptor's workflow skills (the Spec(+Mock) → Architect → Plan →
Build → Review pipeline). The pipeline produces good results today, but
two things are wanted:

1. **A thorough review of the current pipeline** to surface room for
   improvement across all phases.
2. **Replace the agentic Build coordinator with a mechanical one.**
   When plans get long, the Build agent gets off track or worries about
   context usage and pauses without completing the work. Since the Plan
   step already breaks work into small, self-contained tasks, a
   mechanical (non-agent) coordinator should drive the Build step — e.g.
   a DAG-based coordinator where each plan task is a node. The
   coordinator spawns a fresh agent per task ("implement and verify
   exactly this one task"), so every task gets fresh context and no
   agent can stall mid-plan.

The mechanical coordinator also unlocks follow-on capabilities:

- The Plan could emit **parallel streams of work** instead of a linear
  list.
- Each task could have its own **review gates** (mechanical, agentic,
  or human) before the next task proceeds.
- **Different harnesses/models per task** — e.g. Fable/Opus for
  Spec/Architect/Plan, Sonnet or cheaper models for Build tasks, or
  different agents for logic-heavy vs UI-heavy tasks.

Overall goal: build out bigger and bigger chunks of work, fully
autonomously, with complete verification along the way.

**Scope decision:** full pipeline overhaul — the mechanical Build
coordinator is the centerpiece, but the effort also folds in the
findings from the pipeline review (machine-readable plan format,
per-task verification gates, progress visibility, model selection,
ritual-boilerplate dedup where it makes sense).

**Coordinator shape decision:** a deterministic, self-contained
program (Python, in `tools/`) that runs inside a Sculptor tab as a
registered terminal agent — and equally outside Sculptor, discovering
`sculpt` dynamically. It does NOT spawn a Sculptor agent per task
(plans can reach hundreds of tasks); instead it spins worker agent
processes up and down itself — fresh-context interactive sessions
driven via hooks, one per task attempt — and records their session
IDs for later diagnosis. Longer term it orchestrates the entire
pipeline as a graph, with the design phases as interactive nodes.

## User Scenarios

### Overnight autonomous build (happy path)

The user finalizes a phase plan in the Plan tab and picks "Proceed to
Build." The Plan agent launches the coordinator as a terminal-agent
tab and hands it the plan folder. The coordinator parses the DAG,
signals `busy`, and works through tasks in topological order: one
fresh headless worker per task (REQ-COORD-5, REQ-WORKER-2), gates
after each (REQ-GATE-1..2), a commit per passing task, `files-changed`
after each commit so the diff viewer stays live. The user checks the
TUI dashboard occasionally (REQ-UX-1), then goes to bed. In the
morning all tasks are green and the phase review is ready.

### Task fails, retries, escalates, recovers

A worker's diff fails the agentic review gate. The coordinator kills
the worker, records the findings, and spawns a fresh attempt seeded
with them (REQ-FAIL-1). That attempt fails the mechanical gate; the
retry budget is now exhausted, so the coordinator escalates to the
configured stronger model with the full failure history (REQ-FAIL-2).
The escalated attempt passes both gates. The dashboard shows the
task's attempt history; no human was involved.

### Retry exhaustion surfaces cleanly

The escalated attempt also fails. The task is marked failed; the
coordinator keeps executing DAG branches that don't depend on it
(REQ-FAIL-3). When nothing independent remains, it signals `waiting`
with a failure report. The user opens the drill-down (REQ-UX-2),
inspects the attempts' session IDs and gate findings, fixes the task
file (or the code) and hits "retry task" (REQ-UX-3).

### Human gate on a risky task

The plan marks a schema-migration task with a human gate
(REQ-GATE-3). When its worker and automatic gates pass, the
coordinator pauses that branch, signals `waiting`, and presents the
task's diff. The user approves from the dashboard; dependent tasks
proceed.

### Crash / restart resume

Sculptor (or the coordinator) is killed at task 7 of 40. On relaunch
— including via the terminal-agent resume path — the coordinator
reloads the on-disk execution state (REQ-STATE-1..2), sees tasks 1–6
passed and task 7 was mid-flight, discards task 7's incomplete
attempt, and resumes from there. No completed work is redone.

### Phase boundary with re-architecting

Phase 1 (sequential coordinator) is built and reviewed. Using it
surfaces discoveries — worker completion detection needs an extra
signal, and the user wants different gate defaults. Instead of
planning phase 2 directly, the user re-enters Architect with this
feedback (REQ-FLOW-4); the architecture is revised, then Plan produces
the phase-2 plan folder and a fresh coordinator run executes it.

### Mixed models across one plan

The plan annotates backend-logic tasks to run on a cheap worker
registration and marks a gnarly concurrency task for a stronger model
(REQ-MODEL-1); design docs were produced earlier by Fable/Opus tabs.
The coordinator launches each task's worker per its registration; the
dashboard shows which model ran each task.

## Requirements

### Coordinator (REQ-COORD)

- `REQ-COORD-1`: The Build step MUST be driven by a deterministic
  program (not an LLM agent) that parses the plan into a task DAG and
  executes it to completion.
- `REQ-COORD-2`: The coordinator MUST run inside a Sculptor tab as a
  registered terminal agent (TOML registration under
  `<sculptor folder>/terminal_agents/`), so the user sees build
  progress in a normal tab.
- `REQ-COORD-3`: The coordinator MUST integrate with Sculptor status
  via `sculpt signal` (busy while tasks run, waiting on human gates,
  files-changed after each task commit, session-id for
  resume-after-restart).
- `REQ-COORD-4`: The coordinator MUST NOT create a Sculptor
  agent/tab per task. Plans may contain dozens or hundreds of tasks;
  per-task workers are plain agent processes (not Sculptor agents)
  spawned and reaped by the coordinator directly.
- `REQ-COORD-5`: Each task MUST be executed by a fresh-context
  worker instructed to implement and verify exactly that one task.
- `REQ-COORD-6`: The coordinator MUST record each task worker's
  session ID (and its outcome) durably, so any past task run can be
  inspected or resumed later for diagnosis.

### Execution state (REQ-STATE)

- `REQ-STATE-1`: Task execution state (pending / running / passed /
  failed, worker session IDs, gate results) MUST be recorded on disk,
  not held in any agent's context.
- `REQ-STATE-2`: A killed or interrupted coordinator MUST be
  resumable, picking up from the recorded state without redoing
  completed tasks.

### Pipeline orchestration (REQ-PIPE)

- `REQ-PIPE-1`: The coordinator models the **entire workflow** as a
  graph — Spec, Mock, Architect, Plan, build tasks, gates, and Review
  are all nodes — and owns every transition between them. No phase
  transition depends on an agent remembering to spawn another agent.
- `REQ-PIPE-2`: There are two node kinds. **Autonomous nodes** (build
  tasks, agentic gates, Review) run headless workers; completion is
  decided by gates. **Interactive nodes** (Spec, Mock, Architect,
  Plan) run user-paced conversational agents; completion is an
  explicit finalize signal from the session (the skill's finalize
  step notifies the coordinator), not a gate.
- `REQ-PIPE-3`: The graph is dynamic: the Plan node's output (the
  plan manifest) expands into the build subgraph for that phase, and
  phase re-entry (REQ-FLOW-4) appends new Architect/Plan/build nodes
  to a live pipeline.
- `REQ-PIPE-4`: **Portability:** the coordinator MUST run outside
  Sculptor. It discovers dynamically whether `sculpt` is available:
  if yes, interactive nodes spawn as Sculptor agent tabs and status
  flows via `sculpt signal`; if no, the coordinator launches
  interactive agent sessions itself (and build workers exactly as it
  always does).

### Packaging (REQ-PKG)

- `REQ-PKG-1`: The coordinator is a Python package in this repo
  (under `tools/`, alongside `tools/sculpt`), with real unit tests
  and the repo's lint/type gates, exposed as a CLI.
- `REQ-PKG-2`: It MUST be entirely self-contained and shippable
  independently of Sculptor — no hard dependency on the Sculptor
  backend or the `sculpt` CLI beyond optional runtime discovery.

### Plan format (REQ-PLAN)

- `REQ-PLAN-1`: The Plan step emits a **manifest + task files**: the
  human-readable self-contained task `.md` files stay as today, plus
  one machine-readable manifest (e.g. `plan.yaml`) holding the DAG —
  per task: id, task-file path, dependencies, worker
  registration/model, gate policy, retry overrides. The coordinator
  parses only the manifest; humans and workers read only the task
  files.
- `REQ-PLAN-2`: The plan format MUST express real dependencies (a
  DAG) from day one, so parallel streams are representable even
  before the coordinator executes them concurrently.

### Parallel execution (REQ-PAR)

- `REQ-PAR-1`: The first delivered increment of the coordinator
  executes tasks sequentially, in topological order, in the shared
  workspace working tree.
- `REQ-PAR-2`: A later increment adds concurrent execution of
  independent DAG branches, each worker in its own git worktree; the
  coordinator merges each task's commits back and surfaces merge
  conflicts as task failures.

### Workers (REQ-WORKER)

- `REQ-WORKER-1`: Worker launch MUST be a generic registered command
  (a template with placeholders, in the spirit of terminal-agent
  registrations) — not hardcoded to one harness. Adding a new
  harness/model means writing a new worker registration.
- `REQ-WORKER-2`: **Dropped.** Workers are headless Claude Code
  sessions (`claude -p`), which bill against a subscription the same
  way and write transcripts an interactive PTY session does not. One
  fresh session per task attempt, task prompt passed at launch; the
  coordinator MUST NOT depend on parsing the TUI screen.
- `REQ-WORKER-3`: Completion/liveness detection MUST come from hooks
  (e.g. Stop/SessionStart/Notification signaling the coordinator) and
  process lifecycle — never screen parsing. Process exit without a
  completion signal is a failed attempt.
- `REQ-WORKER-4`: "Turn ended" MUST NOT be treated as "task done."
  Gates decide success. On gate failure the coordinator kills the
  worker and spawns a fresh attempt seeded with the failure context,
  up to a bounded retry count, then escalates.
- `REQ-WORKER-5`: The coordinator MUST capture each attempt's session
  ID (via hooks) and record it in execution state for later
  inspection/resume.
- `REQ-WORKER-6`: Workers run with permissions pre-granted and are
  instructed never to wait on user input; a worker that enters a
  "waiting" state is treated as a failed attempt or escalated to a
  human gate.
- `REQ-WORKER-7`: The coordinator SHOULD detect rate-limit exhaustion
  and enter a paused state rather than burning attempts.

### Model/harness selection (REQ-MODEL)

- `REQ-MODEL-1`: Tasks MUST be able to specify which worker
  registration (harness + model) executes them, enabling e.g.
  Fable/Opus for design phases and cheaper models for build tasks, or
  different agents for logic-heavy vs UI-heavy tasks.

### Review gates (REQ-GATE)

- `REQ-GATE-1`: **Mechanical gate** — the coordinator itself re-runs
  the task's verification commands (repo pre-commit verification plus
  task-specific checks) and requires the expected commit to exist.
- `REQ-GATE-2`: **Agentic review gate** — a fresh reviewer agent
  (never the implementer) reads the task file and the task's diff and
  passes/fails with findings; findings seed the retry attempt.
- `REQ-GATE-3`: **Human gate** — a task or phase boundary can pause
  the DAG and wait for user approval (coordinator signals `waiting`).
- `REQ-GATE-4`: Gate policy is declared per task in the plan
  metadata (which gates run, retry budget, escalation).

### Pipeline flow — phased delivery (REQ-FLOW)

- `REQ-FLOW-1`: Spec and Architecture cover the full system; the
  Architecture MUST name the delivery phases and identify a
  right-sized first increment.
- `REQ-FLOW-2`: **Plan-per-phase:** each phase gets its own plan
  folder, coordinator run, and review. Later phases stay unplanned
  until reached — no detailed plans authored before the feedback that
  would invalidate them exists. The coordinator's unit of work is one
  phase's DAG.
- `REQ-FLOW-3`: Phase boundaries MUST support human review before the
  next phase proceeds.
- `REQ-FLOW-4`: Between phases the user (or an autonomous policy) can
  either proceed directly to planning the next phase, or **re-enter
  Architect** with the accumulated feedback and technical discoveries
  first — without restarting the pipeline or losing upstream
  artifacts. (This effort is itself an instance: sequential
  coordinator first, worktree parallelism as a later phase.)

### Delivery increments of this effort (REQ-INC)

- `REQ-INC-1`: **Increment 1 — build-DAG executor.** The coordinator
  executes one phase's build DAG: manifest parsing, sequential
  execution in the shared workspace, fresh interactive workers, all
  three gate types, the escalation ladder, on-disk state and resume,
  and the TUI dashboard — plus the Plan skill emitting the manifest.
- `REQ-INC-2`: **Increment 2 — pipeline orchestration.** Interactive
  nodes (Spec/Mock/Architect/Plan), sculpt-tab spawning with dynamic
  discovery, finalize-signal contract, phase re-entry and graph
  expansion.
- `REQ-INC-3`: **Increment 3 — parallel execution.** Concurrent
  independent DAG branches via git worktrees with merge-back
  (REQ-PAR-2).
- `REQ-INC-4`: The node/manifest schema MUST accommodate all
  increments from day one (node kinds, dependencies, gates, worker
  registrations), even though increment 1 only executes autonomous
  build nodes. The standard pipeline shape is coordinator code, not
  user-editable data, through these increments.

### Skill changes (REQ-SKILL)

- `REQ-SKILL-1`: The Plan skill emits the manifest alongside task
  files, drops the two mandatory `99_*` handoff tasks (final
  verification becomes a built-in coordinator gate; Review spawning
  becomes coordinator code), and hands off to the coordinator at
  finalize.
- `REQ-SKILL-2`: The `/build` agent skill is **replaced immediately**
  in increment 1 — no fallback agent path. `implement_task.md`
  survives in evolved form as the per-task process document embedded
  in each worker's prompt.
- `REQ-SKILL-3`: In increment 2, the design skills' finalize steps
  adopt the finalize-signal contract so the coordinator can own
  their transitions.
- `REQ-SKILL-4`: Skill cleanup rides along with skills already being
  touched: the Q&A-ritual boilerplate is deduplicated into one shared
  reference document, and stale context-management guidance (e.g.
  "don't delegate exploration to sub-agents") is refreshed in the
  same edits. No separate cleanup workstream.

### Failure handling (REQ-FAIL)

- `REQ-FAIL-1`: A failed gate spawns a fresh worker attempt seeded
  with the failure context, up to a bounded per-task retry budget.
- `REQ-FAIL-2`: When the base retry budget is exhausted, the
  coordinator MUST first escalate to a stronger worker (e.g.
  sonnet → opus/fable), seeded with all prior attempts' failure
  context, before involving the human.
- `REQ-FAIL-3`: If the escalated attempt also fails, the task is
  marked failed; the coordinator continues executing DAG branches
  that do not depend on it, then stops and surfaces all failures at
  once (signal `waiting` with a failure report).
- `REQ-FAIL-4`: The escalation ladder (attempt counts, escalation
  model) MUST be configurable, with sensible defaults, and
  overridable per task in the plan metadata.

### Coordinator UX (REQ-UX)

- `REQ-UX-1`: The coordinator renders a full TUI dashboard in its
  tab: DAG/task view with per-task state (pending / running /
  gate-checking / passed / failed / waiting), attempt counts, and the
  active workers' current activity.
- `REQ-UX-2`: Per-task drill-down: gate results, attempt history,
  worker session IDs, and access to worker transcripts for diagnosis.
- `REQ-UX-3`: Interactive controls: pause, resume, retry task, skip
  task, approve human gate, abort run.
- `REQ-UX-4`: The dashboard state and controls MUST remain consistent
  with the on-disk execution state — the TUI is a view over the state
  file(s), not a second source of truth.

## Non-Goals

- Spawning a full Sculptor agent (tab) per task — plans can reach
  hundreds of tasks; per-task workers are coordinator-managed
  processes, not Sculptor agents.
- Replacing the interactive Spec/Architect/Plan phases with
  automation — those remain conversational; this effort mechanizes
  the transitions and execution, not the design conversations.
- User-authorable pipeline templates (custom flow definitions as
  data) — the standard flow ships as coordinator code; a template
  format is a future phase once the node model has proven itself.
- Screen-scraping worker TUIs — all worker signaling is hooks,
  filesystem, and process lifecycle.

## Open Questions

These are unresolved decisions for the Architect and Plan phases to
pick up; everything decided during spec Q&A has been folded into the
Requirements above.

- **Billing premise to verify:** does `claude -p` (print mode) bill
  against a logged-in subscription the same way interactive mode
  does? If yes, print-mode workers (no PTY, structured output) are
  strictly more stable and become just another worker registration.
- **Worker contract details:** exact placeholder set for worker
  registrations, how the hooks fragment reaches the worker, how the
  completion signal travels coordinator-ward (file, socket, `sculpt
  signal`-style CLI).
- **Rate-limit detection:** how the coordinator distinguishes
  "rate-limited, pause and resume later" from "worker failed."
- **Interactive-node UX outside Sculptor:** how the coordinator hands
  the terminal to a conversational session and back (foreground
  takeover with dashboard resume? tmux-style panes?).
- **Finalize-signal contract:** exactly how interactive skills notify
  the coordinator of completion (marker file, small CLI, both), and
  how the design skills' finalize steps adopt it.
- **Graph mutation semantics:** how plan-manifest expansion and phase
  re-entry mutate the persisted pipeline state safely.
- **Agentic review gate specifics:** what the reviewer's prompt
  contains beyond the task file and diff, and whether reviewers use
  the same worker-registration mechanism as implementers.
- **Default retry/escalation numbers:** base attempts per task and
  the default escalation model, before per-task overrides.
- **Worker prompt contents:** what each worker is given beyond the
  task file (the evolved `implement_task.md` process doc, repo config
  excerpts, failure context on retries) and how it's assembled.
