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
