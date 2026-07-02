# Sculptor Slim — Review

## Fixes Applied (post-review)

After the review, the findings were addressed in two commits (`just check` and
`just test-unit` green after each):

- **`3d78bfed7d`** — Removed the Experimental settings section and its three
  spec-listed flags (REQ-EXP-1, finding H1), plus the cascaded dead
  experimental/Pi settings element IDs, their POMs, the dead `enableEntityMentions`
  helper, and the unused `isTelemetryEnabled` atom.
- **`44d1f52c71`** — Fixed the "clone" mislabel (H4) and removed the dead
  mode-badge chain (M4); repointed the broken Storybook import (H3); gave the CI
  Babysitter no-prior-agent case its own disabled reason and dropped its dead
  `config` param (M1); fixed the stale `sculpt run --harness` help text; removed
  orphaned/dead artifacts (the ReportProblemPopover stylesheet, `compute_pi_pin`
  script + recipe, the `enablePiAgent` reset).

**Not auto-fixed (deliberate):**
- **H2 (initial-prompt drop)** — a fix was prototyped (reject the prompt-ful
  create when it resolves to a terminal agent) but **reverted**: it changes an
  established, tested contract (`test_create_task_creates_task` asserts
  `POST /tasks` with a prompt + omitted type returns 200 and creates an agent).
  Whether to (a) reject prompt-ful creation, or (b) actually deliver the prompt
  to the terminal agent on connect, is a product decision, not a clean review
  fix. Left as a finding for the owner — see H2 below. (The stale CLI help text
  *was* fixed.)
- **M2 unused deps**, **M3 backend telemetry/consent plumbing**, and the
  remaining **LOW** dead-code/comment items were left as documented residuals
  (lockfile risk for the deps; M3 is plausibly intentional; the LOW items are
  inert). See those sections.

## Summary

- **The slim-down largely meets the spec.** All the big subsystem removals
  landed cleanly: rich Claude/Pi agents, chat-alpha render tree, telemetry
  (PostHog/Sentry), report-a-problem, auto-update, custom backend + container
  runtime, dependency management, the theme builder, dnd-kit panels, and
  clone/in-place workspaces are gone, with the core (worktree workspaces,
  multi-agent, terminal panel, diff viewer, PR tracking, CI Babysitter)
  intact. `just check` and `just test-unit` both pass green.
- **The test triage was honored well** (169/169 DELETE, 33/33 KEEP, 73/77
  REWRITE), the fresh-start DB guard + its startup test are correct, and the
  babysitter rewire to the bundled `claude-code` fallback is implemented
  exactly as designed.
- **Four things to address before merging:** (1) **REQ-EXP-1 is only
  partially met** — the Experimental settings section and three of its flags
  survive; (2) a **HIGH correctness regression** — a prompt-ful create with
  an omitted agent type (reachable via `sculpt run`) silently drops the
  initial prompt; (3) a **broken Storybook import** to the deleted
  `themeBuilder.ts`; (4) a **user-visible mislabel** — every closed worktree
  workspace now renders as "clone".
- **Nothing here is a data-loss or security risk.** The HIGH items are a
  dropped CLI prompt, a dev-tool build break, a wrong label, and a missed
  removal — all fixable without rework of the architecture.

## Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-WS-1/2/3 | Covered | `AddWorkspacePage.tsx:236` hardcodes `WORKTREE`; branch required `app.py:669`; mode selector + `enable_in_place/clone_workspaces` flags gone |
| REQ-WS-4 | Covered | `database/workspace_enums.py:8-14` WORKTREE-only; fresh-start guard `utils/migration.py` + test `migration_test.py:60-93` |
| REQ-BACKEND-1/2 | Covered | custom-backend cmd/store keys/IPC + `AdvancedSection.tsx` removed; `electron/main.ts:149` always spawns local |
| REQ-BACKEND-3 | Covered | `container/recipes/docker/` runtime artifacts deleted; build/CI infra correctly retained (out of scope) |
| REQ-AGENT-1 | Covered | `interfaces/agents/agent.py:538` union = Terminal/Registered only |
| REQ-AGENT-2 | Covered | registry loads `~/.sculptor/terminal_agents/*.toml` (kept) |
| REQ-AGENT-3 | Covered (see finding H2) | bundled `claude-code` installed `web/app.py:393`; new-agent default `app.py:1654`. But the prompt-ful default path strands the prompt — finding H2 |
| REQ-AGENT-4 | Covered | `claude_code_sdk/`, `pi_agent/`, `hello_agent/`, MCP server, btw all deleted; no dangling imports |
| REQ-AGENT-5 | Covered | `web/data_types.py:36` AgentTypeName = TERMINAL/REGISTERED; no `.CLAUDE/.PI`/`enable_pi_agent` |
| REQ-CHAT-1 | Covered | `chat-alpha/` tree + ChatInput/AUQ/QueuedMessages/BtwPopup deleted; `ChatPanelContent.tsx:30` renders terminal unconditionally |
| REQ-CHAT-2 | Covered | `btw_service`, `btw_process_manager`, `/api/v1/btw` removed |
| REQ-CHAT-3 | Covered | `web/message_conversion.py` deleted; terminal PTY path intact |
| REQ-TEL-1 | Partial | `Telemetry.ts`/`Analytics.ts` + capture sites + endpoints gone, BUT `posthog-js` dep still declared (`package.json:107`), dead `isTelemetryEnabledAtom` (`userConfig.ts:73`), and backend `TelemetryInfo`/consent plumbing survives wired to onboarding email endpoints — finding M4/M5 |
| REQ-TEL-2 | Partial | Sentry init/replay/`instrument.ts` gone, vanilla error boundary `App.tsx:25`, BUT `@sentry/react` still in `package.json:54` (req says it should be gone) |
| REQ-TEL-3 | Covered | `ReportProblemPopover.tsx`, `reportProblem.ts`, `upload_diagnostics.py`, endpoint removed (orphan `.module.scss` only) |
| REQ-TEL-4 | Covered | no posthog/sentry/s3/update outbound remains; tracing flushes to local backend only |
| REQ-UPD-1 | Covered | `autoUpdater.ts`, `useInstallUpdate.ts`, `AutoUpdateToasts.tsx`, `auto_update_mock.py`, IPC + poll all gone |
| REQ-DEP-1 | Covered | `dependency_management_service.py` + `managed_tools.py` deleted; PATH-only via `shutil.which` (`app.py:2629/2649`, `v1.py:165`) |
| REQ-DEP-2 | Covered | deps settings + `DependencyPaths`/`DependencyInfo` + `InstallationStep`/`DependencyCard` removed |
| REQ-ONB-1/2 | Covered (minor leftover) | `OnboardingWizard.tsx:15-23` = PATH_CHECK → ADD_REPO; `PathCheckStep.tsx` read-only. Backend email/skip endpoints survive but are no longer wired to the UI — finding L (leftover) |
| REQ-THEME-1 | Covered (see finding H3) | builder section/atoms/pickers deleted; `useThemeBuilder.ts`→`useTheme.ts`. But `.storybook/preview.tsx:8` still imports the deleted atom — finding H3 |
| REQ-THEME-2 | Covered | `themeAppearanceAtom` (`atoms/theme.ts:83`) + `useResolvedTheme()` survive |
| REQ-PANEL-1/2/3 | Covered | `DockingLayout.tsx` de-dnd-kit'd; `ResizeHandle` + show/hide atoms kept; `@dnd-kit` legitimately retained for TabBar/Actions |
| REQ-EXP-1 | Covered (fixed post-review, `3d78bfed7d`) | plugins system + 6 flags removed at review time; the surviving Experimental section + the three remaining flags were removed in the post-review fix (finding H1) |
| REQ-TEST-1 | Covered | per-file triage in `test-triage.md`; classification honored (see Test Coverage) |
| REQ-TEST-2 | Covered (4 gaps) | 73/77 REWRITE files re-expressed off FakeClaude; 4 left unchanged (pass via terminal-first helper) — finding L |
| REQ-TEST-3 | Covered | `fake_claude*`, `fake_pi*`, `fake_claude_pause`, `real_pi/`, rich `real_claude/` removed; no surviving references |
| REQ-TEST-4 | Covered | `testing/fake_terminal_agent.py` + `_runner.py` + harness test added; side-effecting DSL + lifecycle signals only |
| REQ-TEST-5 | Covered | `just test-unit` green; no references to removed agent types/fakes/rich-chat |
| REQ-CORE-1/2/4 | Covered | worktree mgmt, multi-agent, terminal, diff/file viewer, PR tracking intact |
| REQ-CORE-3 | Covered | `coordinator.py:487-504` returns `DriveableTerminal(claude-code)` on no-MRU; bare shell MRU stays `Disabled`; `ChatAgent`/Claude/Pi arms removed |

## User Scenarios

- **First run (onboarding):** Delivered. `OnboardingWizard.tsx` is now a
  single read-only `PathCheckStep` (checks `claude`/`git` via
  `GET /api/v1/tool-availability` → `shutil.which`) then `AddRepoStep`. No
  installer, no email/consent. Covered by the rewritten `test_onboarding.py`
  and `test_missing_claude_binary.py` (drives the missing-tool case by
  filtering `PATH`, not host state).
- **Creating a worktree workspace:** Delivered. The add-workspace page has no
  mode selector and requires a branch (`AddWorkspacePage.tsx`); backend
  enforces both. Covered by `test_worktree_create_happy_path.py` (KEEP) and
  `test_worktree_edge_cases.py` (trimmed).
- **Running multiple agents:** Delivered for the in-app "+" path (sends an
  explicit type, defaults to bundled `claude-code`). **However** the
  prompt-ful create path (omitted type + initial prompt, reachable via
  `sculpt run`) silently drops the prompt — see finding **H2**. Multi-agent
  lifecycle covered by `test_multi_agent_workspace.py`.
- **Terminal-only agent surface:** Delivered. No structured chat UI remains;
  `ChatPanelContent` renders `AgentTerminalPanel` unconditionally.
- **PR tracking + CI Babysitter:** Delivered and behaviorally preserved. The
  babysitter falls back to a bundled-`claude-code` `DriveableTerminal` so it
  still advances PRs on empty workspaces. Covered by `test_ci_babysitter.py`
  (rewritten) and `test_backend_pr_polling.py` (KEEP, though not rewritten).
- **Toggling/resizing panels:** Delivered. Fixed slots; resize + show/hide
  survive; drag/reorder gone. Covered by `test_side_toggle.py`,
  `test_zen_mode.py` (KEEP).
- **Settings, slimmed:** *Mostly* delivered — theme builder, dependencies,
  telemetry/privacy, advanced/custom-backend sections gone, but the
  **Experimental section is still present** (finding **H1**).
- **No data leaves the machine:** Delivered. Only GitHub + Anthropic outbound
  remain; unused `@sentry/react`/`posthog-js` deps linger but are not invoked.
- **Upgrading from an older install (clean break):** Delivered. The
  fresh-start guard (`migration.py`) moves a pre-slim `internal/`+`workspaces/`
  aside before the DB is opened, so removed enum values never deserialize.
  Asserted by `migration_test.py:60-93`.

## Test Coverage

- **Tests added:** `testing/fake_terminal_agent.py`, `_runner.py`,
  `_test.py`; `tasks/handlers/run_terminal_agent/runner_support.py`;
  `tests/integration/frontend/test_fake_terminal_agent_harness.py`;
  `common/state/atoms/theme.ts` + `theme.test.ts`; `migration_test.py` new
  fresh-start cases; `components/fileDisambiguation.ts`;
  `onboarding-wizard/PathCheckStep.tsx`.
- **Test suite status:** PASS. `just test-unit` → backend/frontend/foundation/
  sculpt all OK; `just check` → lint/ratchets/typecheck/file-hygiene all OK.
- **Integration tests:** The full Playwright integration suite was **not
  re-run by Review** (hundreds of files, heavy + known-flaky under
  parallelism). Task 99.1 reports it greened, and `just check`/`just
  test-unit` pass. Spot-checks confirm the rewritten tests collect against
  the new harness and contain no `fake_claude`/AUQ references.
- **Triage honored:** 169/169 DELETE files deleted; 33/33 KEEP survive;
  73/77 REWRITE modified. **4 REWRITE-classified files were left byte-identical
  to main** — `test_backend_pr_polling.py`, `test_keybindings.py`,
  `test_pr_button_errors.py`, `test_pr_management.py`. None import the removed
  fake (they drive via the now-terminal-first `start_task_and_wait_for_ready`),
  so they still collect/pass — but the triage intended them re-expressed.
- **Skipped/xfail:** Only one skip added —
  `test_project_path_monitoring.py:16` `@pytest.mark.skip(reason="Flakey
  (PROD-2871)")`. Justified by a tracking ticket, but it leaves the
  project-path-moved monitor with no active e2e coverage; confirm the
  worktree-edge missing-repo case is adequate interim coverage.
- **Semantic weakening (MEDIUM):** `test_regression_replay_on_restart.py` no
  longer exercises an *interrupted* turn — it runs a `write_file` to
  completion before restart and asserts only that the agent reaches READY. It
  can no longer catch a prompt *replay*, despite its name/`@user_story`. It is
  now near-redundant with `test_regression_queued_messages_after_restart.py`
  (which does park mid-turn). Consider retitling/merging.
- **Flake risk (MEDIUM):** `test_ci_babysitter.py` relies on 20–25s
  wall-clock waits (`_BASELINE_POLL_SETTLE_MS`, `_MERGED_MODE_STABLE_WAIT_MS`)
  to absorb poll latency and prove negatives via one-shot terminal-buffer
  snapshots — inherently the "wall-clock treadmill" pattern, hard to fix
  without a poll-observed signal.

## Code Review Findings

The repo's configured skill `/code-review-checklist` was run (scoped to the
modified/added files; the diff is 573 deletions / 301 modifications / 13
additions). Findings, by severity:

### HIGH

**H1 — RESOLVED (`3d78bfed7d`). REQ-EXP-1 not fully met: the Experimental settings section survived.**
`pages/settings/sections.ts:135` still registers `SettingsSection.EXPERIMENTAL`
and `SettingsPage.tsx:265-323` renders four toggles, three of which the spec
names for removal and which now gate already-removed features:
`is_always_interrupt_and_send` (`user_config.py:181`; queued messages gone),
`enable_entity_mentions` (`user_config.py:209`; @-mentions gone),
`enable_rich_markdown_rendering` (`user_config.py:213`). The plugins system and
the other six flags *were* removed correctly. Either delete the section + these
three flags (backend field, atom, generated type, UI row) or amend the
requirement if they were intentionally kept.

**H2 — NOT auto-fixed (product decision). Prompt-ful create with an omitted
agent type silently drops the initial prompt.** `web/app.py:534-548`: an *explicit* `TERMINAL`/`REGISTERED` type with
a prompt is rejected (422), but an *omitted* type resolves to the bundled
`claude-code` registered terminal agent and then persists a
`ChatInputUserMessage` (`app.py:595`). The terminal handler has **no
message-queue subscription** (`run_terminal_agent/v1.py:1-14` docstring), and
nothing delivers that persisted message to the PTY — `deliver_prompt_to_terminal_agent`
is only called from the input endpoint (`app.py:3394`) and the babysitter, not
from `start_task`. So the prompt is created and never delivered. This is
reachable today via **`sculpt run "<prompt>"`** with an omitted `--harness`
(`run.py:130-141` sends `agent_type=UNSET` → server resolves to registered →
prompt stranded). Relatedly, `sculpt run` is now semantically unsatisfiable in
the terminal-only world (it "always sends a prompt" but every harness is a
terminal that can't take one), and its `--harness` help still references the
removed "Claude or Pi" / "falling back to Claude" (`run.py:60-63`). Fix:
deliver the initial prompt to the resolved registered agent via the PTY seam,
or reject the omitted-type-plus-prompt case explicitly; and reconcile/retire
`sculpt run` for terminal-only. **A reject-based fix was prototyped and
reverted** because it changes a tested contract
(`app_basic_test.py::test_create_task_creates_task` asserts a 200 + created
agent for exactly this request); the resolution is a product call left to the
owner. The stale `--harness` help text was fixed (`44d1f52c71`).

**H3 — RESOLVED (`44d1f52c71`). Broken Storybook import to a deleted module.**
`sculptor/frontend/.storybook/preview.tsx:8` still
`import { themeBuilderSettingsAtom } from "../src/common/state/atoms/themeBuilder.ts"`
and uses it at line 58, but `themeBuilder.ts` was deleted (replaced by
`theme.ts`, which exports `themeSettingsAtom`). This breaks any Storybook
build/typecheck. It is dev-only and not caught by `just check` (Storybook is
not in the check pipeline). Repoint to `themeSettingsAtom` from
`atoms/theme.ts`.

**H4 — RESOLVED (`44d1f52c71`). Every closed worktree workspace was mislabeled "clone".**
`components/ClosedWorkspaceRow.tsx:25-27`
`formatInitStrategy = (s) => s === "IN_PLACE" ? "in-place" : "clone"` now
falls through to `"clone"` for every row, because
`WorkspaceInitializationStrategy` is WORKTREE-only. The file was not touched by
the branch, so the enum collapse silently broke its label. User-visible. Fix:
drop the strategy from the meta line or return `"worktree"`.

### MEDIUM

**M1 — RESOLVED (`44d1f52c71`). Dead/misleading babysitter surface.** `coordinator.py` threads a now-unused
`config: UserConfig` through `_run_terminal_drive`/`deliver_prompt_to_agent`
(the chat branch that read it is gone). And `_DISABLED_REASON_MRU_NON_DRIVEABLE`
("Your most-recent agent is a terminal that can't receive automated prompts…")
is shown even on the new no-prior-agent / bundled-registration-absent path,
where there is no most-recent agent at all.

**M2 — Unused frontend deps + dead atom.** PARTIALLY RESOLVED (`3d78bfed7d`):
the dead `isTelemetryEnabledAtom` was removed. STILL RESIDUAL: `package.json`
declares `@sentry/react` and `posthog-js` with zero imports; REQ-TEL-2 wants
`@sentry/*` gone. Left because removing a dep requires a lockfile regen, which
`just check`'s frozen-lockfile install would otherwise fail — best done as its
own change.

**M3 — Backend telemetry/consent plumbing survives.** `telemetry/telemetry.py`
(`TelemetryInfo`), `services/user_config/telemetry_info.py`, and consent flags
(`is_telemetry_level_set`, `get_privacy_settings_for_telemetry`) remain and are
still served from the onboarding email/skip endpoints (`app.py` POST
`/api/v1/config/email`, `/skip_account`). The `telemetry.py` docstring frames
this as intentional ("frontend owns telemetry reporting"), but it does not
match REQ-TEL-1's "consent settings/flags removed," and the email endpoints are
no longer reachable from the slimmed onboarding UI (REQ-ONB-2 removed email
confirmation). Confirm intent or remove.

**M4 — RESOLVED (`44d1f52c71`). Dead init-strategy mode-badge chain.** `WorkspaceBanner.tsx:137-141`
`shouldShowModeBadge = strategy !== WORKTREE` is now always false; the badge in
`RepoSegment.tsx:151-155`, the single-entry `MODE_BADGE_LABEL` record, and the
threaded `strategy`/`shouldShowModeBadge` props are inert. End state is correct
(no badge) but this is exactly the dead logic the slim-down meant to remove.

### LOW

**L1 — Orphaned/dead artifacts.** PARTIALLY RESOLVED (`44d1f52c71`):
`ReportProblemPopover.module.scss`, `scripts/compute_pi_pin.py` + its `justfile`
recipe, and the `enablePiAgent` reset were removed. STILL RESIDUAL (inert,
deferred): stale `ElementIDs` constants in `constants.py` (`BTW_POPUP*`,
`ASK_USER_QUESTION_*`, `ALPHA_CHAT_*`, `EXIT_PLAN_MODE_TOOL_BLOCK`); orphaned
POMs `testing/elements/alpha_chat_view.py` and `ask_user_question.py`; dead
`ALPHA_CHAT_*` query methods in `testing/elements/chat_panel.py`; the dead
`install-pi`/`test-real-pi` justfile targets (the former imports the deleted
`dependency_management_service`, but it is opt-in and not wired into
`install`/`rebuild`); the dead `dependencies`/`privacy` nav POM methods.

**L2 — Vestigial backend guards after the union collapse.**
`is_terminal_agent_config` (`interfaces/agents/agent.py:547`) is now trivially
True, so `if not is_terminal_agent_config(...)` branches in `web/app.py`
(`:1929/3325/3385/3440`) and `web/derived.py:486` are dead; the `has_prompt`
param across `app.py` resolvers is vestigial (honestly documented);
`harness_registry.create_agent_for_run` is now an always-raising guard stub.
Keeping the explicit-invariant asserts is defensible; the dead `if` branches
are not.

**L3 — Dead panel markup/props.** `LeftSidebar.tsx:12`/`RightSidebar.tsx:12`
still render `data-droppable-id` (only the deleted DnD used it; now kept alive
by test helpers); `PanelContextMenu.tsx:7-14` accepts a `zoneId` it no longer
reads.

**L4 — Stale comments/docstrings.** `worktree_strategy.py:3` ("Mirrors
clone_strategy.py" — deleted), `app_basic_test.py:114` ("Create an IN_PLACE
workspace" — code uses WORKTREE), `GlobalDefaultsSection.tsx:38` ("clone and
worktree"), `sections.ts:65/129-130` (stale "updates"/"telemetry" keywords),
`panels/atoms.ts:16-19` ("drag-and-drop"/"drop frame"), `user_config.py:33`
("e.g. through PostHog"), `app.py:2682` ("diagnostics uploads").

**L5 — Minor test concerns.** `test_worktree_edge_cases.py:44/80` lower the
Playwright timeout to 5_000 on an async round-trip; `:37` uses a fixed
`wait_for_timeout(500)`; `test_custom_actions.py:318-324` asserts ordering via
`bounding_box()` y-coords (borderline `no_layout_only_tests`, but sits beside
behavioral assertions).

### Categories with no issues

No secrets/credentials in code or commit messages. No bare `except:`/swallowed
errors introduced. Commit messages are atomic, task-scoped, and clean of PII /
internal-only leakage (Linear ticket IDs only, no private contents). The
fresh-start guard and the `fake_terminal_agent_runner` subprocess/signal
lifecycle were reviewed for resource leaks and are sound (try/finally always
emits the done-marker + idle signal; atomic temp+rename for command files).

## Overall Assessment

**Close to merge.** This is a disciplined, large-scale removal that hits the
spec's intent and keeps the core working, with green unit/check suites and a
faithfully-honored test triage. Post-review, **H1, H3, H4, M1, M4** and several
LOW items were fixed in `3d78bfed7d` + `44d1f52c71` (both leave `just check`
and `just test-unit` green). **One finding remains for the owner: H2** — a
prompt-ful create (reachable via `sculpt run`) silently drops the initial
prompt. A reject-based fix was reverted because it changes a tested contract;
the resolution (reject vs. actually deliver the prompt) is a product decision.
Residual LOW/MEDIUM items (unused `@sentry`/`posthog` deps, backend
telemetry/consent plumbing, stale dead `ALPHA_*` ElementIDs and POMs, dead
`install-pi`/`test-real-pi` justfile targets, stale comments) are inert and
left as documented follow-ups. The biggest remaining risk is the integration
suite, which Review did not fully re-run; a targeted CI run of the rewritten
babysitter/restart/PR tests — and a manual check that the slimmed Experimental
section is gone from Settings — is recommended before merge.
