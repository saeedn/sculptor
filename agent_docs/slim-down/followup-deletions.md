# Slim-down follow-up deletions

Items the initial slim-down (see `spec.md`) missed. This doc inventories
each remaining vestige and gives execution notes so the deletions can be
done deliberately. Grouped by the three areas called out in the
follow-up request, plus a fourth section of vestiges surfaced by a fresh
sweep.

Status legend: **DELETE** (clearly dead / out of scope for the slimmed
product) · **DECIDE** (genuine choice about depth) · **KEEP** (looks
related but is legitimately still used — called out so we don't delete it
by mistake).

---

## Execution status (2026-06-25)

**Done & committed:**
1. Dead chat keybindings + chat-search state (§3) — the whole `chat`
   keybinding category, `focus_input`/`chat_search`, the chatSearch
   atoms, and the command-palette chat plumbing.
2. Orphaned chat-input components (§4a).
3. **Settings → Agent page** and **Settings → Privacy page** removed
   (§1a/1b/1f, §2a/2d): both sections, the dead frontend agent-behavior
   code (model/fast-mode/effort components + atoms + per-task draft
   store), the email atoms/AccountFieldRow, and the Agent/Privacy
   ElementIds + Playwright POMs.

**Also done & committed (consolidated backend pass):**
- **Backend agent-behavior plumbing** (§1c/1d/1e): removed `LLMModel`/
  `EffortLevel` enums, the `model`/`fast_mode`/`effort` request & message
  fields, `AgentTaskInputsV2.default_model`, the dead task-view computed
  fields (`model`, `is_smooth_streaming_supported`), `MODEL_SHORTNAME_MAP`,
  and the `default_llm`/`default_fast_mode`/`default_effort_level`/
  `is_smooth_streaming_enabled` config fields. Frozen JSON schemas
  refreshed (field removal is backward-compatible — no data migration).
  Frontend fallout fixed; the sculpt CLI `--model` option removed across
  `run`/`agent create`/`agent send`.
- **Smooth-streaming frontend layer** (§4c): `useChatData`,
  `useSmoothStreaming*`, `smoothStreaming` atoms removed.

**Also done & committed:**
- **Email-on-startup surface** (§2b): removed `user_email` + the
  email-derived identity fields (`user_id`/`organization_id`/
  `user_full_name`), the `email`/`skip_account` endpoints,
  `EmailConfigRequest`/`SkipAccountSetupRequest`, email validation, and
  `has_email`. The onboarding-completion gate (the privacy-consent flag)
  and `TelemetryInfo` are kept intact; test fixtures updated.
- **Dead mention/suggestion system** (§4b): detached the `Mention`
  extension + all suggestion wiring from `Editor`/`TipTapConfig` (leaving
  a plain rich-text editor) and deleted the orphaned cluster
  (EntityMention*, Mention*, mentionDetailPanes, mentionDetails,
  SkillSuggestion/SkillList, SuggestionUtils/DismissalPlugin/
  ListContainer/SplitSuggestionLayout, fuzzyFileScorer). `skillBadge`,
  `SkillHoverContent` (live SkillsPanel) and `FileUploadUtils` kept.

**Also done & committed (second pass):**
- **Telemetry-consent fields + dead telemetry plumbing** — removed the 5
  consent fields, `PrivacySettings`, `get_privacy_settings_for_telemetry`/
  `canonicalize_telemetry_flags`, and the orphaned `TelemetryInfo` /
  `telemetry_info.py`. **Onboarding gate rewired**: completion is now
  implied by having a project (`RequireOnboarding` gates on `hasProject`;
  `get_config_status` dropped `has_privacy_consent`).
- **The model-switcher infra** — removed `ModelOption`, the harness
  `get_available_models`/`get_selected_model_id` + `supports_model_selection`
  capability, `AgentTaskStateV2.available_models`/`current_model`,
  `ModelsAvailableAgentMessage`, `SetModelUserMessage`, the `set_model`
  endpoint, `TaskService.update_available_models`, the derived task-view
  fields, and `PiSetModelError`. Frozen schemas refreshed.
- **Integration suite** — triaged against the removals: deleted dead POMs
  (`task_starter`, `chat_panel`, `chat_search_bar`, `entity_picker`) and
  helpers (`insert_mention_into_tiptap`, `get_mention_span`,
  `expect_chat_replaces_terminal_panel`, `get_chat_panel`,
  `enable_default_fast_mode`), removed the obsolete skill-mention test and
  the pi `harness` fixture, and rewrote the onboarding test for the new
  gate. Also dropped the obsolete `Cmd+I` focus test (the `focus_input`
  keybinding was removed) and stripped `--model`/`model` from the sculpt
  CLI integration tests (the CLI lost its `--model` option). A full
  `RUN_ALL=1` pass of `frontend` + `regression` (425 tests) is green
  **except** one pre-existing failure (see below).

**Fixed: `test_restarts.py::test_chats_persist_on_restart`.**
- It failed deterministically — the relaunched terminal showed the launch
  banner instead of `RESUMED-…` (`terminal_session_id` None on resume). Root
  cause was in the slim-down's *rewrite of this test*, not the product: the
  test gated readiness on the agent tab dot settling (the `idle` signal) as a
  proxy for "the session id reached the backend," but the dot can read
  read/unread before the `session-id` signal is processed, so teardown raced
  persistence. The resume feature itself is sound — `test_registered_terminal_
  agent_resumes_after_restart` exercises it and passes by gating on an explicit
  post-signal terminal marker. Fix adopts the same pattern: the fake runner now
  prints `SESSION-REPORTED-<id>` right after its blocking `sculpt signal
  session-id` returns, and the test waits for that marker. Full suite green.

**Genuinely remaining (one cohesive follow-up — the dead chat render layer):**
- The `chat-alpha/` render tree leftovers (`AlphaMarkdownBlock`, the
  `alpha_chat_view` POM), plan-mode (`enter_plan_mode`/`exit_plan_mode` +
  `PLAN_MODE_TOGGLE`/`EXIT_PLAN_MODE_TOOL_BLOCK`), and the now-inert
  ElementId string constants for all the removed chat/mention/model surface
  (`MODEL_SELECTOR`, `MENTION_*`, `ENTITY_MENTION_*`, `CHAT_PANEL`,
  `CHAT_SEARCH_*`, `ALPHA_CHAT_*`, etc.). These are inert (enum strings /
  unmounted components) and entangled with each other, so they want one
  deliberate leaf-first removal rather than a piecemeal pass.

---

## Execution status (2026-06-26) — orphan sweep

A fresh evidence-based dead-code sweep (verifying zero live inbound
references) cleared the unambiguous, independent leftovers in four
reviewable commits:

1. **Backend `DefaultAgentWrapper` cluster** — the rich-agent message-loop
   wrapper is unreachable now the product is terminal-agent-only (nothing
   constructs/subclasses it outside its own test; the live path is
   `agents/terminal_agent` + `tasks/handlers/run_terminal_agent`). Deleted
   `agents/default/{agent_wrapper.py,agent_wrapper_test.py,utils.py,
   errors.py}` and trimmed `agents/default/constants.py` to just
   `WORKTREE_MODE_PROMPT` (dropping `ENTITY_MENTIONS_SYSTEM_PROMPT`,
   `DEFAULT_WAIT_TIMEOUT`, `REMOVED_MESSAGE_IDS_STATE_FILE`,
   `FILE_CHANGE_TOOL_NAMES`).
2. **Dead task-capability hooks/atoms** — 12 unused `useTaskHelpers`
   selectors + their `atoms/tasks.ts` atomFamilies + the orphaned
   `tasks.test.ts` cases. Kept status/skills/interruption/automated-prompts.
3. **Dead test POMs + ElementIds** — deleted the unimported
   `alpha_chat_view` / `alpha_prompt_navigator` / `settings_update` /
   `agent_tasks_popover` POMs (note: `agent_tasks_popover` was a *fourth*
   dead POM not previously listed — it was the only referrer of
   `STATUS_PILL`). Removed the model/effort/fast-mode, mention, and
   chat-alpha (`ALPHA_CHAT_*`/`STATUS_PILL*`/`TURN_FOOTER*`/
   `STREAMING_CURSOR`/`TOKEN_POPOVER`/`MENTION_LIST`/`MENTION_SPAN`)
   ElementIds; kept interleaved live ids (`ALPHA_JUMP_TO_BOTTOM_*`,
   `SCULPT_SENT_VIA_BADGE`, `DEBUG_CHAT_*`).
4. **Unused npm deps** — `@sentry/react`, `posthog-js`,
   `@tiptap/extension-mention`, `@tiptap/suggestion`, `fuse.js`,
   `remark-emoji`, `change-case` (28 packages total). depcheck
   false-positives (StarterKit-bundled `@tiptap/extension-*`, fontsource,
   `@radix-ui/colors`, playwright, electron-forge makers) intentionally kept.

`just format && just check && just test-unit` green after each.

### Plan-mode is NOT cleanly dead — DEFERRED (correction)

The earlier note above lumped plan-mode in with the inert chat surface.
That is **wrong / too hasty**, and the sweep confirmed why: terminal
agents have **no message stream** (every `TerminalHarness` capability is
`False`), so their waiting/busy state — *including plan mode* — is driven
by shell **hooks** (`claude-code-hooks.json`: `PreToolUse` on
`ExitPlanMode` → `sculpt signal waiting`), NOT by the Python `Harness`
message-parsing. The Python plan-mode cluster (`is_exit_plan_mode_tool`
and the other base-`Harness` stubs, `make_plan_approval_question`,
`PlanModeAgentMessage`/`is_in_plan_mode`, the `derived.py` WAITING
branches, the `enter_plan_mode`/`exit_plan_mode` request+message fields,
`EXIT_PLAN_MODE` tool name, `PLAN_MODE_TOGGLE`/`EXIT_PLAN_MODE_TOOL_BLOCK`
ElementIds, the `ToolInteractiveRole` "exit_plan_mode" literal) is
inert-but-entangled with the AskUserQuestion message-parsing path
and the deferred dead message-parsing layer. It wants the same deliberate
leaf-first pass as the rest of that layer, not a quick excision — so it
was left untouched this round.

### The AskUserQuestion path is ALSO dead — the whole message-parsing layer is (2026-06-26)

The follow-up note above guessed the AUQ path was "live." It is **not**.
Root cause, traced and confirmed: `AgentConfigTypes` has only
`TerminalAgentConfig` / `RegisteredTerminalAgentConfig`, so
`is_terminal_agent_config()` is **always true** and `create_agent_for_run()`
(harness_registry.py) **always raises** — no chat/message-loop `Agent` is
ever constructed. A terminal-agent task's stream contains only
`TerminalAgentSignalRunnerMessage` / `Environment*RunnerMessage` /
`RequestSuccessAgentMessage` / crash/killed messages / `ChatInputUserMessage`
/ `UpdatedArtifactAgentMessage`. The rich-loop stream
(`ResponseBlockAgentMessage`, `AskUserQuestionAgentMessage`,
`PlanModeAgentMessage`, tool blocks) is never produced. `derived.py::status`
hard-branches on `is_terminal_agent_config` → `scan_terminal_signal_state`,
so the AUQ parser (`_ready_or_waiting`) and the `waiting_detail` /
activity parsers are unreachable. The layer only *looked* alive because the
deadness is gated behind a runtime `isinstance` (not a removed branch),
`create_agent_for_run` survives as an always-raising guard, and the base
`Harness` still declared the (never-overridden) AUQ/plan tool methods.

**Removed this pass** (commit "remove the dead AUQ/plan message-parsing
path") — the dead PARSING only, preserving live API fields:
- `derived.py`: the non-terminal `status` branch, `_ready_or_waiting`,
  `_last_request_failed`, `_find_latest_activity`, `_describe_tool_use`,
  `_TOOL_DESCRIPTIONS`; `current_activity`/`last_activity`/`waiting_detail`
  gutted to `return None` (they always were None for terminal agents; the
  frontend workspace-peek reads the fields with fallbacks, so no API change).
  Deleted `derived_activity_test.py` (tested the gutted behavior).
- `interfaces/agents/harness.py`: the 7 AUQ/plan tool-detection methods.
- `chat_state.py`: `make_plan_approval_question` (tests-only).

**Deliberately NOT removed (different risk class / separate decisions):**
- **Persisted message-class definitions** (`AskUserQuestionAgentMessage`,
  `ResponseBlockAgentMessage`, `PlanModeAgentMessage`, the
  Request*/ContextSummary/Warning/Background/AutoCompacting messages, etc.)
  and their unions. These are members of `PersistentMessageTypes`, which
  `SavedAgentMessage` (database/models.py) deserializes from the DB —
  removing them breaks loading any pre-slim-down rich-agent task history.
  Inert schema, kept for backward-compatible deserialization. NOTE: a field
  description on `AskUserQuestionData.plan_file_path` still references the
  now-removed `make_plan_approval_question`; left as-is to avoid a
  JSON-schema migration for a doc-only change — clean it up here when these
  types are eventually removed (with a real migration).
- **The 4 endpoints** (`answer_question`, `clear_context`, `delete_message`,
  `interrupt`) — API-contract; need a frontend/CLI cross-check.
- **The backend stream-converter internals** (`convert_agent_messages_to_
  task_update` + the `StreamingTaskState` `pending_user_question` etc.) —
  these handle the dead ResponseBlock/AUQ/PlanMode branches BUT also process
  the live terminal lifecycle/signal messages, so it's surgical excision
  from a live function, not a leaf delete.
- **Frontend dead chat-stream plumbing** (the `taskDetails` atoms/reducers
  `pendingUserQuestion`/`isInPlanMode`/`completedChatMessages`/
  `submittedQuestionAnswers`/`pendingBackgroundTaskIds`/`queuedChatMessages`,
  `useUnifiedStream` processing, and dead utils `askUserQuestionUtils`,
  `subagentTree`, `getToolDisplayName`/`getToolDisplayNamePresent`, the
  `Guards` tool-block type guards, `extractUserMessageIds`/`userMessageIds`)
  — no persistence risk, but per-item ref-checking needed (`inProgressChat
  Message` IS live for file-op highlighting; some fields are "remove breaks
  WorkspacePanelData shape"). A good next chunk.

### Done (2026-06-26, second batch) — frontend plumbing + endpoints

- **Frontend chat-stream plumbing** removed: the dead `TaskDetailState`
  fields (kept only `inProgressChatMessage` + `artifacts`),
  `taskDetailReducers.ts`, `suggestionUtils.ts`, `useTaskChatMessages`,
  `draftQuestionStateAtomFamily`, the dead `utils.ts` helpers
  (tool-display-name / plan-mode / alpha-chat) and nine unused `Guards.ts`
  block type-guards, plus `askUserQuestionUtils.ts` / `subagentTree.ts`.
- **Endpoints** `answer_question` + `clear_context` removed (no live caller;
  no-ops for terminal agents) + `AnswerQuestionRequest`. `interrupt` kept
  (live: Stop button + `sculpt agent interrupt`). `UserQuestionAnswerMessage`
  / `ClearContextUserMessage` kept as inert persisted-schema types.

### NEW, BIGGER finding — the whole `TaskUpdate` streaming subsystem is dead

Tracing the (non-existent) "converter" revealed the real shape: the live
`StreamingUpdate` builder (`web/streams.py::_convert_to_streaming_update`,
the `return StreamingUpdate(...)` at ~L791) **never populates
`task_update_by_task_id`** — it always defaults to `{}`. The only
`TaskUpdate(...)` constructor in the tree is a test. So:
- **Backend:** `web/derived.py::TaskUpdate` (the whole class) and
  `StreamingUpdate.task_update_by_task_id` (web/streams.py) are dead.
- **Frontend (cascade):** `data.taskUpdateByTaskId` is always empty, so the
  entire `useUnifiedStream` taskUpdate block, `updateTaskDetail`,
  the `taskDetails` atoms (`inProgressChatMessage`/`artifacts`),
  `useTaskDetail`, `useArtifactSync` + the `taskUpdatedArtifacts` atoms, and
  `useActiveFileOperation` never receive data. The file-op highlighting that
  `useActiveFileOperation` feeds in `ChangesTreeView.tsx` / `FileTree.tsx`
  therefore never activates.

This is **deferred as its own pass** — not because it's uncertain (it's
confirmed dead) but because it's one coupled backend+frontend refactor that
reaches into live-rendered file-browser components, so it wants a dedicated,
separately-reviewed removal rather than a tail-end hack. Note this also means
the `inProgressChatMessage`/`artifacts` fields kept in the previous frontend
commit are themselves dead (always-empty) and go in this same pass.
Sequence: (1) backend remove `TaskUpdate` + `task_update_by_task_id`,
`just generate-api`; (2) frontend remove the `useUnifiedStream` block →
`taskDetails`/`useTaskDetail`/`useArtifactSync`/`useActiveFileOperation` →
strip the highlighting from `ChangesTreeView`/`FileTree`.

---

## 1. Settings → Agent page + all agent-behavior vestiges

We no longer control agent behavior (model, fast mode, thinking effort)
from Sculptor — the user's `claude` CLI owns that. The whole Agent
settings section and its supporting model/fast-mode/effort plumbing
should go, on both the frontend and the backend.

### 1a. Frontend — Agent settings UI (DELETE)
- `pages/settings/sections.ts` — remove the `AGENT` member of
  `SettingsSection` and its descriptor in `SETTINGS_SECTIONS`
  (displayName "Agent", subtitle "Default model and effort").
- `pages/settings/SettingsPage.tsx` — remove the
  `activeSection === SettingsSection.AGENT` block (the Default Model
  `Select`, Fast Mode `Switch`, Effort Level `Select`) and the now-unused
  imports: `ModelSelectOptions`, `configuredDefaultModelAtom`,
  `defaultEffortLevelAtom`, `isDefaultFastModeAtom`,
  `EFFORT_DISPLAY_NAMES`, `EFFORT_OPTIONS`.

### 1b. Frontend — model / fast-mode / effort components & atoms (DELETE)
Orphaned (no inbound imports outside their own test/style):
- `components/ModelSelectOptions.tsx` (used only by the Agent settings block above)
- `components/ModelSelector.tsx` + `.module.scss` + `.test.tsx` (test-only)
- `components/FastModeToggle.tsx`
- `components/EffortSelector.tsx` + `.module.scss`
- `components/effortConstants.ts` (only consumers are the Agent block + EffortSelector)
- `common/state/atoms/userConfig.ts` — `lastUsedModelAtom`,
  `configuredDefaultModelAtom`, `defaultModelAtom`, `isDefaultFastModeAtom`,
  `defaultEffortLevelAtom` (verify each has no other consumer after 1a/1d).
- `common/state/atoms/draftAgentSettings.ts` — `fastModeAtomFamily`,
  `effortAtomFamily`, `modelAtomFamily`, and the corresponding lines in
  `removeTaskSettings()`. If the file is then empty, delete it and its
  call from `tasks.ts`.

### 1c. Frontend — model still threaded into create/message calls (DECIDE → recommend DELETE)
- `pages/workspace/components/AgentTabs.tsx` (~L267-288) inherits
  `currentAgent?.model` and sends `model` in the create-agent body — with
  the comment *"Terminal agents never read it."*
- `pages/workspace/components/useChatData.ts` (~L84) sends
  `model: taskModel || LlmModel.CLAUDE_4_OPUS_200K` on every message.
- These are pure vestiges. Removing them is coupled to making `model`
  optional/removed on the backend request types (1e). See decision in §5.

### 1d. Backend — UserConfig fields (DELETE)
In `config/user_config.py`:
- `default_llm` (L124-128) — also drop the stale "electron frontend reads
  this in configFallback.ts" note; confirm `configFallback.ts` no longer
  references it.
- `default_fast_mode` (L205-208)
- `default_effort_level` (L210-213)

Note: `UserConfigField` is **auto-generated** from `UserConfig` fields via
`_generate_user_config_field_enum()`, so removing the fields removes the
enum members automatically — but it also changes the generated TS
`UserConfigField` enum, so `just generate-api` must be re-run and the
frontend rechecked.

### 1e. Backend — model/effort/fast-mode request & message plumbing (DECIDE)
Terminal agents ignore all three (`terminal_agent/harness.py` sets
`supports_fast_mode=False` and never reads `model_name`/`effort`).
Everything below is vestigial for the slimmed product:
- `web/data_types.py` — `model`/`fast_mode`/`effort` fields on
  `StartTaskRequest`, `CreateAgentRequest`, `SendMessageRequest`; the
  `SetModelRequest` class.
- `web/app.py` — assignments at ~L470/578/601-602, 1869/1885/1890-91/1953/1971,
  2321/2325-26; the `POST .../set_model` endpoint (~L2427-2480) and its
  tests in `web/app_basic_test.py`.
- `database/models.py` — `AgentTaskInputsV2.default_model`; and `web/derived.py`
  `model` property (~L410-412) that reads it.
- `state/messages.py` — `LLMModel` enum (L14-27), `EffortLevel` enum
  (L29-34); `interfaces/agents/agent.py` + `state/messages.py`
  `ResumeAgentResponseRunnerMessage.fast_mode`/`.effort`.
- `interfaces/agents/harness.py` — `supports_fast_mode` capability (L86, 137).
- `agents/default/constants.py` — `MODEL_SHORTNAME_MAP` (+ its `LLMModel` import).

**Depth decision (§5):** fully excise `LLMModel`/`EffortLevel` and the
request fields, vs. leave a minimal `LLMModel` enum to avoid a large,
test-heavy ripple. Recommendation: full excision, since "the model list"
is exactly what the request names.

### 1f. ElementIds / testing (DELETE, after UI removal)
- `sculptor/constants.py` — `SETTINGS_NAV_AGENT`,
  `SETTINGS_DEFAULT_MODEL_SELECT`, `SETTINGS_DEFAULT_MODEL_OPTION`,
  `SETTINGS_DEFAULT_FAST_MODE_TOGGLE`,
  `SETTINGS_DEFAULT_EFFORT_LEVEL_SELECT`,
  `SETTINGS_DEFAULT_EFFORT_LEVEL_OPTION` (then `just generate-api`).
- `sculptor/testing/elements/settings_agent.py` — delete; remove
  `click_on_agent`/`_get_agent_nav` from `testing/pages/settings_page.py`.
- Any integration test that opens the Agent settings section.

---

## 2. Settings → Privacy page + email-on-startup vestiges

We no longer ask for the user's email on startup, and telemetry is
already gone, so the Privacy section (email + telemetry) and the
email/account-setup plumbing are dead.

### 2a. Frontend (DELETE)
- `pages/settings/sections.ts` — remove `PRIVACY` member + descriptor
  (subtitle "Email and telemetry").
- `pages/settings/SettingsPage.tsx` — remove the
  `activeSection === SettingsSection.PRIVACY` block and `userEmailAtom`
  import/use.
- `pages/settings/components/AccountFieldRow.tsx` (+ `.module.scss`) —
  only consumer is the Privacy block; confirm and delete.
- `common/state/atoms/userConfig.ts` — `userEmailAtom`.

### 2b. Backend — email / account-setup endpoints (DECIDE → recommend DELETE)
- `web/app.py` — `POST /api/v1/config/email` (~L2654-2692),
  `POST /api/v1/config/skip_account` (~L2695-2715); `has_email` in the
  config-status endpoint (~L2623/2631).
- `web/data_types.py` — `EmailConfigRequest`, `SkipAccountSetupRequest`.
- `startup_checks.py` — `check_is_user_email_field_valid` (+ its import in app.py).
- Confirm `OnboardingWizard.tsx` (PATH_CHECK / ADD_REPO steps) does not
  call these; if it marks completion via `skip_account`, repoint it to
  whatever the slimmed completion path is before removing the endpoint.

### 2c. UserConfig email/telemetry fields (DECIDE)
`config/user_config.py` still has `user_email`, `user_full_name`,
`user_id`, `organization_id`, `instance_id`, and the telemetry-consent
booleans (`is_error_reporting_enabled`, `is_product_analytics_enabled`,
`is_session_recording_enabled`, `is_privacy_policy_consented`,
`is_telemetry_level_set`) plus the `PrivacySettings` model and
`get_privacy_settings_for_telemetry()`. Telemetry was supposedly removed
in the main pass — these may be leftovers. **Decide** how far to prune;
note the runtime assertion that every `PrivacySettings` field also exists
on `UserConfig` (must stay consistent).
- **KEEP:** `user.email`/`user.name` git-author config in
  `services/git_repo_service/default_implementation.py` and
  `auth.py`'s `UserSession.user_email` / `ANONYMOUS_USER_EMAIL` are
  separate from the removed account concept — do not delete without
  confirming they're truly unused.

### 2d. ElementIds / testing (DELETE)
- `sculptor/constants.py` — `SETTINGS_NAV_PRIVACY`, `SETTINGS_EMAIL_FIELD`,
  `SETTINGS_PRIVACY_TELEMETRY_*`.
- `testing/elements/settings_privacy.py`; `click_on_privacy`/`_get_privacy_nav`
  in `testing/pages/settings_page.py`.
- `tests/integration/frontend/test_onboarding.py` privacy-consent cases;
  `test_user_email` fixtures that exist only for these paths.

---

## 3. Keybindings

Source: `common/keybindings/{types.ts,definitions.ts}`;
settings UI `pages/settings/components/KeybindingsSection.tsx`; handler
`layouts/hooks/usePageLayoutKeyboardShortcuts.ts`.

### 3a. Entire "chat" category (DELETE)
All three chat-category bindings are dead — their handlers/targets were
removed with the chat UI:
- `send_message` (Meta+Enter) — no global handler. (Note: the add-workspace
  form reads `useKeybinding("send_message")` only for a hint string; give
  the form its own literal/binding before deleting.)
- `interrupt_agent` (Ctrl+C) — no handler; terminal uses `clear_terminal`.
- `toggle_tool_density` (Meta+Shift+E) — no handler at all.

Remove `"chat"` from the category union in `types.ts` and from the
category display-order array once the bindings are gone.

### 3b. Chat-targeting bindings in the "general" category (DELETE)
- `chat_search` (Meta+Shift+F) — handler only fires if a `CHAT_PANEL`
  element exists; it never renders now (dead path).
- `focus_input` (Meta+I, "Focus the chat input field") — chat input is
  gone. If the workspace-name/add-workspace input focus is still wanted,
  keep the binding but repoint/relabel it to that input only; otherwise
  delete. **DECIDE.**

### 3c. Associated dead state / ElementIds (DELETE)
- `common/state/atoms/chatSearch.ts` (all four atoms) — consumers are only
  the dead `chat_search` handler, `useCommandRuntime.ts`, and the orphaned
  `ChatSearchBar.tsx`.
- ElementIds `CHAT_PANEL`, `CHAT_INPUT`, `CHAT_SEARCH_BAR`,
  `CHAT_SEARCH_INPUT`, `CHAT_SEARCH_MATCH_COUNTER`; const
  `CHAT_INPUT_ELEMENT_ID`.
- `components/CommandPalette/builtinCommands/chat.ts` (`buildChatCommands`)
  + its registration in `CommandRegistrations.tsx` and the `hasChatPanel`
  context field — all gate on a chat panel that no longer exists.

### 3d. Tests (UPDATE)
`tests/integration/frontend/test_keybindings.py`,
`common/keybindings/definitions.test.ts`,
`CommandPalette/__tests__/*` (shortcutResolution, builtinCommands,
registry, drift tests) reference the removed bindings/commands — update or
drop the relevant cases.

---

## 4. Other vestiges surfaced by the sweep

These are real leftovers but larger / outside the three named areas.
Listed with a recommendation; flagged for a go/no-go in §5 rather than
silently expanding scope.

### 4a. Orphaned chat-input components (DELETE — clearly dead)
No inbound imports outside their own test/style:
- `components/SendButton.tsx` (+ `.module.scss`)
- `components/MarkdownBlock.tsx` (+ `.module.scss`)
- `components/FileUpload.tsx` (+ `.module.scss`)
- `components/FilePreviewList.tsx` (+ `.module.scss`)
- `pages/workspace/components/ChatSearchBar.tsx` (+ `.module.scss`)
- `common/state/hooks/useDraftAttachedFiles.ts` (+ test)
- `common/state/atoms/attachedFiles.ts` (+ test)
- `common/state/atoms/alphaScroll.ts` — `alphaScrollPositionAtomFamily`
  (dead; keep `debugViewAtomFamily`, used by AgentTabs).

### 4b. Entity @-mentions system (DEFERRED — bigger/entangled than expected)
Spec'd for removal (REQ-CHAT-1, `enable_entity_mentions`). Currently
hard-gated off via `isEntityMentionsEnabled = false` in `Editor.tsx`.

**Execution finding (2026-06-25):** this is more entangled than the sweep
implied, so it was pulled out of this pass for a focused follow-up:
- The TipTap `Editor` is still live — but its **only** consumer is
  `ActionDialog.tsx`, which passes neither `projectID` nor `workspaceID`.
  In `createTipTapExtensions`, suggestions only activate when
  `editable && (projectID || workspaceID || entityDataRef)`, so in the
  slimmed app **no** picker fires at all.
- Consequently not just the entity (`+`) picker but the entire
  `@file` / `/skill` mention-suggestion infrastructure
  (`MentionPickerSuggestion`, `EntityMentionSuggestion`, `SkillSuggestion`,
  `SuggestionUtils` file picker, `MentionPickerList`, `MentionNodeView`,
  `MentionChip`, `EntityMention*`, `mentionDetailPanes/*`,
  `mentionDetails.ts`) is dead.
- The three chip variants (`@file`, `/skill`, `+entity`) share **one**
  `Mention` node in `TipTapConfig.ts`, so an entity-only extraction is
  fiddly surgery on a live shared node.
- Backend: `ENTITY_MENTIONS_SYSTEM_PROMPT` in `agents/default/constants.py`.

**Open question for the follow-up:** remove only the entity-specific
parts (narrow, fiddly), or remove the whole now-dead mention/suggestion
system and simplify `Editor`/`TipTapConfig` down to what `ActionDialog`
actually needs (larger, cleaner)?

### 4c. Smooth streaming (DEFERRED — part of the dead chat-render layer)
Spec listed smooth-streaming for removal (REQ-CHAT). Still present:
- `config/user_config.py` `is_smooth_streaming_enabled`.
- `common/state/atoms/smoothStreaming.ts`, `hooks/useSmoothStreaming.ts`,
  `hooks/useSmoothStreamingViewportObserver.ts`.

**Execution finding (2026-06-25):** the only consumer chain is
`useChatData.ts`, which is itself **dead** — no live component imports it
(only tests/comments reference it). `ChatPanelContent` is mounted in
`WorkspacePage` but does **not** import `useChatData`/smooth streaming.

### 4d. Dead chat render/data layer (NEW — the umbrella for 4b + 4c)
The slim-down removed the `chat-alpha/` tree but left a sizable dead
data/render layer with no live consumer: `useChatData.ts`,
`useSmoothStreaming*`, the entire mention/suggestion system (§4b),
`AlphaMarkdownBlock`, and likely more under `pages/workspace/hooks` /
`components`. Recommendation: remove this as **one dedicated follow-up**
(map it with an orphan-import pass, then delete leaf-first), rather than
pulling individual threads (smooth streaming, entity mentions) that each
dangle into the same dead cluster. Deferred out of this pass.

---

## 5. Cross-cutting execution notes

- **Type generation:** any change to `UserConfig`, `ElementIDs`,
  `data_types.py` request models, or backend enums requires
  `just generate-api`; then re-typecheck the frontend (a stale
  `node_modules` can cause phantom tsc errors — reinstall if so).
- **Ratchets are at their cap** — don't introduce new flagged patterns;
  `just ratchets-broken` if `just check` fails.
- **Commit gate:** `just format && just check && just test-unit` before
  each commit; run integration tests in small batches (they flake under
  high xdist parallelism).
- **ElementIds:** remove from `sculptor/constants.py` (source of truth),
  not the generated `types.gen.ts`.
- **Suggested sequencing:** ship in reviewable commits — (1) Agent
  settings + agent-behavior, (2) Privacy + email, (3) keybindings + dead
  chat state, (4) orphaned chat components — each green on its own.

### Decisions (confirmed)
1. **Backend depth (1c/1e):** ✅ **Full excision** — remove
   `LLMModel`/`EffortLevel`, the `model`/`fast_mode`/`effort` request &
   message fields, `AgentTaskInputsV2.default_model`, and `set_model`.
2. **Email endpoints & UserConfig telemetry fields (2b/2c):** ✅ **Remove**
   the `email`/`skip_account` endpoints, email validation, and prune the
   dead telemetry-consent `UserConfig` fields + `PrivacySettings` (keeping
   git-author email and `UserSession` email).
3. **`focus_input` (3b):** ✅ **Delete** it entirely with the other dead
   chat bindings.
4. **Scope of §4:** ✅ **All included this pass** — orphaned chat
   components, the entity @-mentions subtree, and smooth streaming.
