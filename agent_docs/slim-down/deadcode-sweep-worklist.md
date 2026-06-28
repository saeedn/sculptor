# Slim-down dead-code sweep — worklist

Generated from a 6-way parallel dead-code analysis (backend services, web/server/tasks,
core/interfaces, frontend components/pages, frontend api/hooks/state, sculpt CLID).
Decision: **delete all of it.** Work top-to-bottom in feature-grouped batches; each
batch is one commit after `just format && just check && just test-unit`.

Status legend: `[ ]` pending · `[x]` done · `[~]` partial/superseded

---

## Batch 1 — Backend dead files, endpoints & symbols (HIGH)

- [ ] `sculptor/sculptor/server/llm_content_generation.py` — whole file (~102 LOC), auto-title gen
- [ ] `web/app.py:1266-1334` local-plugins loader (`LocalPluginInfo`, `GET /plugins/local`, `LocalPluginsDirectory`, `GET /plugins/dir`)
- [ ] `web/middleware.py:51,354` `mount_plugin_files` (+ call site) — keep `skills.py` plugin_dirs
- [ ] `web/app.py:2170-2237` mention file-picker (`GET /files_and_folders`, `_list_directory_contents`)
- [ ] `web/app.py:3301-3315` `GET /uploaded-file/{file_id}` (keep POST upload)
- [ ] `state/messages.py:58-61` `PersistentAgentMessage`
- [ ] `interfaces/agents/messages.py:19-22` `EphemeralAgentMessage`
- [ ] `primitives/ids.py:43-49` `AssistantMessageID`, `ToolUseID`
- [ ] `utils/functional.py` whole (`first`)
- [ ] `utils/file_utils.py` whole (`copy_dir` cluster)
- [ ] `foundation/common.py` `get_temp_dir`, `generate_id`, `truncate_string`, `parse_bool_environment_variable` (+ private chain `get_filesystem_root`, `is_on_osx`)
- [ ] `foundation/git.py:78` `get_repo_url_from_folder`
- [ ] `foundation/async_monkey_patches.py:11` `safe_cancel`
- [ ] dead test POMs: `testing/elements/{plan_item,task_list,ask_user_question,task,settings_claude_cli,skills_panel,compaction_header,compaction_panel}.py` + referencing methods in `testing/pages/*`

## Batch 2 — ElementIDs (~77) + regen

- [ ] Remove dead members of `ElementIDs` in `constants.py` (rich chat, /btw, prompt navigator, PLAN/artifact, DAG popover, Pi/managed-dep onboarding, debug/alpha view, orphans). Keep `AGENT_TYPE_MENU_ITEM_PI`, `ASK_USER_QUESTION_*`.
- [ ] `just generate-api`

## Batch 3 — Frontend dead files/components/hooks/atoms/IPC (HIGH)

- [ ] `components/AgentLightboxContext.tsx` + `components/ImageLightbox.tsx` (+ scss/test)
- [ ] `components/fileDisambiguation.ts`
- [ ] `pages/workspace/components/ErrorInput.tsx` (+ scss)
- [ ] orphan `components/SuggestionList.module.scss`
- [ ] orphan `pages/debug/ComponentGalleryPage.module.scss`
- [ ] `common/usePollingInterval.ts` (+ test)
- [ ] `hooks/useFocusOnMountIfUnclaimed.ts`
- [ ] `common/highlightMatch.tsx`
- [ ] `common/formatRepoUrl.ts` (+ test)
- [ ] `common/state/hooks/usePromptDraft.ts` + `common/state/atoms/promptDrafts.ts` `promptDraftAtomFamily`
- [ ] electron `captureScreenshot` IPC chain (constants/main/preload/types)
- [ ] electron `captureBrowserPanelToClipboard` IPC chain

## Batch 4 — sculpt CLI message-stream cluster (HIGH imports + MEDIUM cluster)

- [ ] unused imports: `commands/agent.py:21,29`, `formatting.py:4`
- [ ] `message_formatting.py` whole
- [ ] `agent messages` command + its imports (`commands/agent.py:488-559`)
- [ ] `_follow_helpers.py` `on_messages_*`/`on_partial*`/`noop_messages` plumbing
- [ ] `ws_client.py` message/partial branches + `_partial_signature` + `on_partial` param plumbing
- [ ] always-default fields on `AgentSnapshot`/`AgentShowOutput`/`AgentStatusOutput` + their reads/output (activity/progress/waiting/artifact)
- [ ] note: `sculpt schema`/`--json` shape changes (documented contract change)

## Batch 5 — Backend vestigial scaffolds (MEDIUM)

- [ ] `workspace_service/setup_command_runner.py` `SetupStateProvider`/setup-reminder slice + `make_setup_state_provider` (api + default_impl)
- [ ] `data_model_service/sql_implementation.py` Sentry rewriting (`overwrite_missing_table_error_for_sentry`, `MissingSQLTableError`) + decorator usages
- [ ] `data_model_service/sql_implementation.py` read-only mode (`_is_read_only`, branch, `ReadOnlyConnectionStringExpectedError`, import)
- [ ] `config/user_config.py` `UpdateChannel`/`update_channel`
- [ ] `user_config/user_config.py` telemetry `instance_id` cluster (`_create_random_hash`, `_EXECUTION_INSTANCE_ID`, `get_execution_instance_id`, field population)
- [ ] `state/messages.py:24` `AgentMessageSource.SCULPTOR_SYSTEM`
- [ ] `web/data_types.py` `TaskInterface` enum + `derived.py` `interface` field (always API)
- [ ] `web/data_types.py:550` `Message` arm of `TaskUpdateTypes` + `streams.py:770` guard
- [ ] `tasks/handlers/run_terminal_agent/runner_support.py` `AgentHardKilled`/`AgentShutdownCleanly`/`AgentPaused` + unreachable match arms
- [ ] `interfaces/agents/harness.py:64` `get_jsonl_path_for_working_directory` + `web/app.py:1964-1967` transcript block
- [ ] no-op task handler (`tasks/handlers/noop/v1.py`, `NoOpTaskView`, `NoOpTaskInputsV1`/`MustBeShutDownTaskInputsV1` dispatch) — collapse with its tests
- [ ] `data_model_service` `get_all_tasks`, `task_service` `task_sync_dir`, `get_saved_messages_for_task`, `_is_transient_git_error` constant, `get_project_env_var_names`, task deadline/`max_seconds` subsystem, ci_babysitter `return False` dead line

## Batch 6 — Frontend vestigial (MEDIUM)

- [ ] `FilePreview.tsx` + `CopyImageContextMenu.tsx` cluster (+ scss/test/story)
- [ ] `App.tsx:19,50-58` debug-route bypass + `isDebugRoute`
- [ ] `pages/settings/sections.ts:52-53` stale "updates" copy/keywords
- [ ] `pages/settings/SettingsPage.tsx:55-59` always-true `mobileSections` filter

## Batch 7 — Browser / webview cluster (cross-cutting, user approved delete)

- [ ] frontend `pages/workspace/panels/browser/` whole dir (+ `BrowserViewHost` render in `App.tsx:70`)
- [ ] any inert `agentWebviewStateAtomFamily` writes in `common/state/hooks/useUnifiedStream.ts`
- [ ] sculpt CLI `commands/ui.py` webview commands
- [ ] backend `web/app.py:1020-1053` `/ui/webview/navigate` + `/refresh`, `WebviewCommandUiAction`, `streams.py` fan-out field, `ui_actions.py` union arm
- [ ] regen clients/api after endpoint removal

## Batch 8 — single-impl collapses & always-true branches (LOW / refactor)

- [ ] `foundation/progress_tracking/` no-op placeholder (if fully removable)
- [ ] `web/streams.py` narrow-scope subsystem (Scope*, parse/resolve non-`all` branches) — frontend always ScopeAll
- [ ] `WorkspaceInitializationStrategy` one-value enum + always-WORKTREE params/branches
- [ ] `EnvironmentManager`/`Environment`/`AgentExecutionEnvironment` single-impl ABCs (collapse) — assess risk
- [ ] `EnvironmentTypes`/`ArtifactType` single-value aliases
- [ ] always-true params: `is_history_included`, `get_current_git_branch(is_detached_head_ok)`, `LocalEnvironment.destroy(is_killing)`, `sculptor_folder`, `from_new_repository(user_email,user_name)`

## Batch 9 — second scan
- [x] Re-run dead-code fan-out after batches 1-8 (backend + frontend scans done).

### Second-pass iteration (9.x)
Done concurrently (disjoint FE/BE trees), one combined gate:
- [x] 9-FE: electron <webview> infra; copyImageToClipboard; DIFF_TOOLS/ensureWorkspaceFiles/
      fetchFreshWorkspaceSkills/ZONE_DISPLAY_NAMES/getAncestorPaths/SHIKI_THEME_PAIR_NAMES;
      test-only useIsWorkspaceDeleted/usePanelEnabled/isZoneMoveDisabled/TaskID; folder-reveal-highlight chain.
- [x] 9-BE: H1 KilledAgentRunnerMessage, H2 RunnerMessageUnion, H4 get_messages_for_task(singular),
      H5 Workspace.setup_command_triggered (+migration), H6 TASK_SYNC_DIR, M2 stop_terminal_manager,
      M4 ErrorMessage base, M5 restore_workspace_agent endpoint (+restore_task), InvalidTaskOperation.

### Remaining second-scan items (9.y) — DONE
- [x] H3 setup-reminder provider cluster (batch 9d)
- [x] 2a narrow-scope streaming subsystem → collapsed to all-user (batch 9c)
- [x] 2c/item3 transcript chain (batch 9e)
- [x] 2d no-op task handler (batch 9d)
- [x] Third scan (cascade + LOW assessment) — done.

### Final cleanup (batch 9f) — DONE
- [x] H1 task-container subscription cluster (cascade orphan of scope removal)
- [x] H2 stale SCULPTOR_SYSTEM fake-mock method
- [x] H3 dead SCSS classes (TitleBar/BranchSelector/RepoPathDialog/VersionPopover)
- [x] M2 Environment system-prompt chain (get_system_prompt/WORKTREE_MODE_PROMPT/ATTACHMENTS/to_environment_path + agents/default/constants.py)
- [x] M3 Task.max_seconds column (+migration)
- [x] M4 settings.TESTING / TestingConfig
- [x] M5 NotificationImportance.PASSIVE/.CRITICAL (FE+BE)

### Deliberately NOT removed (verified live or refactor-only, not dead code)
- **git-retry machinery (M1/2a-old): LIVE.** The third-scan "never retries" premise was WRONG — 15+ callers use is_retry_safe=True (default) → RetriableGitCommandFailure + is_transient=True → tenacity retries 3x. Left intact.
- get_jsonl transcript (E1): removed in 9e after all (was deferred in batch 5).
- progress_tracking no-op scaffold: live-wired (report_output_line used as on_output callback) — refactor, not delete.
- Single-impl ABCs (EnvironmentManager/Environment/AgentExecutionEnvironment), single-value enums (WorkspaceInitializationStrategy, ArtifactType), EnvironmentTypes alias: simplifications, not dead code — left for an explicit refactor decision.
- sculptor_folder / from_new_repository(user_email,user_name) params: test-used.

## Simplification refactors (follow-up phase) — DONE
After the dead-code sweep, the deferred "not dead, but single-impl/single-value" refactors were executed:
- **Single-value enums**: `ArtifactType` (→ `DIFF_ARTIFACT_DIRNAME` constant) and
  `WorkspaceInitializationStrategy` (removed the enum, the persisted column +migration,
  the API field, ~40 plumbing sites, and the sculpt `--strategy` flag — all always WORKTREE).
- **Single-impl environment ABCs**: `EnvironmentManager`→`DefaultEnvironmentManager`,
  `AgentExecutionEnvironment`→`LocalAgentExecutionEnvironment`, `Environment`→`LocalEnvironment`
  (merged shared concrete code into the one impl), and dropped the `EnvironmentTypes` single-type alias.
- **No-op `progress_tracking`**: deleted the placeholder module and unthreaded its handles from
  workspace_service + concurrency_group (the no-op on_output collapsed to the caller's callback).
All behavior-preserving; full unit + integration suites green after each.

Integration baseline (before refactors): 103 passed, 3 skipped, 1 xfailed; the lone
`test_discard_file` "failure" was a load flake (passed in isolation), NOT a sweep regression.

## Coverage note
no-op handler removal (9d) dropped 2 task-lifecycle unit tests (idle-finalize, proper-shutdown-kills-runners) that depended on the removed lightweight task type; their assertions (_get_name_for_runner_from_task, stop()-kills-runners) could be re-covered later via a real terminal-agent fixture.

## Targeted subsystem removals + deep cut (later session)
Removed wholesale (each gated green, committed separately):
- **Dead config/scripts/assets**: container/ dir, codex-output-schema.json, dead sculptor scripts, 6 unused SVGs.
- **Dead CSS** (~683 lines), **dead backend** (stdin-writer feature, dead exceptions, test-only helpers), **unused deps** (boto3/pyjwt; electron-squirrel-startup/uuid/user-event/@types-semver/tsx).
- **All CI config** (.github/workflows + actions + scripts/ci + APPROVED_CONTRIBUTORS) and the **Offload** subsystem (offload*.toml, tools/offload-stats, .devcontainer, justfile recipes).
- **Auto-update infrastructure** (generate-autoupdate-manifest, app-update.yml, latest-*.yml feed artifacts, electron-updater helpers).
- **Pi agent** remnants (test-real-pi/install-pi recipes, real_pi marker, stale comments, AGENT_TYPE_MENU_ITEM_PI).
- **Iterate pass**: setuptools package-data stanza (dead globs), CI-orphaned scripts, getFileData/getAppVersion IPC chains, write-only command-palette target atoms, more dead CSS.

### Release pipeline + final telemetry-cruft passes (bottom-out)
- **Release/publish/S3 pipeline DELETED** (maintainer decision): builder cut/promote/hotfix/fixup-release, publish/snapshot/retrieve-build-artifacts, bump-version, verify-release-tag, s3 helpers, artifacts.py + tests; matching justfile recipes/aliases; create-version-file --annotate-dev. Kept local build/package (build-backend/frontend, package-*, dist, refresh + version/setup-build-vars→removed/create-version-file/sync-frontend-version/validate-darwin-binary).
- **Cascade**: version helpers VersionComponent/is_prerelease/next_version/is_devrelease + tests.
- **Final telemetry cruft**: dead Vite defines (FRONTEND_SENTRY_*/POSTHOG_*), setup-build-vars + its recipe `eval`s, inert ci_job_id/ci_ref version metadata (CI gone → always null) end-to-end, docs/development/posthog.md.
- A final confirmation scan verified structural bottom-out (every remaining builder cmd / script / helper traces to a live caller). Self-corrected a nested-worktree false positive (CI-Babysitter is a LIVE product feature; not CI).

### Open items needing a decision (NOT plain dead code — flagged, not removed)
- **Broader stale telemetry references**: `// former @sentry/react`-style comments in App.tsx/useWebsocket.ts/localStorageMigrationLogic.ts (intentional breadcrumbs explaining vanilla replacements — probably keep) and telemetry mentions in docs/specs/*. Doc cleanup, judgment call.
- **Builder release/publish/S3 cluster** (~700 LOC): verify-release-tag/check_release_tag, publish/snapshot/retrieve-build-artifacts + s3_copy, artifacts.py, create-version-file --annotate-dev, cut/promote/hotfix-release. Still `just`-recipe-reachable but CI-decapitated (no automated trigger after CI removal). Delete only if manual desktop releases are not intended.
- **Toast variant CSS** (`.success/.error/.warning`): latent styling bug — `styles[type]` uses uppercase ToastType values but CSS keys are lowercase, so these toasts render unstyled. Bug fix, not dead code.
- **Pre-existing `sculpt run` integration failures** (terminal-readiness 409): predate this work (terminal_input.py untouched by it); ~5 tests in test_sculpt_cli.py.
