# Workflow Build Coordinator (Increment 1) — Review

Reviewed: `origin/main...HEAD` (23 commits, 91 files, ~9,900 insertions),
against `spec.md`, `architecture.md`, and `plan/00_overview.md`.

## Summary

- **The implementation meets the spec**, and after the fix pass every
  requirement in scope is Covered — including the two former Partials
  (per-task escalation override, REQ-GATE-4 / REQ-FAIL-4, added in
  `b2ff9c7a`).
- **All findings below have been fixed and committed** (resolution log
  at the top of *Code Review Findings*), except three consciously
  declined LOWs with rationale. The full verification suite is green
  after every fix commit: `just check` plus `just test-unit` (backend,
  foundation, sculpt, coordinator — now 225 tests — and frontend).
- The original top risks — the CRITICAL stale-state rerun hazard, the
  journal-poisoning crash path, the launcher resource leaks, and the
  orphaned reviewer processes — are all closed with regression tests.

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-COORD-1 | Covered | `tools/coordinator/coordinator/dag.py:45-103` (manifest→DAG, cycle detection), `scheduler.py:266-307` (run loop), `run.py:94-182` |
| REQ-COORD-2 | Covered | `samples/terminal_agents/coordinator/coordinator.toml`; bundled install `sculptor/sculptor/services/terminal_agent_registry/bundled.py:44-52,144-162`; `accepts_automated_prompts = false` |
| REQ-COORD-3 | Covered | `tools/coordinator/coordinator/sculpt_signals.py` (busy/waiting/files-changed/session-id); wired in `run.py:158-179` |
| REQ-COORD-4 | Covered | `launcher.py:227-353` — plain `subprocess.Popen` workers spawned/reaped by the coordinator; no Sculptor agent per task |
| REQ-COORD-5 | Covered | `attempt.py:108-114` (one-task bootstrap prompt), `launcher.py:58-71` (`scrub_env` guarantees fresh session), `data/implement_task.md` |
| REQ-COORD-6 | Covered | session id from hooks (`launcher.py:110-113`) → journal (`executor.py:163-175`, `journal.py:288-297`); failure report prints `claude --resume` hints (`scheduler.py:558-560`) |
| REQ-STATE-1 | Covered | `statedir.py:19-33` (`_state/` + self-written `.gitignore`), `scheduler.py:248-264` (write-ahead transitions) |
| REQ-STATE-2 | Covered | `scheduler.py:188-246` (`Scheduler.load`: replay, mid-flight discard, PID reap) — but see the reviewer-PID reap gap in findings |
| REQ-PIPE-1..3 | Deferred | Increment 2, per plan (REQ-FLOW-2) |
| REQ-PIPE-4 | Covered | `sculpt_signals.py:79-88` (`detect_signaler`: PATH + `SCULPT_AGENT_ID`), `NullSignaler` no-op outside Sculptor |
| REQ-PKG-1 | Covered | `tools/coordinator/pyproject.toml` (typer CLI entry); `justfile` format/lint/`test-unit-coordinator`; `pyrefly.toml:26` |
| REQ-PKG-2 | Covered | zero `sculptor`/`sculpt` imports in the package; `sculpt` reached only via `shutil.which` subprocess probes |
| REQ-PLAN-1 | Covered | consume: `manifest.py:84-133,196-217`; emit: `sculptor/sculptor-workflow/skills/plan/SKILL.md:176-372` |
| REQ-PLAN-2 | Covered | `TaskSpec.deps` → real DAG with topological order (`dag.py:45-103`) |
| REQ-PAR-1 | Covered | `scheduler.py:306` executes `ready[0]` only — sequential, in the shared tree |
| REQ-PAR-2 | Deferred | Increment 3, per plan |
| REQ-WORKER-1 | Covered | `registrations.py:67-185` — YAML command templates, layered built-in → user → repo discovery, unknown placeholders rejected |
| REQ-WORKER-2 | Covered | `data/workers/claude-interactive.yaml`; PTY launch `launcher.py:227-290`; screen never parsed (`launcher.py:10-12`) |
| REQ-WORKER-3 | Covered | signals + process lifecycle only (`launcher.py:298-324`); exit without Stop → `exited-without-stop` failure |
| REQ-WORKER-4 | Covered | Stop only hands off to gates (`gates.py:1-13`); gate failure → fresh seeded attempt (`scheduler.py:376-429`) |
| REQ-WORKER-5 | Covered | `launcher.py:110-112` → `SignalObserved` → `AttemptRecord.session_id` |
| REQ-WORKER-6 | Covered | `--dangerously-skip-permissions` + `skipDangerousModePermissionPrompt` (`attempt.py:66`); waiting signal = failed attempt (`launcher.py:126-134,305`) |
| REQ-WORKER-7 | Covered | `ratelimit.py:22-73` transcript-tail classification; paused without burning budget (`scheduler.py:358-374`) — see false-positive finding |
| REQ-MODEL-1 | Covered | `TaskSpec.worker` override (`manifest.py:98`), `registrations.py:188-195` |
| REQ-GATE-1 | Covered | `gates.py:58-101` — verification commands + commit-required (honors `no_change`) |
| REQ-GATE-2 | Covered | `review.py` + `executor.py:296-389`; phase-boundary default (`manifest.py:119`, `dag.py:65-70`); fail-closed verdicts |
| REQ-GATE-3 | Covered | `executor.py:198-209` + `scheduler.py:504-515`; TUI approval — see waiting-state UX finding |
| REQ-GATE-4 | Covered | per-task `gates`/`attempts` (`manifest.py:99-100`); per-task `escalation_worker` added in `b2ff9c7a` |
| REQ-FAIL-1 | Covered | `scheduler.py:376-429`, `ladder.py:59-102` (seeded retries, bounded budget) |
| REQ-FAIL-2 | Covered | `ladder.py:66-73` — escalated rung with full failure history; defaults 2 base + 1 escalated |
| REQ-FAIL-3 | Covered | independent branches continue (`dag.py:123-141`); consolidated failure report + waiting signal (`scheduler.py:531-564`, `run.py:176-177`) |
| REQ-FAIL-4 | Covered | attempts + escalation model configurable plan-wide and overridable per task (per-task `escalation_worker` added in `b2ff9c7a`) |
| REQ-UX-1 | Covered | `tui/app.py:135-182`, `tui/widgets.py` — task table with states, attempts, worker, activity |
| REQ-UX-2 | Covered | `tui/drilldown.py:71-163` — gates, attempt history, session ids, transcript tail |
| REQ-UX-3 | Covered | `tui/app.py:93-103,231-267` — pause/resume/retry/skip/approve/abort |
| REQ-UX-4 | Covered | controls append journal intents only (`tui/app.py:206-217`); dashboard renders from snapshot only |
| REQ-FLOW-1..4 | Covered | process-level: architecture names the three increments; plan-per-phase honored (this plan covers increment 1 only) |
| REQ-INC-1 | Covered | the whole diff |
| REQ-INC-2/3 | Deferred | per plan |
| REQ-INC-4 | Covered | `manifest.py:65` reserves `spec/mock/architect/plan/review/gate` kinds; `scheduler.py:522-529` rejects unexecutable kinds at run start |
| REQ-SKILL-1 | Covered | `plan/SKILL.md:176-372` (manifest schema + authoring rules), `:408-428` (coordinator handoff via `--launch-arg run --launch-arg <plan-dir>`); 99_* templates gone |
| REQ-SKILL-2 | Covered | `skills/build/` deleted; `implement_task.md` evolved into coordinator package data with all "ask the user" language removed |
| REQ-SKILL-3 | Deferred | Increment 2, per plan |
| REQ-SKILL-4 | Covered | `skills/_shared/qa-ritual.md` referenced by spec/mock/architect/plan/review/fix-bug; stale sub-agent guidance refreshed in the same pass |

## User Scenarios

**Overnight autonomous build (happy path).** Delivered. Plan finalize
creates a Coordinator tab with `--launch-arg run --launch-arg
<plan-dir>`; the coordinator signals busy, executes topologically with
gates, commits per task, and signals files-changed per commit. Tested by
`test_e2e_fake_worker.py::test_all_pass_three_tasks_two_phases`,
`::test_signal_sequence_with_fake_sculpt`, and
`::test_review_handoff_spawns_agent_after_full_success`; a live manual
demo through a real Sculptor tab is documented in commit `5a242370`.

**Task fails, retries, escalates, recovers.** Delivered. Findings seed
fresh attempts; the escalated rung runs on the stronger registration
with the full failure history. Tested by
`::test_retry_after_gate_failure_succeeds` and
`::test_escalation_uses_escalation_registration_with_full_history`.

**Retry exhaustion surfaces cleanly.** Delivered. Failed tasks don't
block independent branches; the consolidated failure report (with
session ids and resume hints) lands when nothing runnable remains, and
the drill-down exposes attempts. Tested by
`::test_exhausted_ladder_fails_with_report` and
`::test_signal_waiting_on_failed_run`. Caveat: a manual TUI `retry`
does not carry the failure seed context an automatic retry gets
(finding below).

**Human gate on a risky task.** Delivered with a UX caveat. Human-gated
tasks pause the branch, signal waiting, and approve via TUI intent
(`::test_human_gated_task_blocks_then_approves`,
`::test_human_phase_review_waits_and_approves`). However, once nothing
else is runnable the run loop exits while the dashboard stays up, so an
approval clicked after that point is journaled but not consumed until
the coordinator is re-run — the dashboard doesn't say so (finding
below).

**Crash / restart resume.** Delivered. The run id doubles as the
Sculptor terminal session id, so the tab's resume path re-enters
`coordinator resume <run-id>`; replay discards mid-flight attempts and
reaps recorded implementer PIDs. Tested by
`::test_resume_after_kill_skips_completed_tasks` (kill -9 mid-run) and
`test_scheduler.py::test_resume_discards_mid_flight_attempt_and_reaps`.
Caveats: reviewer PIDs are not reaped, and a discarded mid-flight
attempt still burns retry budget (findings below).

**Phase boundary with re-architecting.** Process-level (REQ-FLOW-4);
nothing to verify in code. The plan-per-phase structure this diff was
built under is itself the demonstration.

**Mixed models across one plan.** Delivered. Per-task `worker:`
overrides resolve through layered registrations; the dashboard's task
table shows each task's worker registration. Tested by
`test_registrations.py` (layering/overrides) and the TUI tests.

## Test Coverage

- **Tests added:** 26 coordinator test files (205 tests: manifest, DAG,
  journal replay/resume, scheduler transitions and intents, launcher
  spawn/kill/reap with real subprocesses, gates, ladder, rate-limit,
  registrations, attempt prep, trust seeding, sculpt signaling, review
  spawn, CLI, TUI via Textual Pilot, and a 639-line fake-worker e2e
  suite); backend tests for the `{args}` placeholder (registry
  validation, shell-quoted rendering incl. hostile input, create-agent
  API 422 paths, launch-vs-resume, bundled install); sculpt CLI
  `--launch-arg` tests.
- **Suite status:** all green. `just check` passes (lint, typecheck,
  ratchets, file hygiene). `just test-unit` passes: backend 763 passed
  / 4 skipped (pre-existing skips, untouched by this diff), foundation
  124, sculpt 203, coordinator 205 passed / 1 deselected, frontend OK.
- **Integration tests run:** none added or required — the plan's
  end-to-end coverage is the fake-worker e2e suite (real subprocesses,
  real git, real signals files; no LLM), which ran green as part of
  `just test-unit`.
- **Skipped / xfail / pending:** only
  `test_smoke_real_claude.py` — intentionally opt-in
  (`COORDINATOR_REAL_SMOKE=1`), triple-guarded, and called for by the
  architecture as a manual smoke test. Justified. No xfail anywhere.

## Code Review Findings

### Resolution log

Every finding below was addressed after the review, one verified fix
commit per group, each gated on `just format` / `just check` /
`just test-unit`:

- `18cf7de2` — **Resolved** the CRITICAL stale-state rerun hazard
  (`coordinator run` now refuses a plan with existing run state) +
  regression test.
- `b85bb5e4` — **Resolved** the HIGH journal poisoning: a
  crash-truncated final line is discarded before the next append.
- `d43e27d5` — **Resolved** the HIGH launcher leaks (try/finally
  cleanup on every path, PTY fds closed on failed spawn, drain-thread
  close race avoided) and the post-kill `Stop` verdict flip.
- `bf6de4a6` — **Resolved** the HIGH orphaned reviewers: resume reaps
  `<node>.review` PIDs too.
- `e3f8984b` — **Resolved** gate subprocess hardening: stdin closed,
  verification timeout, git timeouts, `GitError` carrying stderr.
- `b2ff9c7a` — **Resolved** the intent-consumption race, sticky
  pause-then-resume, stale aborts on resume, seedless manual retries,
  budget burned by discarded attempts, rate-limit false positives
  (error surfaces only) and unclassified reviewer rate limits, abort
  latency during reviews, duplicate Review handoff on resume, the
  scheduler `print`, the TUI's silent stopped state, and the two
  Partial requirements (per-task `escalation_worker`).
- `2f6c941a` — **Resolved** the LOWs (root-commit review diff,
  reviewer-dirtied tree voided+restored, attempt-dir collision digest,
  `process_doc` containment, `tail_text` seek) and the test-quality
  items (XDG isolation, TUI polling, kill-window predicate, git
  signing/hooks isolation, real retry assertions, PTY kill-path
  parametrization, bundled wrapper deletion).
- `960715c2` — **Resolved** the style categories: dataclasses →
  pydantic, `raise ... from`, REQ-/increment/spike comment cleanup,
  exhaustive fold chains, `TrustError`/`_HandoffError`, executor
  callback dedup, naming (`is_ok`, `finished_gates`,
  `should_start_run`), typed `Finding` findings list, loguru for
  diagnostics.

**Declined with rationale** (recorded, not fixed): the
`reap_recorded_pid` cmdline guard (three layered guards already exist;
a name check would couple the reaper to registration internals for a
low-probability recycled-PID case); the `mkstemp` fd guard
(`os.fdopen` with a constant valid mode cannot realistically raise);
the untyped `**kwargs` passthrough into `execute_plan` (an explicit
re-declaration of nine keyword parameters in two places trades one
LOW for a drift hazard). Known coverage seam, unchanged by design:
the hooks-fragment ↔ real-Claude contract is exercised only by the
opt-in smoke test.

### Original findings (as reviewed, before the fix pass)

Output of `/code-review-checklist` over `origin/main...HEAD` (all
CRITICAL/HIGH findings and the flagged MEDIUMs were re-verified against
the code by the reviewer):

### Correctness

**CRITICAL** — **Resolved in `18cf7de2`.** —
`tools/coordinator/coordinator/run.py:94-123`,
`main.py:104-109`. A fresh `coordinator run <dir>` over a plan whose
`_state/journal.jsonl` already exists was never rejected. The fresh
scheduler restarts `attempt_counts` at 0, so attempt dirs were reused
(`attempt.py:92-93` `mkdir(exist_ok=True)`; `write_hooks_fragment`
never truncates an existing `signals.jsonl`) and `SignalReader` starts
at offset 0 (`launcher.py:85`) — the previous run's `Stop` event was
consumed instantly, the fresh worker killed at spawn, and the attempt
reported "completed". `no_change: true` tasks then passed the
mechanical gate without ever running, and an agentic gate could pass on
a stale `verdict.json`. The journal also became an inconsistent mix of
two runs. Fixed: `execute_plan` now refuses a fresh run when the plan
already has a non-empty journal, pointing to `coordinator resume
<run-id>` (or deleting `_state/`), mirroring the dirty-tree refusal;
regression test `test_run.py::test_fresh_run_over_existing_state_refused`.

**HIGH** — `tools/coordinator/coordinator/journal.py:161-166`.
`Journal.append` never checks whether the file ends with a newline.
After a crash leaves an unterminated final chunk (which `replay`
deliberately tolerates), the next append writes `line + "\n"` straight
after the partial chunk, producing one newline-terminated garbage line
— and every subsequent `replay` raises `JournalError`
(`journal.py:186-190`). The resume path poisons its own journal on its
first event, making the run permanently unrecoverable. Verified.

**HIGH** — `tools/coordinator/coordinator/launcher.py:292-339`. No
try/finally around the observe loop: an exception from
`on_spawn`/`on_signal` (both journal, which can raise) or
`should_abort` propagates without `_terminate_child`, leaking the
worker subprocess, `master_fd`, and the drain thread. Verified.

**HIGH** — `tools/coordinator/coordinator/scheduler.py:238-245` +
`executor.py:269,320-330`. The resume reaper only reaps PIDs for node
ids present in `scheduler.states`, but per-task/phase reviewers journal
`AttemptStarted` under `"{node_id}.review"`, which `Scheduler.load`
filters out (`scheduler.py:207-208`). A coordinator killed during an
agentic gate orphans the live reviewer `claude` process forever.
Verified.

**MEDIUM** — `tools/coordinator/coordinator/launcher.py:298-306,339`.
The final `consume(reader.poll())` after `_terminate_child` sets
`status = "completed"` on a Stop event with no `status is None` guard
(the waiting branch has one), so a Stop landing between the last poll
and the kill flips a `"timeout"`/`"killed"` (user abort) verdict to
success. Verified.

**MEDIUM** — `tools/coordinator/coordinator/gates.py:29-50,71-72`.
Mechanical-gate verification commands run with `shell=True`, no
timeout, and inherited stdin: a hung command wedges the coordinator
forever (workers have a 30-minute deadline; gates have none), and a
command that reads stdin steals keystrokes from the Textual TUI on the
same tty. Git helpers likewise have no timeout and surface bare
`CalledProcessError` without the captured stderr.

**MEDIUM** — `tools/coordinator/coordinator/scheduler.py:467-477`.
Intent-consumption race: `_intents_position` assumes the
`IntentsConsumed` event lands at exactly `len(events)`; a
`ControlIntent` appended concurrently (TUI thread or `coordinator
intent` from another process) between replay and append occupies that
index and is silently skipped for the rest of the live run.

**MEDIUM** — `tools/coordinator/coordinator/executor.py:346-355`.
`_run_agentic` passes no `should_abort` to `launch_attempt` (unlike
`run_attempt` at `executor.py:186`), so an abort issued during a
review is not honored until the reviewer finishes or times out — up to
30 minutes of latency on a user abort. Verified.

**MEDIUM** — `tools/coordinator/coordinator/scheduler.py:209-210` +
`ladder.py:66-73`. Discarded mid-flight attempts burn retry budget:
resume counts the write-ahead `AttemptStarted` of a crashed/paused
attempt toward the ladder even though no worker failure occurred, so
repeated crashes or dirty-tree pauses can exhaust a node with zero real
attempts.

**MEDIUM** — `tools/coordinator/coordinator/run.py:170-175`.
`snapshot.review_agent_id` is never checked before `handoff_review`, so
resuming an already-completed run spawns a second Review agent tab on
every re-invocation.

**MEDIUM** — `tools/coordinator/coordinator/ratelimit.py:22-29` +
`scheduler.py:410-416`. Rate-limit classification greps the transcript
tail for substrings as generic as `"429"` and `"rate limit"`: a task
that legitimately works on rate-limiting code is misclassified on every
attempt — the run pauses forever and the node can neither pass nor
fail. Conversely a genuinely rate-limited *reviewer* is never
classified (only implementer artifacts are inspected) and burns an
implementation attempt.

**MEDIUM** — `tools/coordinator/coordinator/scheduler.py:487-492`. A
manual `retry` intent transitions FAILED→PENDING without setting
`_seed_context`, so a human-triggered retry runs without the failure
context every automatic retry gets.

**MEDIUM** — `tools/coordinator/coordinator/tui/app.py:253-267` +
`scheduler.py:294-305`. When the run loop exits as
`waiting-human`/`failed`/`paused`, the run thread ends but the
dashboard stays up and still accepts approve/retry/skip intents that
nothing in-session will consume; the status bar shows the request
indefinitely with no hint that a re-run is needed.

**MEDIUM** — `tools/coordinator/coordinator/launcher.py:195-224`
(plausible, low probability). `reap_recorded_pid`'s recycled-PID guards
(alive, session leader, older than the coordinator) don't rule out an
innocent long-lived session leader whose PID matches; a
cmdline/name check is missing.

**LOW** — `launcher.py:271-284`: interactive spawn has no try/finally,
so a failed `Popen` leaks both PTY fds (print mode does close them).
`launcher.py:335-338`: `os.close(master_fd)` after a 5s `join` timeout
races a drain thread still blocked in `os.read`. `review.py:92-95`:
`f"{commits[0]}^"` fails uncaught when the first in-scope commit is the
repo's root commit. `statedir.py:44-49`: `sanitize_node_id` maps
`"a:b"` and `"a_b"` to the same attempt dir. `tui/app.py:66-74`:
`StateReader.read` swallows `JournalError`, so a corrupt journal
silently freezes the dashboard. `tui/drilldown.py:21-33`: `tail_text`
reads whole (potentially multi-MB) transcripts despite its docstring.
`journal.py:331-337` / `trust.py:52-58`: `mkstemp` fd leaks if
`os.fdopen` raises. `executor.py:357-360`: a reviewer leaving
*uncommitted* edits passes the HEAD-moved void-check and the dirt is
later misattributed to the user. `executor.py:133-137`:
`defaults.process_doc` lacks the plan-folder containment check task
files get.

### Consistency with stated goal

**MEDIUM** — `tools/coordinator/coordinator/manifest.py:93-101`. The
spec (REQ-FAIL-4, REQ-GATE-4) and architecture ("Both numbers and the
escalation registration are configurable plan-wide and overridable per
task") promise a per-task escalation override; `TaskSpec` exposes only
`worker`/`gates`/`attempts`/`no_change`. Small schema addition; the
ladder already threads per-task attempts through.

Otherwise the diff matches the goal with no scope creep: the
`bundled.py` generalization, sculpt CLI options, and skill edits are
all in service of the spec, and increments 2–3 are correctly left
unbuilt while the manifest reserves their node kinds.

### Test coverage

**MEDIUM** — `tools/coordinator/tests/conftest.py`. `execute_plan` →
`load_registrations` reads the real user-level
`$XDG_CONFIG_HOME/coordinator/workers` (`registrations.py:133-135`);
only `test_registrations.py` isolates it, so every e2e/run test is
hostage to machine state — one broken YAML in the developer's config
dir fails the suite. An autouse `XDG_CONFIG_HOME` fixture would close
this (verified: the existing autouse fixture only scrubs sculpt env
vars).

**MEDIUM** — `tools/coordinator/tests/test_tui.py:96`.
`await pilot.pause(0.8)` is a fixed real-time wait on a 0.5s refresh
timer with no condition polling — 60% margin invites CI flakes.

**LOW** — `test_e2e_fake_worker.py:615`: the kill-window predicate
matches two independent substrings anywhere in the journal, satisfiable
just before the `AttemptStarted` write-ahead it means to wait for.
`fakes.py:228-237`: `make_git_repo` doesn't set `commit.gpgsign=false`
or neutralize `core.hooksPath`, so global git config can flake every
fake-worker commit. `test_review_spawn.py:134-152`: the retry test
asserts `len(sends) >= 1` and would pass with the retry loop deleted.
`test_launcher.py:75-97`: the risky kill paths (waiting, timeout,
SIGKILL escalation) run only in print mode; PTY kill/drain interplay is
happy-path only. The hooks-fragment ↔ real Claude contract is the one
seam CI never exercises (covered only by the opt-in smoke test) —
acceptable, but worth knowing.

### Proof of work completeness

Stated goal is a spec, not an autonomous-workflow MR body — section
skipped.

### Dead code & leftover artifacts

**MEDIUM** — `tools/coordinator/coordinator/scheduler.py:303`. A bare
`print(...)` in the scheduler library bypasses the injected `progress`
callback and the journal (which already carries the message as
`resume_hint`), and writes to stdout inside the TUI's process where
Textual owns the screen.

**LOW** — `sculptor/sculptor/services/terminal_agent_registry/bundled.py:111`.
`get_bundled_claude_code_dir()` survives as a back-compat wrapper whose
only caller is a test import; callers could use
`get_bundled_sample_dir("claude-code")` and the wrapper deleted.

No commented-out code, no ownerless TODOs, no debug leftovers; ruff is
clean across the diff.

### Comments

**HIGH** — `tools/coordinator/coordinator/tui/app.py:3,207`.
`(REQ-UX-4)` requirement-ID pointers in the module docstring and a code
comment — the comments policy explicitly bans `REQ-*` references; they
mean nothing to a reader who opens the file cold.

**MEDIUM** — plan-phase/increment narration baked into code comments:
`scheduler.py:15,524`, `dag.py:8`, `review.py:88`, `manifest.py:40,64`,
`run.py:4` ("increment 1/2", "phase 6 layers the TUI on top"). Rewrite
as present-tense facts ("execution is sequential; only `task` kinds are
executable").

**MEDIUM** — `tools/coordinator/coordinator/attempt.py:34`.
"(spike-verified on Claude Code 2.1.200)" narrates the development
process and pins a volatile version; the durable fact stands without
it.

No real names, user paths, or ASCII banners; the `agent_docs/...`
strings in tests are realistic test data, not doc pointers.

### Error handling

**HIGH** — `raise` inside `except` without `from e`/`from None`
throughout the new package: `journal.py:190`, `manifest.py:207,213`,
`review.py:69,73`, `trust.py:43`, `main.py:55,66,126,156`. The style
guide marks exception chaining IMPORTANT; there are zero
`raise ... from` in the package.

**MEDIUM** — subprocess I/O without timeouts: gate verification
commands and git helpers (`gates.py:29-72`), plus inherited stdin (see
Correctness). `tui/app.py:66-74` swallows all exceptions including
journal corruption. `review_spawn.py:101,115-117` uses
`RuntimeError` as internal control flow caught by its own broad
`except Exception`.

### Security & secrets

No issues found. Worker commands are argv lists rendered by literal
placeholder substitution (no shell); hook commands `shlex.quote` their
paths; the backend renderer shell-quotes each launch arg individually
with hostile-input tests; API-level count/length/printable validation;
no secrets logged. `shell=True` for manifest verification commands and
`--dangerously-skip-permissions` for workers are explicit, documented
trust decisions consistent with the spec.

### Type safety

**MEDIUM** — `scheduler.py:124`: `findings_list: tuple[object, ...]`
consumed via `getattr(finding, "task_id", None)` duck-typing — an
ad-hoc shape where the existing `review.Finding` model fits (move it to
a leaf module to break the import cycle). Signal events flow through
the launch path as unparameterized `dict`
(`launcher.py:55,91`, `executor.py:163,332`) probed with `.get()`; the
schema is fixed by `append_signal.py` and fits a small pydantic model.

**LOW** — `run.py:231` / `tui/app.py:110`: untyped `**kwargs`
passthroughs defeat checking of `execute_plan`'s keyword contract;
`attempt.py:57` / `trust.py:36`: unparameterized `dict` returns. The
only two type-suppressions in the diff are justified.

### Backwards compatibility

No issues found. `CreateAgentRequest.launch_args` is optional/additive
(frontend contract regenerated; frozen pydantic schemas updated via the
sanctioned mechanism); the `{args}` placeholder is opt-in per
registration and validated at load; pre-manifest plan folders are
explicitly unsupported with a documented re-plan path (architecture's
migration strategy, restated in the plan skill).

### Frontend issues

No `.tsx`/frontend changes in the diff — not applicable.

### Integration test issues

No changes under `sculptor/tests/integration/` — not applicable.

### Style guide & ratchets

**HIGH** — systemic `@dataclass` use where the backend style guide says
"Never use dataclasses or named tuples — use pydantic models instead"
(`docs/development/style/backend.md:341,624`): `scheduler.py:22,101,116`,
`attempt.py:47`, `dag.py:26,38`, `review.py:102`, `ratelimit.py:37`,
`run.py:201`, `ladder.py:22-48`, and `bundled.py:34` (`_Bundle`) inside
sculptor proper. Pydantic is already a dependency and used for the
manifest/journal models; `tools/sculpt` (the stated precedent package)
contains zero dataclasses. If the team wants dataclasses for internal
value types in `tools/`, that's a style-guide amendment to make
explicitly, not silently.

**MEDIUM** — if/elif chains over closed unions without exhaustiveness
(`scheduler.py:479-515`, `journal.py:257-324` — no `assert_never` or
raising `else`); mutation of list/dict/set parameters
(`manifest.py:144`, `registrations.py:142`, `dag.py:123`,
`gates.py:62`, `executor.py:75`, `app.py` `_validate_launch_args`);
nested function definitions throughout (`executor.py:151,163,320,332` —
the duplicated `on_spawn`/`on_signal` pairs would be cleaner as
methods; `launcher.py:298`; `registrations.py:124`; `run.py:137,241`;
`tui/app.py:247,263`); no loguru anywhere in the package (diagnostics
via `print(..., file=sys.stderr)`); `time.sleep(0.05)` retry with a
magic number inside `tui/app.py:67-74`.

**LOW** — booleans without `is_`/`has_` prefixes
(`AttemptResult.ok`, `start_run`); `drilldown.py:124`
`failed_gates` actually selects *finished* gates; single-letter
comprehension variables; a function-body import in `main.py:60`
justified but missing the conventional `# noqa`.

Ratchets: `just check` passes — no ratchet regressions.

### Git hygiene

No issues found. 23 atomic commits, one per plan task, each with a
substantive why-focused body including verification evidence and (for
7.4) a manual live demo record.

### Public-facing text

No issues found. Commit messages contain no PII, secrets, internal
hostnames, or user paths (scanned mechanically and read); the
`Co-authored-by: Sculptor` trailer is the repo convention.

### Checklist summary

- The change accomplishes the stated goal: increment 1 of the
  workflow-build-coordinator spec is fully delivered, replacing `/build`
  outright. (The one gap found — the per-task escalation override — was
  closed in the fix pass, `b2ff9c7a`.)
- The blocking items identified here (stale-state rerun, journal
  poisoning, process leaks) were all fixed with regression tests; see
  the Resolution log above.

## Post-review field test (nested dev instance)

A live run through a `just start` dev instance surfaced one incident:
the Coordinator tab appeared stuck on node 1.1 "running" although the
worker had committed and written its `Stop`. Investigation (journal,
file mtimes, process table, backend logs, terminal buffer) showed two
compounding causes, both now fixed in `a5554cf3`:

- **The observing coordinator died mid-run** (~100s in) without
  cleanup; its worker — correctly isolated in its own process session —
  finished 7 minutes later, unobserved. The likely trigger: Textual's
  built-in priority Ctrl+C binding quits the app immediately,
  bypassing the TUI's quit-when-idle guard. Ctrl+C now routes through
  the same guard as `q`.
- **A relaunched `coordinator run` in the same tab hit the
  stale-state guard** (correctly — that's the CRITICAL fix working)
  and its dashboard rendered the last snapshot: 1.1 eternally
  "running". Separately, resume would have *discarded* the completed
  attempt and re-run the task, which would then fail the
  produced-no-commit gate. Resume now records each attempt's base
  commit in the journal and inspects the attempt dir's
  `signals.jsonl`: an attempt that reached `Stop` re-enters at its
  gates (`resume-gates`) instead of being redone. Old journals without
  a base commit keep the discard behavior.

Also fixed from the same evidence: the status bar redrew every 0.5s
tick even when unchanged, flooding the tab's PTY stream (~1MB of
identical repaints observed in the terminal buffer).

## Overall Assessment

This is a strong, well-tested implementation of increment 1. Every
requirement in scope is implemented and almost all are verifiably
covered by focused tests — the fake-worker e2e suite in particular
exercises the real launcher, real git, and real signal files with no
LLM in the loop, and the resume/kill/reap paths have genuine
never-rerun proofs. The Sculptor-side `{args}` plumbing is small,
layered, and defensively validated, and the skill rework (manifest
emission, `/build` deletion, Q&A dedup) landed coherently.

The biggest risk at review time was **state-lifecycle robustness around
edges the happy path never hits**: rerunning a plan that already has
state (CRITICAL), resuming after a crash that truncated the journal
(HIGH), and process leaks when the observe loop throws or a reviewer is
mid-flight at crash time (HIGH). All of those — and every other finding
except three consciously declined LOWs — were fixed and committed in
the post-review pass (`18cf7de2` through `960715c2`, see the Resolution
log), each gated on the full verification suite. The coordinator test
count grew from 205 to 225 in the process.

Remaining follow-ups are increment-2 scope, not defects: the
interactive-node pipeline, the finalize-signal contract, and worktree
parallelism, plus the known opt-in-only coverage of the real-Claude
hooks contract.
