# Slim-down dead / vestigial code audit

Branch: `saeed/sculptor-slim/remove-features`. Product is now **terminal-agent-only**
(agents run `claude` in an xterm PTY; no structured message stream; waiting/busy/plan
state is hook-driven via `claude-code-hooks.json`).

This file is the running worklist. Each item: location — what — why vestigial — confidence — action.
Confidence: **HIGH** = provably unreachable/unused; **MEDIUM** = reachable but a husk of a
removed feature; **LOW** = suspicious / cosmetic.

> Method note: reachability alone is NOT sufficient. Two false-negative classes bit us and
> are called out inline:
> 1. **Vestigially-named but LIVE** (e.g. `chatActions`) — looks dead, is wired to a live feature.
> 2. **Effectively-constant gate → dead branch** (e.g. `backendCapabilities`) — code is reachable
>    but a condition is fixed in the shipped product, so one branch can never run.

Status: **wave 2 (constant-gate hunt + skeptical re-audit) in progress — findings below the divider will be appended.**

---

## Tier 1 — biggest wins (HIGH confidence, real removal)

### A. Frontend docking machinery — husk of removed drag/dock/zen/toggle UI (`components/panels/`)
Live product registers exactly 3 fixed panels (files→top-left, actions→top-right, terminal→bottom);
only live mutations are `togglePanel` + resize.
- `hooks.ts:42-186` — **`movePanel`** (cross-zone move + promotion invariant + `insertIndex`) is
  returned from `usePanelActions` but **no caller destructures it** (verified). Collapse
  `usePanelActions` to `togglePanel` only. Also drop the orphan `data-droppable-id` on
  `LeftSidebar.tsx:12` / `RightSidebar.tsx:12` and `data-panel-icon` (`SidebarIcon.tsx:46`) — no
  DndContext/drop handler wraps the sidebars. **HIGH**
- `atoms.ts:47` — **`panelEnabledAtom`** written only in tests → always `{}`; so `isBuiltin` /
  `defaultEnabled` (`types.ts:25-26`) are never set by any live panel and the `isEnabled` filters
  (`atoms.ts:70-71`, `89-96`) always pass. Remove the enable/disable cascade (leftover of
  Skills/harness-caps gating). **HIGH**
- `types.ts:4` — **`bottom-left` / `bottom-right` zones are structurally unreachable** (no panel
  defaults there; `movePanel` was the only reassignment path). Dead consequences:
  `VerticalSplit.tsx:44-69` bottom half + inner handle; `DockingLayout.tsx` `isBottomLeftVisible`
  / `isBottomRightVisible` (57,59), `bottomLeftPx`/`bottomRightPx` (129-130), the four
  get/set bottom handlers (180-184), `DEFAULT_INNER_BOTTOM_HEIGHT_PX` (`constants.ts:5`);
  `LeftSidebar.tsx:21,24,30-32` / `RightSidebar.tsx:21,23,29-31` bottom-zone + `shouldShowDivider`.
  Collapse the 5-zone model to the 3 live zones; `VerticalSplit` → single-zone render. **HIGH**
- `types.ts:10,24` — `contextMenuItems` / `ContextMenuItem` never populated → `PanelContextMenu.tsx:23-32`
  items block never renders (label-only menu). **MEDIUM**
- `atoms.ts:41` — `zoneOrderAtom` reorder machinery inert (one panel per zone; only writer was dead
  `movePanel`); the ordered/unordered sort in `panelsInZoneAtom` (98-104) is a no-op. **MEDIUM**
- `DockingLayout.tsx:53` — expand mode only ever targets `"files"` (sole non-null writer is
  `DiffTabBar.tsx:224`), so the `bottom-left`/`top-right`/`bottom-right` expand arms are unreachable.
  Simplify to the single top-left case. **MEDIUM** (expand mode itself is LIVE — keep it.)
- KEEP (verified live): per-panel keyboard shortcuts (`usePanelKeyboardShortcuts`, `panelShortcutsAtom`,
  `panel_${id}` bindings in Settings), `expandedPanelIdAtom` expand mode, `terminalPanelMountedAtom`,
  `filesZoneAtom`.

### B. Write-only backend DB fields with zero readers (`sculptor/database/models.py`)
- `AgentTaskInputsV2.system_prompt:138` — written from `project.default_system_prompt`
  (`web/app.py:1429`, `services/ci_babysitter_service/coordinator.py:593`); **zero readers**
  (verified — terminal agents run `claude` in a PTY, never inject a system prompt). **HIGH**
- `Project.default_system_prompt:57` (+ `services/data_model_service/data_types.py:75`, DB column
  in initial migration) — only ever *copied into* the write-only field above; never set in prod,
  never surfaced to the frontend. Dead config chain. **HIGH**
- `AgentTaskInputsV2.git_hash:136` — written from `initial_commit_hash`; diff computation now uses
  workspace-level `source_git_hash`. Only "readers" are the docstring + tests (verified). It's a
  required `str`, so removal needs a migration/backfill or demote-to-optional first. **HIGH**
- These are baked into task-input JSON in the DB; removal needs an alembic migration + regenerated
  `frozen_pydantic_schemas.json`. Migrations were squashed to one initial migration — regenerate via
  autogenerate against an EMPTY conn.

### C. Frontend remote/custom-command backend husk (removed subsystem)
- `electron/main.ts:829` — `get-backend-url` IPC always resolves **`null`** ("custom-command backends
  are gone"), so `apiClient.ts:136` always calls `initBackendCapabilities(false)`. Consequences:
  - `common/state/atoms/backendCapabilities.ts:28` — **`REMOTE_CAPABILITIES` unreachable**; capabilities
    are permanently `DEFAULT_CAPABILITIES` `{canOpenInOS:true, canSelectLocalDir:true,
    fileUploadMode:"electron-ipc"}`. Delete `REMOTE_CAPABILITIES`; make `initBackendCapabilities` take
    no arg. **HIGH**
  - **Every false-branch of those capability flags is dead** (constant-gate class): the
    `fileUploadMode==="http"` path; the `!canOpenInOS` fallbacks in `BinaryPreview.tsx:275,304,322`,
    `RepoSegment.tsx:23`, `useFileMenuGroups.tsx:156`; the `!canSelectLocalDir` path in
    `useAddRepo.tsx:122`. (Wave-2 frontend agent is enumerating these precisely.) **HIGH**
  - `apiClient.ts:121-133` + IPC chain (`electron/main.ts:127-130,785,829`, `preload.ts:31`,
    `shared/types.ts:41`) exists solely for the removed backend — collapse to the localhost branch,
    drop the `getBackendUrl` IPC/preload/type. **MEDIUM**

### D. Dead test POM + orphaned ElementIDs (auto-update / model-selection / bottom-bar)
- `testing/elements/version_popover.py` — `PlaywrightVersionPopoverElement` never imported; references
  4 ElementIDs that no longer exist (would `AttributeError`). Delete → unblocks removing
  `CLAUDE_CLI_VERSION_POPOVER` + `CLAUDE_CLI_MODE_POPOVER` (`constants.py:195-196`). **HIGH**
- `constants.py:153` `BOTTOM_BAR` ElementID + its only consumer `get_bottom_bar()` (zero callers) —
  bottom bar removed in `c6421811a0`. **HIGH**
- `constants.py:71` `FILE_PREVIEW_COPY_IMAGE` — only ElementID fully unreferenced across `.py/.ts/.tsx`.
  Possibly an abandoned unwired button. **MEDIUM**
- Regenerate TS types after removing ElementIDs (`just generate-api`).

---

## Tier 2 — collapse over-general abstractions (MEDIUM)

- **Task-view generic/ABC hierarchy → one concrete type** (`web/derived.py:88-222`):
  `LimitedBaseTaskView[Generic] → TaskView[Generic] → CodingAgentTaskView` (only leaf); the
  `TaskInputs`/`BaseTaskState` bases each have exactly one subclass (already aliased in
  `models.py:143,168`). Leftover strategy scaffolding for removed Pi/rich agents — flatten to one
  concrete `TaskView`, drop the abstract bases + TypeVars. Several docstrings here are also stale.
- **`AgentMessageSource` single-value enum** (`state/messages.py:11`): only member `RUNNER`, hardcoded
  everywhere; the `source == RUNNER` filter (`base_implementation.py:137`) is always true. Touches a
  serialized field + `SavedAgentMessage.source` DB column → careful refactor, not a pure delete.
- **`StatusIndicators` / `VersionDisplay`** — after "Report a problem" removal, two trivial passthrough
  wrappers around `VersionPopover` (`PageLayout → VersionDisplay → StatusIndicators → VersionPopover`).
  Collapse.
- **`primitives/hashes/`** (`control_plane_tag.txt`, `control_plane_manifests.json`) — OCI base-image
  pinning for the removed offload/remote-environment subsystem; referenced only by a `MANIFEST.in`
  glob. Delete (and prune the MANIFEST.in include).
- **`common/overlayUtils.ts:29-45`** — TipTap suggestion-popover DOM detection (TipTap removed; no
  `ReactRenderer` remains). Broad DOM heuristic — confirm nothing else portals an absolute element
  into the root-theme node, then remove. Lines 1-27 (Radix detection) stay.
- **`useProgressiveCollapse.ts:11,75,114-117`** — overflow-menu accounting (`OVERFLOW_BUTTON_WIDTH_ESTIMATE`,
  `data-overflow` skip) never exercised; the only consumer (`WorkspaceBanner.tsx`) renders no overflow
  menu. Wire it or drop it.

---

## Tier 3 — low-value / cosmetic (naming + comment debt)

- **Empty agent-package dirs** — `agents/{default, default/claude_code_sdk, hello_agent, pi_agent,
  terminal_agent}` are on-disk husks (0 tracked files). `rmdir`.
- **Stale filename** — `pages/workspace/components/ChatIntro.module.scss` (no `ChatIntro.tsx`; imported
  by `SetupConfigPrompt.tsx`). Rename to `SetupConfigPrompt.module.scss`.
- **Vestigially-named but LIVE** (rename only — DO NOT delete; verified wired to live terminal features):
  - `common/state/atoms/chatActions.ts` (`chatActionsAtom`/`ChatActions`/`sendMessage`/`appendText`) —
    **LIVE**: bundled `samples/terminal_agents/claude-code/claude-code.toml` sets
    `accepts_automated_prompts = true` (installed by `services/terminal_agent_registry/bundled.py`),
    so `useTerminalChatActions` registers real closures that drive Commit / Create-PR / ActionsPanel
    action chips / CommandPalette git-and-open through the PTY. Rename away from "chat".
  - `pages/workspace/components/useTerminalChatActions.ts`, `ChatPanelContent.tsx`,
    `DiffSplitContainer.tsx` (`CHAT_MIN_WIDTH_PX`/`chatPanel`/`chatContent`) — live, chat-named.
- **Stale docstrings/READMEs**: `interfaces/agents/README.md` (describes removed message-based model +
  deleted classes); `CodingAgentTaskView` docstring ("messages are the primary way…" — fix the
  Pydantic source, then regenerate TS `api/types.gen.ts:203-214`); `services/user_config/__init__.py:1`
  ("…and telemetry").
- **Comment debt** referencing removed features: `CommandPalette/hooks.ts:32` (zen mode / chat panel),
  `commandActions.ts:6,41` (chat panel), `hooks.ts:25`+`types.ts:119` (experimental flags),
  `CommandPalette.tsx:50`+`.module.scss:290` (chat input KeyboardHint), `dynamic/panels.ts:9` (Notes
  panel), `groups.ts:16-19` (panel/zone toggles), `useAppZoom.ts:20-25` (Browser panel/Linux CI),
  `useTerminal.ts:702` (ChatInput.tsx), `useTerminalChatActions.ts:15,39` (useChatData/rich-chat),
  `settingsStyles.ts:5` (`~/.sculptor/plugins`), `common/state/atoms/tasks.ts:83-85` (chat intro).
- **sculpt CLI**: `_follow_helpers.py:78` `follow_and_stream_messages` stale name/docstring (message
  stream deleted; `send` no longer calls it → rename `follow_until_terminal`); `agent.py:414`
  `status -f --timeout` silently ignored under `--follow`; `agent.py:156` `list --status` help omits
  `WAITING`; text-mode `run --follow` emits nothing (`noop_status`); `harness.py` one-entry
  `BUILTIN_HARNESS_LABELS` dict-loop over a single value.
- **Over-exports** (tighten, not dead): `setActiveDiffTabAtom` (`diffPanel/atoms.ts:129`),
  `FileViewTab`/`CommitFileDiffTab` (`diffPanel/types.ts:18,27`), `PrErrorCategory`/`EffectiveError`
  (`PrButton.tsx:19,27`), `RepoSegment.tsx:17` unused `data-testid?` prop (delete the prop).
- **`foundation/common.py:31-42`** `get_filesystem_root()` / `SCIENCE_FILESYSTEM_ROOT` — legacy imbue
  "science"-monorepo paths; reachable only via one integration test. Consider collapsing `get_temp_dir`.
- **Duplicate** `isDismissibleOverlayOpen` — `common/ShortcutUtils.ts:201-205` vs
  `common/overlayUtils.ts:9`. Consolidate.

---

## Explicitly cleared in wave 1 (guard against false positives)
Verified LIVE via a real production path (re-checked by wave-2 skeptic agent):
- **`chatActions` + custom-actions system** — live (see Tier 3; bundled registration opts in).
- CI-Babysitter (live PR-CI feature, ≠ removed build CI); all 8 settings sections; keybindings registry;
  CommandPalette providers; `statusDot/statusUtils`; workspace tab infra + `useWorkspaceTabActions`;
  all six `TaskState` values and every `*RunnerMessage` type (real producers+consumers);
  `useUnifiedStream`, `promptDrafts`/`usePromptDraft` (repurposed for new-workspace drafts),
  `WarningStatusBanner`; generated sculpt client models (no offload/telemetry orphans); `tools/` has
  only `tools/sculpt` (no orphaned subsystem dirs).

---

## Sequencing
- **No-migration frontend/test removals** (do first): Tier 1A (docking husk), 1C (remote-backend +
  capability dead branches), 1D (POM + ElementIDs), Tier 2 wrappers, Tier 3 renames/comments.
- **Migration-bearing batch** (do together): Tier 1B write-only DB fields + Tier 2 `AgentMessageSource`
  enum — one alembic migration + regenerated frozen schema + `just generate-api`.

---

## Wave 2 — constant-gate dead branches + skeptical re-audit

Wave 2 hunted the two false-negative classes and re-litigated wave-1's "cleared" list.
**The 11 wave-1 "cleared as live" items all held up — no false-negatives.** New dead code:

### Backend constant-gate findings (all traced to a constant production source)
- **`TaskState.CANCELLED`** (`interfaces/agents/tasks.py:12`) — never produced; only ever
  SUCCEEDED/FAILED/QUEUED/DELETED. Dead branches: `services/task_service/base_implementation.py:448-450`
  (`if outcome == CANCELLED: pass`), and the `CANCELLED` term in `web/derived.py:147`. **HIGH — delete.**
- **`SERVE_STATIC_FILES_DIR`** (`config/settings.py:37`) — zero assignment sites (packaged app serves
  the frontend via Electron). Dead: `web/middleware.py:295-296` guard + its only-caller helper
  `mount_static_files` (`web/middleware.py:42`). **HIGH — delete.**
- **`NotificationImportance.ACTIVE`** (`database/models.py:259-269,279`) — the only production
  `Notification(...)` passes `TIME_SENSITIVE` (`tasks/handlers/run_terminal_agent/runner_support.py:138`);
  ACTIVE default never stored. Dead frontend arms: `NotificationToasts.tsx:20,32`. **HIGH — delete member,
  retarget default to TIME_SENSITIVE.**
- **repo-polling scope filters** — sole prod caller passes `workspace_filter=None, project_filter=None`
  (`web/streams.py:249-254`). Dead: `web/repo_polling_manager.py:104-107` filter arms + the
  `workspace_filter`/`project_filter` params/precedence (`:86-87,93,192,196-197`). **MEDIUM — delete.**
- **`streams.py:114`** `if state.status == "not_configured": continue` — runner slots only emit
  pending/running/succeeded/failed; `not_configured` only lives on the persisted Workspace field.
  **MEDIUM — delete the dead skip.**
- **`SetupStatus "pending"` on runner/stream path** (`setup_command_runner.py:61`) — always overwritten
  before observable; but the value IS live on `Workspace.setup_status`. **NARROW — keep the value; skip
  (too risky for low value).**
- **SKIP (intentional/defensive, acknowledged in comments):** `is_terminal_agent_config` always-true
  clauses (`web/app.py:2242,2302,2357`, `tasks/api.py:35`); `environment.supports_terminal` guard
  (`default_implementation.py:650`); CORS test hook; `is_live_debugging` dev-aids.

### Backend dead test POMs + ElementIDs (skeptical re-audit)
- Delete 4 orphaned POM files (zero importers): `testing/elements/version_popover.py` (also BROKEN —
  references removed ElementIDs), `testing/elements/lightbox.py`, `testing/elements/file_preview_and_upload.py`,
  `testing/elements/panel_zones.py`. **HIGH.**
- Drop orphaned `ElementIds` from `constants.py` (0 frontend refs): `CLAUDE_CLI_VERSION_POPOVER`,
  `CLAUDE_CLI_MODE_POPOVER`, `BOTTOM_BAR`, `FILE_PREVIEW_COPY_IMAGE`, `LIGHTBOX_NAV_PREVIOUS/NEXT/COUNTER`,
  `FILE_UPLOAD`, `FILE_PREVIEW`, `FILE_PREVIEW_CONTAINER`, `FILE_PREVIEW_REMOVE`; then `just generate-api`. **HIGH.**

### Frontend constant-gate findings
- **Cluster 1 — `BackendCapabilities` permanently `DEFAULT`** (root: `apiClient.ts:128-130` +
  `electron/main.ts:829` always-null): delete `REMOTE_CAPABILITIES` (`backendCapabilities.ts:28-32`);
  the **`fileUploadMode` field + `"http"` union member are fully dead — never read anywhere** (delete
  entirely); make `initBackendCapabilities` no-arg; collapse `getBackendUrl` IPC chain
  (`apiClient.ts:121-133`, `electron/main.ts:127-130,785,829`, `preload.ts:31`, `shared/types.ts:41`).
  Dead consumer arms (canOpenInOS/canSelectLocalDir constant-true): `workspaceActions.ts:100,116-117,134-135`,
  `RepoSegment.tsx:24,70,98`, `useGitAndOpenInRuntime.ts:114`, `menu.tsx:118`, `BinaryPreview.tsx:275,304,322`,
  `useFileMenuGroups.tsx:156`, `useAddRepo.tsx:122` (canSelectLocalDir conjunct only — keep isElectron). **HIGH.**
- **Cluster 2 — panel drag-to-move dead → bottom zones never populated** (root: `movePanel` never called):
  delete `hooks.ts:55-159` (`movePanel`) + `hooks.ts:28-39` (`usePanelsByZone`); remove bottom-left/right
  zone machinery in `LeftSidebar`/`RightSidebar`/`DockingLayout`/`VerticalSplit`/`atoms.ts` (verify
  reconciliation strips stale localStorage zones before removing zone IDs). **HIGH root / MED-HIGH arms.**
- **Cluster 3 — expand mode only targets `files`→`top-left`**: dead arms `DockingLayout.tsx:57,58,59,61-63`. **HIGH.**
- **Cluster 4 — single-constant-value props** (each spot-verified): `isSidebarOpen` always false
  (`electron/utils.ts:26,37`, param); `PageLayout.showVersionIndicator` always true (`:33,100`);
  `TitleBar.leftPadding`/`className` never passed (`:7-8,13,26`); `PierreDiffView.hideHandle` never passed
  (`:33,124,267`); `CommitButton.onCommit` never passed (`:17,29`); `BranchSelectorCore.triggerVariant`
  always "ghost" (dead `"soft"` defaults `BranchSelectorCore.tsx:48`, `BranchSelector.tsx:27`). **HIGH.**
- **Cluster 5 — per-panel extension fields never set**: `getFocusTarget` (dead branch `hooks.ts:204-208`),
  `contextMenuItems` (`PanelContextMenu.tsx:23-32`); enable-filter arms (`atoms.ts:70,72,91,95`). **HIGH/MED.**
- **LOW dead**: `preload.ts:27` `saveFile` IPC + `electron/main.ts:787` handler (no renderer caller);
  `useCommandRuntime.ts:145` `electron.isAvailable`; `CodingAgentTaskView.taskStatus` serialized-but-unread.
- **SKIP (genuinely varies / uncertain):** `isElectron()`/web-build fallbacks (web build ships, default
  for integration suite), `isMac()`/linux (both platforms ship), **GitLab MR branches** (in tension with a
  main-branch removal — needs a dedicated check), `fileBrowserDockSideAtom`, `electron-custom-command` test mode,
  TabBar/SortableTab library surfaces with story coverage.

### Latent product gaps found (NOT dead code — file tickets, do not delete)
- Crash-message payloads (`AgentCrashedRunnerMessage.exit_code/error`, etc.) are persisted but never
  surfaced — the user only sees a generic red ERROR (`web/derived.py:327` reads `task.error`, which stays
  None on the terminal-crash path). Classes are live (drive unread/updated_at). File a ticket if wanted.

---

## Execution log

**Done this pass (no persisted-schema change — cleanly reviewable, no migration workflow):**
- Backend: `SERVE_STATIC_FILES_DIR` + `mount_static_files` removed; repo-polling `workspace_filter`/
  `project_filter` scope machinery removed; `streams.py` `not_configured` dead skip removed.
- Backend dead files: 4 orphaned test POMs (`version_popover`/`lightbox`/`file_preview_and_upload`/
  `panel_zones`), orphaned ElementIDs (`CLAUDE_CLI_VERSION_POPOVER`/`_MODE_POPOVER`, `BOTTOM_BAR`,
  `FILE_PREVIEW*`/`FILE_UPLOAD`/`LIGHTBOX_*`) + `get_bottom_bar` accessor, empty `agents/` dirs,
  `primitives/hashes/` + its MANIFEST.in include.
- Frontend Cluster 1: `REMOTE_CAPABILITIES` + dead `fileUploadMode` field removed, `getBackendUrl`
  IPC chain collapsed, dead `saveFile` IPC removed.
- Frontend Cluster 4: `isSidebarOpen` param, `showVersionIndicator` prop, `TitleBar.leftPadding`/
  `className`, `PierreDiffView.hideHandle`, `CommitButton.onCommit`, `BranchSelector(Core).triggerVariant`
  all removed (single-constant-value props).
- Tier 2: `StatusIndicators`/`VersionDisplay` passthrough wrappers collapsed into `PageLayout`;
  `overlayUtils.ts` dead TipTap block removed.
- Frontend Clusters 2/3/5 (panel docking husk): `movePanel`/`usePanelsByZone`, bottom-left/right zones,
  expand-mode dead arms, per-panel extension fields — done via focused sub-agent (see its report).

**DONE (persisted-schema batch — separate commit, ran the `bump_migrations.py` frozen-schema regen +
deleted the generated no-op migration stub):**
All genuinely dead, each changing a persisted-model JSON schema / DB column (hence its own commit):
- `TaskState.CANCELLED` (never produced) — removed the member + the dead `outcome == CANCELLED` guard
  and the READY-tuple entry.
- `NotificationImportance.ACTIVE` (default never stored; only TIME_SENSITIVE produced) — removed the
  member, retargeted the default to TIME_SENSITIVE, dropped the dead frontend toast arms.
- `AgentTaskInputsV2.system_prompt` (write-only) — removed the field + ~8 `system_prompt=None` fixtures.
- `Project.default_system_prompt` (write-only config chain) — removed the field, the DB column in the
  initial migration, the `ProjectFieldUpdate` entry, and repointed the `sql_implementation_test.py`
  concurrency/durability guinea-pig field + `coordinator_test.py` to `naming_pattern`.
- `AgentTaskInputsV2.git_hash` (write-only; diff uses workspace `source_git_hash`) — removed the field,
  both write sites + the now-orphaned `initial_commit_hash`/repo-open blocks, and ~9 test fixtures.
Frozen JSON schema regenerated via `bump_migrations.py`; SQL stayed in sync (column dropped from the
initial migration), so the generated migration was a no-op and was deleted (clean break — old rows are
not migrated). `just format`/`check`/`test-unit` green.

**Also deferred (naming/comment debt — not dead code):** rename `chatActions`/`useTerminalChatActions`/
`ChatIntro.module.scss` away from "chat"; stale comments enumerated in Tier 3; `useCommandRuntime`
`electron.isAvailable`. Low value, high churn; left to avoid noise in this pass.
