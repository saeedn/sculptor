# Slim-down branch — post-review findings & port plan

Consolidated output of a 5-way review (correctness sweep, backend dead-code,
frontend dead-code, further-cuts assessment, upstream PR triage) run at
aa4612ac8e (2026-07-01). Verification gate at that commit: `just check` and
all four `just test-unit` suites green.

**Verdict:** the slim-down is complete and correct. Every open finding from
`review.md` is resolved at HEAD — notably H2 (stranded initial prompt):
`CreateAgentRequest` no longer accepts a prompt, and `sculpt run` creates
promptlessly then delivers via the terminal-input endpoint. The removal work
structurally bottomed out: no dead HTTP routes, keybindings, palette
commands, or CLI subcommands remain. What's left: 3 real bugs, stale dev/test
infra + docs, a modest dead-code residue, discretionary further cuts, and
~14 upstream PRs worth porting.

Sections 1–3 are actionable (checkboxes). Sections 4–5 are decisions for the
owner.

## 1. Actual bugs

- [x] **1.1 `sculpt agent list --workspace/--project` silently lists agents
  from ALL workspaces.** The CLI still sends a `scope=` query param
  (`tools/sculpt/sculpt/ws_client.py:43-59`) that the server no longer
  implements (batch-9c removed the server side; FastAPI silently ignores the
  param), and `commands/agent.py:175-203` applies no client-side
  workspace/project filter (only `--status`). Existing tests only assert
  presence, so they pass. Fix: filter client-side; delete the scope husk
  (`ScopeMalformedError`/`ScopeForbiddenError`/`ScopeNotFoundError`,
  `_wrap_invalid_status`, the catch blocks in
  `commands/agent.py:190-195,439-445,463-468`).
- [x] **1.2 Toast variants render unstyled.** `components/Toast.tsx:13-19`
  uses uppercase values (`"SUCCESS"`/`"ERROR"`/`"WARNING"`) while
  `Toast.module.scss:48/57/66` keys are lowercase, so `styles[type]` at
  `Toast.tsx:60` is undefined for all three (only `errorProminent` aligned).
  ~25 call sites affected; reachable live via `NotificationToasts.tsx:16-19`.
  (Upstream #142 contains the same fix.)
- [x] **1.3 Expand mode can blank the workspace given pre-slim
  localStorage.** `DockingLayout.tsx:47-52` hardcodes right/bottom hidden
  when expanded; zone reconciliation (`PanelRegistryProvider.tsx:74-79`)
  only resets zones not in `ZONE_IDS`, so a drag-era persisted assignment
  like `files: "top-right"` (localStorage is NOT covered by the fresh-start
  guard) makes expand hide every panel until Escape. Fix: reconcile any
  persisted zone assignment that differs from the fixed default.
- [x] **1.4 Minor nits:** `ws_client.py:87` lists removed `"CANCELLED"` as a
  terminal task status; `PrStatusInfo.error_provider`
  (`web/data_types.py:84`, written `pr_status.py:45`,
  `pr_polling_service.py:706`) and `PrStatusInfo.mismatched_pr_web_url`
  (`data_types.py:88`, written `pr_status.py:106`) are write-only — remove
  both fields (+ regen).

## 2. Completeness gaps (stale references to removed features)

- [x] **2.1 Custom-backend-command test/dev cluster** (Electron no longer
  implements the mechanism): `justfile:585-606` `frontend-custom` recipe;
  `electron-custom-command` launch mode in `sculptor/conftest.py:77-138`;
  `testing/resources.py:481-530` `_create_custom_command_instance`;
  `testing/electron_frontend.py:57,113-114` env var;
  `sculptor/pytest.ini:14` `electron_custom_command` marker (zero tests use
  it). Delete the cluster.
- [x] **2.2 Packaged-launch-mode harness is CI-decapitated**:
  `testing/packaged_electron_frontend.py`, `packaged_backend_frontend.py`,
  `packaged_utils.py`, the `--packaged-binary-path` option +
  `packaged-electron`/`packaged-backend` conftest branches
  (`sculptor/conftest.py:68-70,117-146`), the `packaged_electron` marker +
  collection-time guard. No recipe or script invokes these modes; the
  release pipeline that ran them was deleted. (`@release`-marked tests
  still run in the normal suite — keep the tests, drop the packaged
  plumbing.)
- [x] **2.3 `justfile check-reserved-plugin-names`** (justfile:354-379,
  wired into `just check`) guards plugin dirs that no longer exist —
  permanently a no-op. Delete.
- [x] **2.4 docs/specs document removed features as current**: GitLab/MR as
  a live provider (`docs/specs/requirements.md:189,266-272,344`,
  `SPEC.md:261,398-408,653`,
  `scenarios.md:376,423-426,651-701,816,1241-1242,1485`,
  `scenario_coverage.md:179-180` citing deleted tests); zen/focus mode +
  Skills panel (removed after the spec-reconcile commit:
  `SPEC.md:491-514,790`, `scenarios.md:184-201,836,1051-1069,1219`,
  `scenario_coverage.md` citing deleted `test_zen_mode.py` /
  `test_side_toggle.py`); `requirements.md:206,225` still requires
  `internal/uploads/`.
- [x] **2.5 Test-infra docs + bundled skills teach the removed FakeClaude /
  rich-chat harness**: `docs/development/review/integration_tests.md`
  (fake_claude commands, `FakeClaudePause`, `ALPHA_CHAT_VIEW`,
  `electron_custom_command`/`test_image_upload.py`, release-pipeline
  section); `docs/development/testing.md:22-23`;
  `sculptor/tests/integration/frontend/README.md:60,102-103,156`;
  `.sculptor/testing.md:10`; `sculptor/pytest.ini:17` "(no FakeClaude
  available)"; `.claude/skills/write-integration-test/SKILL.md` (whole
  skill); `.claude/skills/debug-integration-test/SKILL.md:63-73,209`;
  `.claude/skills/measure-react-renders/scenarios/*` + `scripts/*`
  (ChatInput/TipTap, `mode: 'IN_PLACE'`);
  `.claude/skills/storybook-screenshot/SKILL.md:124-236` (deleted
  stories); `.claude/skills/auto-qa-changes/SKILL.md:594` (`CHAT_INPUT`).
  Rewrite against the fake registered terminal agent harness.
- [x] **2.6 Stale comments**: `web/pr_status.py:160` ("an MR");
  `ci_babysitter_service/coordinator.py:262` ("an PR" typo);
  `foundation/subprocess_utils.py:728-731` (message_conversion /
  fake_claude MCP references); `git_repo_service/default_implementation.py:226`
  ("diagnostics uploads"); `DockingLayout.tsx:97,139` (drag/drop);
  `test_ci_babysitter.py:65-70,80` (deleted "bump" pattern, unimplemented
  `closed` mode); `stories/custom/SettingRow.stories.tsx:65` ("Custom
  Backend Command" sample); `vite.base.config.ts:154`
  `SCULPTOR_CUSTOM_BACKEND_URL` naming; `WorkspacePeekPopover.module.scss:264`
  `.mrRow`; `createMergeRequest`/`openMergeRequest` method naming.

## 3. Dead code residue

### Backend (provably dead)

- [x] **3.1 `UserSettings` subsystem husk**: zero-data-field model
  (`database/models.py:29-33`), DB table, `get_user_settings` /
  `get_or_create_user_settings` (`data_model_service/data_types.py:162-165`,
  `sql_implementation.py:198-223`), auth threading (`web/auth.py:48,85-88`),
  stream arms (`streams.py:460-462`, `sql_implementation.py:805,867-872`),
  `UserUpdate.user_settings` (`derived.py:346`; zero FE/CLI reads),
  `UserSettingsID`. Regen after.
- [x] **3.2 `SculptorSettings` stream arm unreachable**: no producer ever
  enqueues one. `web/data_types.py:512` union, `streams.py:395-396,467-469`.
- [x] **3.3 `AgentCrashed` chain has no producer**:
  `interfaces/agents/errors.py:8` (raised only by its own test), the
  unreachable `case AgentCrashed()` arm
  (`runner_support.py:109-114`), `AgentCrashedRunnerMessage`
  (`interfaces/agents/agent.py:52-60` + union tag :103; persisted union →
  frozen-schema bump), `errors_test.py`.
- [x] **3.4 `UserSession.user_email` + `ANONYMOUS_USER_EMAIL` + EmailStr
  plumbing**: `web/auth.py:38,49,81,89`; `database/automanaged.py:57`
  EmailStr column mapping; `sql_implementation.py:563` isinstance branch.
  Then drop the `email-validator` dep.
- [x] **3.5 Dead test infra**: `sculptor/conftest.py:154` `database_url_`,
  `:160` `port_manager_`; duplicate `sculptor_launch_mode` fixtures
  (`tests/integration/frontend/conftest.py:7`,
  `tests/integration/real_claude/conftest.py:34`);
  `fake_terminal_agent.py:247` `stop_fake_terminal_agent` (+ now-unreachable
  `__quit__` branch `fake_terminal_agent_runner.py:152`);
  `playwright_utils.py:450,502,517` (`navigate_away_and_back`,
  `get_local_storage_item`, `remove_local_storage_item`);
  `dependency_stubs.py:316` `create_claude_version_stub_dir`; ~30 orphaned
  POM methods (action_dialog:48,52; actions_panel:15; agent_tab:29,94,115;
  command_palette:18,29,33,40,58,61,64; diff_panel:41,107,110,127;
  settings_actions:19,23,27; toast:24,27,33; warning_banner:8;
  workspace_peek:22; add_workspace_page:37; onboarding_page:22;
  project_layout:130,158; settings_page:27; task_page:35,93); permanently
  skipped `test_restarts.py:79-96` targeting never-rendered `TASK_INPUT`;
  vacuous `TERMINAL_HEADING` count-0 assertion
  (`test_terminal_tab_enhancements.py:104` + `elements/terminal.py:374`);
  empty `tests/acceptance/` + `tests/benchmark/` scaffolds + the
  `just benchmark` recipe that collects nothing.
- [x] **3.6 Unused Python deps**: `python-multipart` (main), `pillow` (dev),
  `ty` (+ `[tool.ty.*]` config), `pyyaml` (runtime dep whose only consumer
  is the justfile `check-yaml` one-liner → move to dev), duplicate
  `filelock` declaration (keep main, drop dev dup).
- [x] **3.7 Backend likely-dead (judgment, approved)**:
  `Notification.project_id` (never written non-None; FE read trivially
  always-true) + no-producer `user_reference=None` broadcast semantics;
  `NotificationImportance` single-value enum (persisted column; FE switches
  constant-fold); `HealthCheckResponse.python_version` (zero readers);
  `get_workspace_include_deleted` (tests only);
  `TaskStatusRunnerMessage.outcome` field (never read — keep the message
  itself; it may act as a stream poke); `foundation/common.py` science
  chain (`is_on_osx`/`get_filesystem_root`/`get_temp_dir`) +
  `foundation/test_utils.py` `create_temp_dir` (serve one test → use
  `tmp_path`); `Coordinator._git_repo_service` stored-never-read;
  `start_task_and_wait_for_ready` no-op back-compat params
  (`playwright_utils.py:236-238`: `prompt`, `wait_for_agent_to_finish`,
  `model_name`) + ~57 call sites still passing them; `is_worth_notifying =
  True` constant fold (`runner_support.py:106,130`); stale-scope docstrings
  (`task_service/base_implementation.py:441-443,466-469`,
  `ws_client.py:48`).

### Frontend (provably dead)

- [x] **3.8 Unused npm deps**: `react-markdown`, `remark-gfm` (orphaned by
  35833a237d), `highlight.js`, `@dnd-kit/utilities`, `@floating-ui/dom`;
  likely also `playwright` (npm devDep; all Playwright use is Python),
  `@vitest/coverage-v8` (no --coverage invocation), `@radix-ui/colors`
  (comment-only references — the "depcheck false positive" keep looks
  wrong; verify then drop).
- [x] **3.9 Orphaned `.markdownBody` SCSS block**
  (`ReadOnlyPreview.module.scss:19-70`, consumer deleted by 35833a237d).
- [x] **3.10 Dead FE runtime bits**: `isZoneVisibleAtom`
  (`components/panels/atoms.ts:115-117`); command-palette `runtime.electron`
  slice + `runtime.ui.toggleDevPanel` (`runtime.ts:35,73-76`,
  `useCommandRuntime.ts:17-24,97,112,134,145,165` + 6 test fixtures);
  `PanelContextMenu.tsx` (renders only a label, zero items; unread `zoneId`
  prop); `.storybook/vitest.setup.ts` (no consumer).
- [x] **3.11 Dead ElementIDs** (+ POM accessors, + regen): `TASK_INPUT`,
  `AGENT_TYPE_MENU_ITEM_CLAUDE`, `TERMINAL_HEADING`,
  `COMMAND_PALETTE_FOOTER` (negative assertion `CommandPalette.test.tsx:653`
  trivially true).
- [x] **3.12 Dead props** (declared, no caller passes): `TabBarProps.maxTabWidth`
  / `.className` (types.ts:32,37); `ResizeHandleProps.className` /
  `data-testid` (ResizeHandle.tsx:15,17); `PanelHeaderProps.afterTitle`;
  `PierreDiffViewProps.className`; `BranchSelectorCore`
  `specialBranchFilter`/`contentTestId`/`height`;
  `ActionContextMenu.onOpenChange`; `Code.isUnderlined`/`.isClickable`;
  `HotkeyChip.disabled` (+ its dead branches 122,133,140,173,184).
- [x] **3.13 `data-droppable-id`** (`LeftSidebar.tsx:12`,
  `RightSidebar.tsx:12`): production-dead; load-bearing only in
  `DockingLayout.test.tsx:112`. Switch the test locator, then drop.

### Implementation verification (2026-07-02)

Sections 1-3 were implemented across commits bfe39a9f1a..b6ed5304ec.
Gates at HEAD: `just format`, `just check`, and all four `just test-unit`
suites green. Full integration suite (RUN_ALL=1, frontend + regression):
**412 collected == 412 executed; 400 passed, 5 skipped, 1 xfailed, 6
failed**. All 6 failures were re-run in isolation and against the
pre-change commit aa4612ac8e:

- 4 passed on the isolation re-run (load flakes under -n8).
- `test_workspace_scoped_changes.py::test_changes_tab_shows_diffs_from_all_agents`
  flakes ~50% solo at BOTH HEAD and aa4612ac8e (an add-agent double-fire
  race: 3 AGENT_TABs where 2 are expected) — pre-existing; upstream #165
  fixes this class.
- `test_workspace_close_vs_delete.py::test_cmd_shift_w_deletes_active_workspace`
  failed 1-of-2 solo at HEAD, 0-of-5 at aa4612ac8e; its signature (Radix
  delete-confirmation dialog detaching the confirm button mid-click) is the
  known dialog-animation race family, and nothing in the diff touches that
  dialog. Attributed to pre-existing flake; keep an eye on it. Upstream
  #169/#181 harden adjacent surfaces.

## 4. Further cuts (owner decisions — NOT yet approved)

**Should-cut by the spec's own logic:**
- **A1 Perfetto/viztracer tracing pipeline** (~800 LOC product code):
  `utils/tracing.py` (283), auth-exempt `POST /api/v1/trace/batch`
  (`app.py:2877-2903`), `frontend/src/common/tracing.ts` (195),
  `trace_endpoint_test.py`, `--trace-to` plumbing, `viztracer` dep,
  `just test-tracing`. Shipped multi-process profiling in a slim
  single-user product.
- **A2 Backend Notification persistence**: table + enum + scoping whose
  sole producer is one hard-coded "Agent failed." string
  (`runner_support.py:133-141`). Replace with a transient stream event.
- **A4 `task_service` 3-tier ABC hierarchy**: only `LocalThreadTaskService`
  is ever constructed; ~800 LOC collapse
  (`base_implementation.py`/`concurrent_implementation.py`/`threaded_implementation.py`).
- **A5 Stale-fork tooling**: `depot` install in `install-build-deps`;
  Electron sign/notarize config in `forge.config.ts` (hardcoded imbue
  identity, Vault-injected creds); x86_64 macOS cross-build recipes +
  `builder/*-x86_64.sh`; `.claude/skills/write-release-notes` (keyed to
  imbue release versions).

**Could-cut (judgment calls):**
- **B1 Custom Actions subsystem** (~2,000+ LOC): ActionsPanel (681, with
  dnd-kit drag-grouping), ActionsSettingsSection (613) + ActionGroupSection
  (179), ActionDialog (176) + dialogs/menus. Real working feature; not one
  of the four pillars. At minimum drop drag-to-group.
- **B2 WorkspacePeekPopover** (~700 LOC) — hover preview whose richest
  backend fields were already gutted to None/0.
- **B3 Multi-user/org auth scoping**: `UserSession.{user_reference,
  organization_reference}` + `UserReference`-keyed observer fan-out
  (`sql_implementation.py:592-885`) always resolve to `ANONYMOUS_*`. Keep
  the CSRF `SessionTokenMiddleware`. Wide mechanical refactor — dedicated
  pass.
- **B4 Git-poller consolidation**: three independent 3s pollers per
  workspace (`diff_refresh.py`, `repo_polling_manager.py:69,254`) with two
  redundant branch→diff-refresh paths. Note upstream **#185** replaces
  `repo_polling_manager.py` outright — take together.
- **B5 Frozen-JSON-schema migration guard** (~520 LOC:
  `frozen_pydantic_schemas.json`, `json_migrations.py`,
  `migration_test_utils.py`, `alembic/utils.py`, `bump_migrations.py`) —
  keep if incremental migrations continue; cut if clean-break-forever.
- **B6 sculpt marginal subcommands**: `--follow` streaming half (~190 LOC),
  `sculpt schema`, agent/workspace rename/delete, `repo show`. Small wins;
  keep symmetric CRUD.
- **B7 Dev-tools-in-prod-bundle**: VersionPopover devtool switches,
  `components/DevPanel/` + TanStack devtools mount (401) + `react-grab`.
- **B8 Environment-variables settings section** — likely KEEP (it's how
  users pass tokens to agent PTYs).

**Keep (surveyed, earns its place):** all 60+ HTTP routes (every one has a
live caller; 5 are CLI-only), workspace_service, streams.py,
ConcurrencyGroup, MRU (three small uses), file browser + diff viewer
(REQ-CORE-4), builder local-packaging half, 13/14 .claude skills.

## 5. Upstream PR port list (d457af55b2..upstream/main, 101 commits triaged)

~60 SKIP (touch only removed subsystems, or already done equivalently here:
#132 GitLab-strip, #137 terminal-model, #159 nvm pin, #150 update-specs,
#203 sculpt-send-PTY). #210 (credential redaction) fixes a feature that
never landed here. #130 (npm→pnpm) is a standalone decision. #93/#195 are a
self-cancelling add+revert pair.

**High priority — clean/near-clean cherry-picks, in order:**
| PR | What it fixes | Pick |
|----|---------------|------|
| #205 | Python 3.14 pydantic default-factory memory leak (multi-GB RSS) | clean (additive `foundation/pydantic_serialization.py`) |
| #190 | Reliable busy/idle/waiting via Claude CLI hooks (SessionStart + idle_prompt matchers; hash-gated managed-file refresh) | clean — registry files byte-identical |
| #180 | `sculpt signal` retry + explicit timeout (hooks depend on it — take with #190) | near-clean |
| #173 | Terminal agents unread/green after restart — slim still has the buggy fallback at `derived.py:212-215` | clean |
| #243 | Detached-HEAD placeholder selectable as source branch | near-clean |
| #198 | Terminal freeze after macOS sleep (`useTerminal.ts`) | near-clean |
| #135 | Focus terminal pane when tab selected | near-clean |
| #192 | Active-workspace delete strands blank /ws/new tab | light manual |
| #181 | Flaky read/unread indicators (useMarkRead/statusUtils/AgentTabs) | light manual |
| #191 | Batch GitHub PR-status polling (rate limits) — slim's files ~12 lines from upstream base | mostly clean |

**High priority — manual ports:** #164 (babysitter all-agents-idle gate;
re-derive "busy" from hook-driven terminal status; NB it DROPS, not defers,
busy-time failures), #134 (persist babysitter pause across restart — fold
column into the squashed initial migration), #231 (workspace branch-name
validation; drop the dependency-management hunk), #185 (git-ref scanning
replaces `repo_polling_manager.py`; pairs with B4).

**Medium:** #166+#170 (Electron harness relaunch; clean picks in that
order), #216 (backend unit-test flake stabilization incl. spawned_pty),
#199 (terminal connection indicator + terminal_socket_mock), #169
(Cmd+Shift+W delete-dialog fix), #189 (workspace-service tests →
tmp_path), #184 (Auth.ts origin fallback, 3-liner), #165 (add-agent race,
manual), #228 (`just doctor`), #153 (build-warnings hygiene, surviving
hunks), #162/#133 (settings navigation hunks; drop chat-alpha/slimmed
parts), #220 (WorkspaceTabs `getCurrentTabIdFromHash` fix only), #149
(`workspaces.ts` applyClose clamp — reload-bounces-to-/ws/new bug exists
here), #142 (hand-pick fixes in ~10 surviving files; includes the Toast
fix in 1.2).

**Low:** #244 (fix-bug skill diff base), #226 (style-guide comment rules),
#223+#240 (post-pr-to-slack skill), #193 (update-specs SKILL.md hardening
only), #167 (pydantic-settings bump), #236/#214 (scrollbar polish,
partial), #163+#171+#168 (profiling trio — moot if A1 tracing is cut),
#178 (likely superseded by the slim terminal test rewrite).
