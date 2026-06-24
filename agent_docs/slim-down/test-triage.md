# Sculptor Slim — Integration Test Triage

Companion to `architecture.md`. This is the REQ-TEST-1 deliverable: a
**per-file, deliberate** classification of every integration test against
the slimmed (terminal-agents-only) feature set. It is an *assessment*, not
the edits — the actual deletes/rewrites and their sequencing are Plan/Build
work. Verdicts:

- **DELETE** — the test's subject is a removed surface; the behavior is gone.
- **REWRITE** — the subject survives, but the test drives it through
  `FakeClaude` / rich chat and must be re-expressed against a terminal agent
  (the future fake registered terminal agent, REQ-TEST-4).
- **KEEP** — subject survives and the test depends on no removed surface
  (often already terminal-based or pure surviving-UI). No change needed.
- **REWRITE? / DELETE?** — genuinely ambiguous; needs a human call (see the
  *Ambiguous* section). Counted under their base verdict in totals.

The classification rule (removed vs. surviving surfaces, decide by *subject*
not *vehicle*) is in `architecture.md` → Testing Strategy. Method: 8 parallel
classification agents read every file in their batch (no sampling) and
applied that rule; ambiguities were flagged rather than guessed.

## Totals

See the per-directory tables below. Aggregate counts are computed from the
verdict column (the base verdict for ambiguous rows):

| scope | DELETE | REWRITE | KEEP | files classified | (+infra) |
|---|---|---|---|---|---|
| frontend | 116 | 65 | 28 | 209 | +2 = 211 |
| regression | 18 | 15 | 2 | 35 | +2 = 37 |
| real_claude | 15³ | 0 | 3¹ | 18 | — |
| real_pi | 17³ | 0 | 0 | 17 | — |
| **total** | **166** | **80** | **33** | **279** | +6 = 285² |

¹ real_claude KEEP = the one surviving terminal-agent test + its
`__init__`/`conftest`. ² The "+infra" column holds the frontend, regression,
and root `__init__`/`conftest` files (2+2+2). ³ The real_claude (18) and
real_pi (17) figures **fold in their own 3 infra files each**
(`__init__`/`conftest`/`helpers`), counted under their verdicts (e.g.
`helpers.py` → DELETE), rather than in the "+infra" column — that is why the
column is "files classified," not "test files." Genuine `test_*.py` files =
**273**; all integration `.py` = **285**. All previously-ambiguous rows are
resolved (see §6); one further row was reclassified in review (see §6, row 7).

**So: ~60% of the suite is DELETE, ~29% REWRITE against the fake terminal
agent, ~12% KEEP.** The REWRITE bucket (80 files) is the real work — it is
what sizes the REQ-TEST-4 fake-terminal-agent harness and validates the
architecture's "narrower than FakeClaude" assumption: every REWRITE row
above needs only the side-effecting DSL (write/edit/bash/git) plus
lifecycle signals, never the chat/JSONL/MCP surface.

Headline: the rich-chat render tree (`chat-alpha/`, tool pills, status
pills, turn footers, AUQ/plan blocks), the ChatInput controls
(model/fast-mode/effort/@-mentions/pseudo-skills), Pi, telemetry, deps,
theme builder, dnd panels, and clone/in-place workspaces account for the
bulk of **DELETE**. The **REWRITE** bucket is dominated by surviving
git/diff-viewer, workspace/tab-lifecycle, PR-tracking, babysitter,
setup-command, and restart-persistence tests that only used `FakeClaude` as
a vehicle to mutate the workspace.

---

## §1. frontend (`sculptor/tests/integration/frontend/`)

| file | verdict | fakeclaude | subject | rationale |
|---|---|---|---|---|
| test_add_workspace_agent_type.py | REWRITE | no | Add-Workspace first-agent type picker | workspace creation + terminal-agent selection survive; pi-gating subtest drops, Terminal/MRU subtests survive |
| test_add_workspace_page.py | REWRITE | yes | Add Workspace form / workspace lifecycle | creation, draft persistence, branch select, project-delete cascade survive; FakeClaude only confirms the agent responds |
| test_agent_diagnostics_context_menu.py | REWRITE | no | agent-tab Diagnostics context menu | multi-agent tab + diagnostics survive; driven via a Claude chat agent |
| test_agent_settings.py | DELETE | yes | Agent settings: model/fast-mode/effort defaults | removed ChatInput controls + rich Claude config |
| test_agent_tab_context_menu.py | REWRITE | no | agent-tab rename/delete context menu | multi-agent + tab management survive |
| test_agent_type_menu.py | REWRITE | no | `+` agent-type menu (terminal/registered/bundled) | terminal+registered+bundled survive; pi-gating drops |
| test_alpha_ask_user_question.py | DELETE | yes | AskUserQuestion inline block | AUQ block + alpha chat removed |
| test_alpha_chat_auto_bg_bash.py | DELETE | yes | alpha chat bash-block segmentation | alpha render tree removed |
| test_alpha_chat_bash_block.py | DELETE | yes | alpha chat bash pill rendering | alpha render tree removed |
| test_alpha_chat_bash_block_advanced.py | DELETE | yes | alpha chat bash block rendering | alpha render tree removed |
| test_alpha_chat_chip_rendering.py | DELETE | yes | alpha chat chip rendering (@-file/folder/entity) | alpha + @-mentions removed |
| test_alpha_chat_chip_row.py | DELETE | yes | alpha chat file-change chip rows | alpha render tree removed |
| test_alpha_chat_chip_row_advanced.py | DELETE | yes | alpha chat chip row rendering | alpha render tree removed |
| test_alpha_chat_edit_outside_workspace_chip.py | DELETE | yes | alpha chat out-of-workspace edit chip | alpha render tree removed |
| test_alpha_chat_intro.py | DELETE | yes | alpha chat intro text | alpha render tree removed |
| test_alpha_chat_mixed_tools.py | DELETE | yes | alpha chat mixed-tool rendering | alpha render tree removed |
| test_alpha_chat_subagent.py | DELETE | yes | alpha chat subagent pill | alpha + subagent pill removed |
| test_alpha_chat_subagent_parallel_bash.py | DELETE | yes | alpha subagent/bash pill grouping | alpha render tree removed |
| test_alpha_chat_table_wrap_toggle.py | DELETE | yes | alpha chat table wrap toggle | rich-chat table rendering removed |
| test_alpha_chat_tool_block_file_chips.py | DELETE | yes | alpha chat file chips in tool blocks | alpha render tree removed |
| test_alpha_chat_tool_density.py | DELETE | yes | alpha chat tool-density toggle | rich-chat tool-pill rendering removed |
| test_alpha_chat_tool_grouping.py | DELETE | yes | alpha chat tool render-group shape | alpha render tree removed |
| test_alpha_chat_view.py | DELETE | yes | alpha chat view (messages/tools/AUQ/plan/pills) | alpha render tree + AUQ + plan removed |
| test_alpha_nested_list_rendering.py | DELETE | yes | alpha nested-list markdown | rich-chat markdown removed |
| test_alpha_ordered_list_numbering.py | DELETE | yes | alpha ordered-list markdown | rich-chat markdown removed |
| test_alpha_prompt_navigator_interactions.py | DELETE | yes | alpha prompt-navigator dot rail | chat nav removed |
| test_alpha_scroll_auto_scroll.py | DELETE | yes | alpha auto-scroll / jump-to-bottom | rich-chat scroll removed |
| test_alpha_scroll_behaviors.py | DELETE | yes | alpha scroll behaviors | rich-chat scroll removed |
| test_alpha_scroll_padding_agent_switch.py | DELETE | yes | alpha scroll padding on agent switch | rich-chat scroll removed |
| test_alpha_scroll_prompt_nav.py | DELETE | yes | alpha keyboard prompt navigation | chat nav removed |
| test_alpha_scroll_search.py | DELETE | yes | alpha in-chat search | chat search removed |
| test_alpha_scroll_task_switch.py | DELETE | yes | alpha scroll persistence across task switch | rich-chat scroll removed |
| test_alpha_scroll_to_top.py | DELETE | yes | alpha scroll-to-top on send | rich-chat scroll removed |
| test_alpha_streaming_cursor.py | DELETE | yes | alpha streaming cursor | smooth-streaming / alpha removed |
| test_alpha_tool_pill_hover.py | DELETE | yes | tool-pill hover popover | rich-chat tool pills removed |
| test_alpha_tool_pill_keyboard.py | DELETE | yes | tool-pill row keyboard nav | rich-chat tool pills removed |
| test_alpha_tool_pill_pin.py | DELETE | yes | tool-pill click-to-pin popover | rich-chat tool pills removed |
| test_alpha_tool_pill_popover.py | DELETE | yes | tool-pill popover targeting | rich-chat tool pills removed |
| test_arrow_nav_does_not_trigger_slash_command.py | DELETE | no | ChatInput `/` skill picker | ChatInput slash picker removed |
| test_ask_user_question.py | DELETE | yes | AskUserQuestion interactive block | AUQ block removed |
| test_ask_user_question_continue.py | DELETE | yes | AUQ continue-after-error | AUQ block removed |
| test_ask_user_question_focus.py | DELETE | yes | AUQ panel focus vs terminal | AUQ block removed |
| test_ask_user_question_invalid_input.py | DELETE | yes | AUQ MCP invalid-input | AUQ + sculptor MCP removed |
| test_at_mention_completion.py | DELETE | no | ChatInput @-mention file completion | @-mentions removed |
| test_at_mention_file_chip_click_opens_tab.py | DELETE | yes | @-mention chip → diff tab | @-mentions/chips removed |
| test_at_mention_keyboard_navigation.py | DELETE | no | @-mention picker arrow keys | @-mentions removed |
| test_at_mention_path_mode.py | DELETE | no | @-mention path-mode browsing | @-mentions removed |
| test_at_mention_tab_drill_and_shift_tab.py | DELETE | no | @-mention Tab/Shift-Tab folder drill | @-mentions removed |
| test_auto_collapse_combined_diff.py | REWRITE | yes | diff viewer auto-collapse (Review All) | diff viewer survives; drop experimental Review-All gate |
| test_auto_update_browser.py | DELETE | no | auto-update UI (version popover/toasts) | auto-update removed |
| test_auto_update_disabled_electron.py | DELETE | no | auto-update disabled env | auto-update removed |
| test_auto_update_electron.py | DELETE | no | auto-update lifecycle (electron) | auto-update removed |
| test_backend_pr_polling.py | REWRITE | no | PR-status tracking/badges | PR tracking survives; uses fake gh + plain spawn |
| test_backend_shutdown_stall.py | DELETE | no | auto-update quitAndInstall stall recovery | exists only for removed auto-update install |
| test_background_subagent_rendering.py | DELETE | yes | alpha subagent pill / message merge | rich-chat render tree removed |
| test_blocked_version.py | DELETE | no | onboarding blocked-Claude-version install | deps + onboarding install removed |
| test_branch_name_collisions.py | REWRITE | no | branch-name collision on workspace create | worktree collision survives; drop clone-mode test |
| test_branch_switching_integration.py | REWRITE | yes | branch selector on workspace create | branch-from-branch survives; drop in-place test |
| test_browser_panel.py | DELETE | no | experimental Browser panel | experimental opt-in panel, not a survivor |
| test_btw.py | DELETE | yes | `/btw` side-chat pseudo-skill + popup | /btw removed |
| test_bundled_linear_plugin.py | DELETE | no | bundled Linear frontend plugin | frontend plugins removed |
| test_chat_input_send_error.py | DELETE | no | ChatInput send-error contract (TipTap) | ChatInput removed |
| test_chat_search_bar.py | DELETE | yes | Cmd+Shift+F chat search | chat search removed |
| test_ci_babysitter.py | REWRITE | yes | CI Babysitter | babysitter survives (drives registered terminal agent); re-express FakeClaude-driven scenarios |
| test_claude_auth_paste_code.py | DELETE | no | onboarding Claude paste-code auth | deps auth + onboarding install removed |
| test_claude_binary_installation.py | DELETE | no | Claude binary install / deps settings | deps/managed-tools removed |
| test_claude_configuration.py | DELETE | no | rich Claude SDK local config (.claude/MCP/slash) | rich SDK + sculptor MCP removed (already skipped) |
| test_claude_errors.py | DELETE | yes | rich Claude SDK CLI error resilience | rich SDK process/error handling removed |
| test_clone_local_only_branch.py | DELETE | no | clone workspace from local-only branch | clone workspaces removed |
| test_clone_mode_branch_name.py | DELETE | no | clone-mode branch-name field | clone workspaces removed |
| test_closed_workspaces_dropdown.py | KEEP | no | Workspace tab lifecycle (close/reopen/delete) | surviving lifecycle; no FakeClaude/rich-chat |
| test_command_palette.py | REWRITE | yes | Command palette | palette survives; clean removed commands (theme/Report a problem), one FakeClaude agent subtest |
| test_commit_from_changes_tab.py | REWRITE | yes | Commit from Changes tab (git/diff) | survives; FakeClaude write_file vehicle |
| test_component_gallery_tab.py | DELETE | no | Component Gallery via Theme Builder | reached only via removed Theme Builder |
| test_copy_image_context_menu.py | DELETE | no | Copy Image on chat/composer images | chat image input removed |
| test_custom_actions.py | REWRITE | no | Custom actions / actions panel | RESOLVED: actions panel survives (chatActionsAtom is agent-agnostic; useTerminalChatActions routes to PTY). Rewrite only the draft-into-chat-input subtest against a terminal agent |
| test_delete_last_repo.py | KEEP | no | Repo deletion → onboarding ADD_REPO | surviving repo/settings lifecycle |
| test_diff_loading_bar_no_file.py | REWRITE | yes | Diff panel loading bar | diff viewer survives; FakeClaude write_file |
| test_diff_refresh_on_branch_change.py | REWRITE | yes | Diff refresh on branch change | diff/git survives; FakeClaude vehicle |
| test_diff_scope_and_fullscreen.py | REWRITE | yes | Diff scope picker / expand (Review All) | diff viewer survives; drop Review-All gate |
| test_diff_scope_switching.py | REWRITE | yes | Diff scope switching | diff viewer survives; FakeClaude vehicle |
| test_diff_tab_close_others.py | REWRITE | yes | Diff tab context menu (close others) | diff viewer survives; FakeClaude vehicle |
| test_discard_file.py | REWRITE | yes | Discard file from Changes panel | diff/git survives; FakeClaude vehicle |
| test_discard_preserves_all_tab.py | REWRITE | yes | Discard + All/Uncommitted scope | diff/git survives; FakeClaude vehicle |
| test_entity_mention_persistence.py | DELETE | no | Entity @/+ mention chips in ChatInput | entity mentions removed |
| test_entity_picker_workspace_drill.py | DELETE | no | Entity picker (+-mention) drill | @-mentions removed |
| test_error_states.py | REWRITE | yes | Agent error/crash states + workspace peek | error surfacing survives; driven by FakeClaude error commands |
| test_expand_escape.py | REWRITE | yes | Expanded diff view (Review All) Escape | diff viewer survives; drop Review-All gate |
| test_fast_mode_persistence.py | DELETE | yes | Fast-mode toggle + model selector | removed ChatInput controls |
| test_file_browser.py | REWRITE | yes | File browser + diff panel | file/diff viewer survives; FakeClaude vehicle |
| test_file_browser_symlink_replaces_directory.py | REWRITE | yes | Changes tab tree (symlink dup-row) | file browser survives; FakeClaude vehicle |
| test_file_browser_tabs.py | REWRITE | yes | File browser All/Changes/History tabs | file/diff/history survives; FakeClaude vehicle |
| test_file_browser_uncommitted.py | REWRITE | yes | Uncommitted changes panel | diff/git survives; FakeClaude vehicle |
| test_file_chip_tilde_path_opens_home_file.py | DELETE | yes | @-mention file chip (~/) click | @-mention chip removed |
| test_file_open_diff_modes.py | REWRITE | yes | File-open diff modes | file/diff viewer survives; FakeClaude vehicle |
| test_history_panel.py | REWRITE | yes | Commit history panel | history/git survives; FakeClaude vehicle |
| test_history_panel_diffs.py | REWRITE | yes | History panel commit-diff tabs | history/diff survives; FakeClaude vehicle |
| test_home_page.py | KEEP | no | Home page (recent workspaces, search, nav) | surviving nav UI; subject is the home page |
| test_home_page_tab.py | KEEP | no | Home page pseudo-tab lifecycle | surviving tab/nav UI |
| test_image_lightbox_navigation.py | DELETE | no | Image attachment lightbox in chat | chat image input removed |
| test_image_thumbnail_strip.py | DELETE | no | Inline image thumbnail strip | chat image input + alpha render removed |
| test_image_upload.py | DELETE | no | Image upload/attachment in chat | chat file/image input removed |
| test_inline_media_display.py | DELETE | yes | Inline img/video rendering in rich chat | alpha media rendering removed |
| test_interrupt_and_continue.py | REWRITE | yes | Interrupt/stop a running agent turn | interrupting survives for terminal agents; FakeClaude vehicle |
| test_keybindings.py | REWRITE | no | Keybindings settings + help dialog | keybindings/panel-toggle survive; registry covers removed actions, re-express |
| test_linear_plugin_runtime.py | DELETE | no | Bundled Linear frontend plugin + plugins settings | frontend plugins removed |
| test_mark_unread.py | REWRITE | yes | mark-unread on agent tabs | tab read/unread + multi-agent survive; FakeClaude vehicle |
| test_markdown_gfm.py | DELETE | yes | rich markdown render (experimental flag) | rich-markdown toggle + experimental flag removed |
| test_markdown_render_toggle.py | DELETE | yes | rich-markdown render toggle | experimental rich-markdown removed |
| test_mention_picker_completion.py | DELETE | no | +/@ entity-mention picker | @-mentions + ChatInput picker removed |
| test_migration.py | KEEP | no | data-dir bootstrap when .format_version missing | infra/bootstrap; survives |
| test_minimum_interface_conformance.py | REWRITE | yes | harness turn-boundary conformance | conformance survives; pi half removed, re-express against terminal agent |
| test_missing_claude_binary.py | REWRITE | no | friendly error when claude binary disappears | RESOLVED (reclassified in review): behavior survives, but the test sets a broken path via `DependencyPaths(claude=…)` + `dependency_stubs` + `_resolve_claude_binary_path()` — all removed under PATH-only resolution. Re-express by making `shutil.which("claude")` fail (manipulate `PATH`), not via the deleted config field |
| test_model_capability_gating.py | DELETE | yes | model selector + fast-mode | removed ChatInput controls |
| test_multi_agent_workspace.py | REWRITE | yes | multiple agents per workspace | multi-agent + tab lifecycle survive; FakeClaude vehicle |
| test_multi_repo.py | REWRITE | yes | multi-repo workspace creation & switching | project/repo + workspace lifecycle survive |
| test_notes_panel.py | DELETE | no | Notes panel (tiptap editor panel) | non-surviving rich panel |
| test_onboarding.py | REWRITE | no | onboarding flow (email, install, deps, auth) | RESOLVED (split): delete the email/install/deps/auth steps; keep+rewrite the PATH-check + repo-add steps |
| test_open_in_viewer.py | REWRITE | yes | open file in diff viewer from chat | diff/file viewer survives; entry is alpha file chip, re-express via file-browser path |
| test_optimistic_close.py | REWRITE | yes | optimistic close of workspace tabs | tab lifecycle survives; FakeClaude vehicle |
| test_optimistic_deletion.py | REWRITE | yes | optimistic agent/workspace deletion + rollback | deletion + tab state survive; FakeClaude vehicle |
| test_panel_zones.py | DELETE | no | panel zone drag/reassignment (dnd) | dnd zone reassignment removed |
| test_panels_settings.py | DELETE | no | Settings→Panels drag-to-zone config | dnd panel config removed (show/hide survives but is not this file's subject) |
| test_path_autocomplete_keyboard.py | KEEP | no | add-repo path autocomplete keyboard | surviving repo-add UI |
| test_path_tilde_display.py | KEEP | no | add-repo path autocomplete tilde display | surviving repo-add UI |
| test_pi_backchannel.py | DELETE | no | Pi agent AUQ/plan backchannel | Pi + AUQ/plan removed |
| test_pi_background_tasks.py | DELETE | no | Pi agent background tasks | Pi removed |
| test_pi_basic.py | DELETE | no | Pi agent basic workspace + /clear | Pi + /clear removed |
| test_pi_capability_gating.py | DELETE | yes | Pi/Claude capability gating | Pi + gated ChatInput affordances removed |
| test_pi_interrupt.py | DELETE | no | Pi agent interrupt-and-continue | Pi removed |
| test_pi_managed_install.py | DELETE | no | Pi managed-install / deps | Pi + managed-tools removed |
| test_pi_session_resume.py | DELETE | no | Pi agent session resume | Pi removed |
| test_pi_sub_agents.py | DELETE | no | Pi agent sub-agents | Pi + sub-agent pill removed |
| test_pi_turn_error.py | DELETE | no | Pi agent turn-error rendering | Pi removed |
| test_picker_dismissal.py | DELETE | no | @/`/`/+ ChatInput mention-picker dismissal | ChatInput pickers removed |
| test_picker_no_reopen_after_dismissal.py | DELETE | no | ChatInput mention-picker re-open suppression | ChatInput pickers removed |
| test_plan_mode.py | DELETE | yes | plan mode: Enter/Exit, AUQ, plan-file viewer | plan-mode + AUQ/exit-plan blocks removed |
| test_plugin_loader.py | DELETE | no | frontend plugins system (loader) | frontend plugins removed |
| test_plugins_settings_visibility.py | DELETE | no | experimental frontend-plugins flag + section | frontend plugins + experimental removed |
| test_plus_does_not_trigger_bullet_list.py | DELETE | no | `+` mention vs TipTap bullet rule | ChatInput `+` mention removed |
| test_pr_button_errors.py | REWRITE | no | PR-status tracking / PR button errors | PR tracking survives; re-express against terminal agent |
| test_pr_management.py | REWRITE | yes | PR management: target-branch, Settings→Git | PR/target-branch tracking survives; FakeClaude vehicle |
| test_project_env_vars.py | REWRITE | yes | project .env vars in agent + terminal + settings | env-var loading/terminals/settings survive; agent-side assertions via FakeClaude, re-express |
| test_project_path_monitoring.py | REWRITE | no | project-path-moved warning banner | project-lifecycle UI survives; already skipped, rewrite to API-based create |
| test_pseudo_skills.py | DELETE | yes | /clear, /copy pseudo-skills + autocomplete | pseudo-skills + chat-input autocomplete removed |
| test_queued_messages.py | DELETE | yes | queued-message bar, edit/undo, always-interrupt, AUQ | queued-message + ChatInput + AUQ removed |
| test_read_unread_status.py | REWRITE | yes | read/unread dots on agent & workspace tabs | multi-agent + tab dot-status survive; FakeClaude vehicle |
| test_registered_terminal_agent.py | KEEP | no | registered terminal agents launch/resume from TOML | already terminal-based; real sculpt signal CLI |
| test_restart_mru.py | KEEP | no | restart MRU restore of tabs/draft | surviving tab lifecycle; localStorage + URL |
| test_restarts.py | REWRITE | no | tasks/chats persist across backend restart | persistence survives; uses chat panel vehicle, re-express |
| test_review_all_visibility.py | REWRITE | yes | Review All button visibility on diff | diff viewer + experimental gate; re-express via terminal git ops |
| test_sculpt_cli.py | REWRITE | yes | sculpt CLI workspace/agent/repo CRUD | sculpt CLI survives; re-express agent-message parts against terminal agent |
| test_sculpt_ui_open_file.py | REWRITE | yes | sculpt ui open-file → diff/file viewer | sculpt CLI + diff viewer survive; FakeClaude no-op vehicle |
| test_sculpt_ui_webview.py | DELETE | yes | sculpt ui webview-navigate (Browser panel) | targets removed browser panel / custom backend |
| test_settings_integration.py | REWRITE | yes | Settings: env-vars, keybindings, Review All | settings + diff survive; re-express Review-All part |
| test_settings_tab.py | KEEP | no | Settings pseudo-tab open/close/singleton | surviving settings UI + tab bar |
| test_shared_instance_validation.py | KEEP | no | shared-instance test infra | surviving harness smoke |
| test_side_toggle.py | KEEP | no | panel show/hide toggles | surviving panel show/hide (not drag) |
| test_skill_autocomplete.py | DELETE | yes | slash/@-mention skill autocomplete popover | ChatInput autocomplete + entity mentions removed |
| test_skill_without_frontmatter.py | DELETE | yes | SkillsPanel chip for frontmatter-less skill | SkillsPanel (rich-chat skills UI) removed |
| test_skills_panel.py | DELETE | yes | SkillsPanel list/click-insert/search | SkillsPanel + insert into rich editor removed |
| test_slash_command_enter_accepts_suggestion.py | DELETE | yes | Enter accepts slash-command suggestion | ChatInput slash popover removed |
| test_slash_command_errors.py | DELETE | yes | slash-command error/warning messages | rich-chat warning rendering removed |
| test_smooth_streaming_viewport_sentinel.py | DELETE | yes | smooth-streaming viewport sentinel | smooth-streaming + AlphaChatView removed |
| test_startup_errors.py | KEEP | no | fatal startup error → backend error page | surviving app-lifecycle/error-boundary |
| test_status_pill.py | DELETE | yes | StatusPill in AlphaChatView | alpha status pill + AUQ removed |
| test_status_pill_background_wait.py | DELETE | yes | StatusPill waiting-for-background | alpha status pill + rich background subagent removed |
| test_status_pill_plan_mode_stop.py | DELETE | yes | StatusPill stop after plan approval | status pill + exit-plan/AUQ removed |
| test_status_pill_tasks_widget.py | DELETE | yes | agent-tasks popover (TaskCreate/Update DAG) | status pill + rich tool pills + sculptor MCP Task tools removed |
| test_stop_kills_foreground_processes.py | REWRITE | yes | Stop kills orphaned foreground subprocess (SCU-211) | agent stop/process-group survives; re-express against terminal stop |
| test_stop_kills_sigterm_immune_subprocess.py | REWRITE | yes | Stop kills SIGTERM-immune subprocess (SCU-1340) | agent stop/process-group survives; re-express against terminal stop |
| test_stopped_turn_footer.py | DELETE | yes | turn footer (duration/tokens/Stopped) | AlphaChatView turn-footer removed |
| test_tab_context_menus.py | KEEP | no | terminal tab context menu "Close Others" | surviving terminal panel + tabs |
| test_tanstack_devtools_panel.py | KEEP | no | in-app TanStack Query devtools panel | surviving app chrome |
| test_target_branch.py | REWRITE | yes | target-branch scope picker + diff content | diff viewer + branch scope survive; re-express via terminal git ops |
| test_target_branch_local_only.py | REWRITE | yes | Changes tab on local-only worktree | worktree + diff viewer survive; re-express via terminal agent |
| test_task_page_chatting.py | DELETE | yes | multi-turn chat, model selector, drafts, compaction | rich chat conversation removed |
| test_task_page_plan_tab.py | DELETE | yes | agent-tasks popover plan rows | status pill agent-tasks + sculptor MCP Task tools removed |
| test_task_page_tool_results.py | DELETE | yes | rich chat tool-pill rendering | alpha tool pills / bash blocks removed |
| test_telemetry_opt_out.py | DELETE | no | telemetry opt-out + onboarding email/install | telemetry + onboarding email/install removed |
| test_terminal.py | KEEP | no | terminal panel (PTY, tabs, keybindings) | surviving terminal panel |
| test_terminal_agent_automated_prompts.py | REWRITE | yes | automated prompts to registered terminal agent | registered terminal + commit survive; FakeClaude vehicle for change-count/chat-fallback |
| test_terminal_agent_basic.py | KEEP | no | plain terminal agent lifecycle | surviving terminal-agent subject |
| test_terminal_agent_external_rename.py | KEEP | no | terminal-agent live rename via sculpt/API | surviving terminal-agent + sculpt CLI |
| test_terminal_agent_signals.py | KEEP | no | terminal-agent signals drive tab dot | surviving terminal-agent + sculpt signal |
| test_terminal_close_kills_shell.py | KEEP | no | terminal-close kills PTY | surviving terminal panel |
| test_terminal_tab_enhancements.py | KEEP | no | terminal tab rename/context-menu/layout | surviving terminal panel UI |
| test_theme_builder.py | DELETE | no | theme builder settings | theme builder removed |
| test_turn_footer_interactions.py | DELETE | yes | alpha chat turn-footer (token popover) | alpha turn-footer removed |
| test_turn_summary.py | DELETE | yes | alpha chat turn-footer file count | alpha turn-footer removed |
| test_turn_summary_worktree.py | DELETE | yes | backend changed_files in worktree (DiffTracker) | RESOLVED: observable surface is the removed turn-footer; DiffTracker/changed_files is already covered by diff_tracker_test.py (worktree regression), test_workspace_banner, test_file_browser |
| test_websocket_session_token_auth.py | KEEP | no | stream WebSocket session-token auth | surviving auth/sculpt-CLI subject |
| test_workspace_banner.py | REWRITE | yes | workspace banner diff summary / branch | banner + diff stats survive; FakeClaude write_file |
| test_workspace_banner_overflow.py | REWRITE | yes | workspace banner progressive-collapse | banner survives; FakeClaude vehicle |
| test_workspace_close_vs_delete.py | REWRITE | yes | workspace tab close-vs-delete lifecycle | lifecycle survives; FakeClaude vehicle |
| test_workspace_deletion_cleanup.py | REWRITE | yes | workspace delete cascade (PTY + worktree teardown) | teardown survives; FakeClaude sleep / chat vehicle |
| test_workspace_diagnostics_context_menu.py | REWRITE | yes | workspace tab context-menu copy actions | tab menu survives; FakeClaude only spawns workspace |
| test_workspace_peek.py | REWRITE | yes | workspace peek popover (status/diff) | peek survives but derives from chat-agent states; re-express via terminal signals |
| test_workspace_scoped_changes.py | REWRITE | yes | workspace-scoped Changes across agents | Changes + multi-agent survive; FakeClaude write_file, drop Review-All gate |
| test_workspace_setup_command.py | KEEP | no | workspace setup command + SetupStatusCard | surviving settings/setup subject |
| test_workspace_setup_status.py | KEEP | no | pinned setup status card | surviving setup-status subject |
| test_workspace_setup_system_reminder.py | DELETE | no | setup reminder injected into first SDK message | RESOLVED: injection is SDK-only (process_manager `user_instructions`); terminal agents have no first-message injection. Behavior is intentionally dropped for terminal agents (setup command still runs + status card shows) |
| test_workspace_tab_context_menu_icons.py | REWRITE | yes | workspace tab rename via context menu | tab menu survives; FakeClaude only spawns workspace |
| test_workspace_tab_enhancements.py | REWRITE | yes | workspace tab keyboard/close/delete | tab + keyboard survive; FakeClaude vehicle |
| test_worktree_as_user_repo.py | KEEP | no | register worktree as user repo | worktree/repo-registration survives |
| test_worktree_create_happy_path.py | KEEP | no | worktree workspace creation | surviving worktree creation |
| test_worktree_deletion_policies.py | KEEP | no | worktree branch-deletion policy | surviving worktree lifecycle |
| test_worktree_edge_cases.py | REWRITE | no | worktree edge cases (mode selector, setup, missing repo) | RESOLVED (trim): drop the CLONE/in-place mode-selector case; keep the worktree setup + missing-repo cases |
| test_zen_mode.py | KEEP | no | zen/focus mode + panel toggle | surviving panel show/hide + appearance |

---

## §2. regression (`sculptor/tests/integration/regression/`)

| file | verdict | fakeclaude | subject | rationale |
|---|---|---|---|---|
| test_regression_action_skill_popover.py | DELETE | no | ActionDialog rich TipTap editor + skill mentions | ChatInput skill mentions / rich editor removed |
| test_regression_add_repo_cmd_enter_stays_on_page.py | KEEP | no | Add Workspace / Add Repo dialog | surviving worktree-creation/repo surface |
| test_regression_agent_count_diagnostics.py | REWRITE | yes | agent count / workspace-agent lifecycle vs settings | multi-agent + settings count + health survive; FakeClaude AUQ vehicle |
| test_regression_angle_brackets_in_editor.py | DELETE | yes | TipTap markdown of user message in rich chat | rich-chat render removed |
| test_regression_auq_failure_stuck.py | DELETE | yes | ask-user-question block + chat dispatch | AUQ removed |
| test_regression_auto_compact_indicator.py | DELETE | yes | auto-compact pill / context summary | chat-alpha render removed |
| test_regression_compaction_message_position.py | DELETE | yes | compaction message ordering in rich chat | alpha message ordering removed |
| test_regression_copy_branch_name.py | DELETE | no | copy branch name in clone-mode banner | clone workspaces removed |
| test_regression_copy_file_path.py | DELETE | yes | copy file path in clone-mode via alpha chip | clone workspaces + alpha file chip removed |
| test_regression_copy_user_message_html.py | DELETE | yes | copy user message with @-mention node | chat @-mentions / rich copy removed |
| test_regression_default_model_opus.py | DELETE | no | default model resolution / chat model selector | model selector removed |
| test_regression_invalid_slash_command.py | DELETE | yes | invalid slash command warning block | slash-command + chat warning removed |
| test_regression_large_diff_crash.py | REWRITE | yes | single-file diff viewer (uncommitted scope) | diff viewer survives; FakeClaude authors the file |
| test_regression_model_selection.py | DELETE | yes | chat-panel model selector inheritance | model selector removed |
| test_regression_mru_default_model.py | DELETE | yes | MRU model default / model selector | model selector removed |
| test_regression_no_error_block_on_restart_during_auq.py | DELETE | yes | suppress error block for AUQ restart | AUQ + chat ErrorBlock removed |
| test_regression_prompt_placeholder.py | DELETE | yes | ChatInput TipTap placeholder + slash | ChatInput / slash popover removed |
| test_regression_queued_messages_after_restart.py | REWRITE | yes | queued-message + interrupted-turn restart recovery | restart/lifecycle survives; re-express against terminal agent |
| test_regression_replay_on_restart.py | REWRITE | yes | no prompt-replay after restart (run-loop) | lifecycle/restart survives; re-express against terminal agent |
| test_regression_review_all_shiki_error.py | DELETE | yes | Review All combined diff (experimental) | experimental Review-All removed |
| test_regression_review_all_shiki_error_target_branch.py | DELETE | yes | Review All combined diff, target-branch (experimental) | experimental Review-All removed |
| test_regression_settings_delete_repo_stays_on_page.py | KEEP | no | settings repositories add/delete navigation | surviving settings + repo mgmt |
| test_regression_setup_command_backfill.py | REWRITE | no | workspace setup-command (no retroactive run) | setup-command survives; real-agent prompt vehicle, re-express |
| test_regression_setup_command_rerun.py | REWRITE | no | workspace setup-command rerun/persistence | setup-command survives; plain prompt vehicle |
| test_regression_streaming_warning.py | DELETE | no | spurious chat warning block in streaming | rich-chat warning-block / streaming processor removed |
| test_regression_target_branch_merge_base_oldlines.py | REWRITE | yes | vs-target-branch single-file diff (merge-base) | diff viewer survives; FakeClaude authors git history |
| test_regression_task_list_after_restart.py | REWRITE | yes | agent task-list popover persistence | task-list/restart survives; re-express against terminal agent |
| test_regression_task_list_after_sync_dir_wiped.py | REWRITE | yes | task-list cache backfill after sync-dir wipe | task-list survives; FakeClaude TaskCreate vehicle |
| test_regression_task_list_claude_config_dir.py | REWRITE | yes | task-list honoring CLAUDE_CONFIG_DIR | task-list survives; re-express against terminal agent |
| test_regression_task_status_after_restart.py | REWRITE | yes | task status not ERROR after restart mid-turn | lifecycle + restart recovery survives; FakeClaude sleep vehicle |
| test_regression_terminal_light_mode_contrast.py | REWRITE | no | terminal panel light-mode ANSI palette | terminal + appearance survive; plain prompt vehicle |
| test_regression_terminal_link.py | REWRITE | no | terminal panel link opening (Electron) | terminal panel survives; plain prompt vehicle |
| test_regression_terminal_theme_toggle.py | REWRITE | no | terminal theme updates on appearance toggle | terminal + light/dark survive; plain prompt vehicle |
| test_regression_workspace_mode_persistence.py | DELETE | no | in-place workspace mode selector persistence | in-place + experimental removed (also xfail) |
| test_regression_workspace_peek_stuck_on_close.py | REWRITE | yes | workspace tab peek popover dismissal | tabs/lifecycle survive; FakeClaude only spawns workspace |

---

## §3. real_claude (`sculptor/tests/integration/real_claude/`)

Tests run against a real `claude` binary. All but the terminal-agent test
drive the rich Claude SDK agent + sculptor MCP tools → DELETE. The
terminal-agent test targets the surviving bundled `claude-code`
registration → KEEP.

| file | verdict | subject | rationale |
|---|---|---|---|
| __init__.py | KEEP | package marker | needed by the surviving terminal test's import path |
| conftest.py | KEEP | real-OAuth + real-binary harness | the surviving terminal test still needs the real binary; no rich-chat dependency |
| helpers.py | DELETE | alpha-chat drive helpers | entirely alpha-chat oriented; move only the `real_claude` marker to conftest/shim |
| test_ask_user_question.py | DELETE | AskUserQuestion MCP tool + AUQ block | removed surfaces |
| test_background_tasks.py | DELETE | SDK background-task protocol + alpha | removed |
| test_basic_message_flow.py | DELETE | rich SDK stdin message/resume + alpha | removed |
| test_claude_code_terminal_agent.py | KEEP | bundled claude-code registered terminal agent | surviving: registration loading, terminal panel, hooks |
| test_clear_context.py | DELETE | /clear pseudo-skill | removed |
| test_edge_cases.py | DELETE | SDK stdin edge cases + AUQ/plan | removed |
| test_interrupts.py | DELETE | SDK interrupt protocol + alpha + AUQ | removed |
| test_monitor_tool.py | DELETE | Monitor MCP tool | sculptor MCP server removed |
| test_parallel_slow_bash_hang.py | DELETE | SDK parallel/background bash + alpha | removed |
| test_permission_prompt.py | DELETE | SDK permission-prompt protocol + alpha pills | removed |
| test_plan_mode.py | DELETE | plan mode + ExitPlanMode/AUQ | removed |
| test_schedule_wakeup.py | DELETE | ScheduleWakeup MCP tool | sculptor MCP server removed |
| test_stop_kills_foreground_subprocess.py | DELETE | Stop kills SDK Bash subprocess (process-group) | RESOLVED: redundant — process-group teardown is covered by the two frontend test_stop_kills_* rewrites against terminal agents; no rich-agent Stop gesture in terminal world |
| test_streaming.py | DELETE | rich SDK streaming into alpha chat | removed |
| test_tool_calls.py | DELETE | SDK Write/Bash/Read tools + alpha pills | removed |

---

## §4. real_pi (`sculptor/tests/integration/real_pi/`) — entire directory DELETE

The whole Pi integration is removed (REQ-AGENT-4), so the entire suite goes,
support files included. No per-file ambiguity.

`__init__.py`, `conftest.py`, `helpers.py`, `test_ask_user_question.py`,
`test_background_tasks.py`, `test_basic_message_flow.py`,
`test_clear_context.py`, `test_compaction.py`, `test_file_attachments.py`,
`test_file_edit.py`, `test_image_input.py`, `test_interrupts.py`,
`test_plan_mode.py`, `test_session_resume.py`, `test_skills.py`,
`test_sub_agents.py`, `test_tool_calls.py` — **all DELETE.**

---

## §5. Fakes & harness to remove (REQ-TEST-3) and create (REQ-TEST-4)

**Remove once no test depends on them:**
- `sculptor/sculptor/agents/testing/fake_claude.py`
- `sculptor/sculptor/agents/testing/fake_claude_commands.py`
- `sculptor/sculptor/agents/testing/fake_claude_jsonl.py`
- `sculptor/sculptor/testing/fake_claude_pause.py`
- `sculptor/sculptor/testing/fake_pi.py`
- `sculptor/sculptor/testing/fake_pi_test.py`
- the whole `real_pi/` directory; the rich-chat parts of `real_claude/`

**Create (REQ-TEST-4) — the rewrite target for every REWRITE row:** a
test-only registered terminal agent (`.toml` whose `launch_command` runs a
scripted, controllable program) carrying only the side-effecting command DSL
(write/edit/bash/multi_step/wait) plus the terminal lifecycle signals the
real registration emits. Deliberately narrower than `FakeClaude` — no JSONL
streaming, tool pills, MCP control, or AUQ blocks (those surfaces are gone).

**Shared-fixture edits (not test subjects, but must change):**
- `frontend/conftest.py` — drop the Pi harness fixture and the auto-update
  mock it re-exports.
- `regression/conftest.py` — re-exports playwright fixtures; survives.

---

## §6. Ambiguous — RESOLVED

The six originally-flagged rows were settled with the user (and grounded in
code, not guessed); a seventh (row 7) was caught and reclassified during
review. The verdicts are reflected in the tables above.

- **frontend/test_custom_actions.py** → **REWRITE.** The actions panel
  survives untouched: `chatActionsAtom` is agent-agnostic and
  `useTerminalChatActions` already routes actions to the PTY via
  `postAgentTerminalInput`. Only the draft-into-chat-input subtest needs
  re-expression against a terminal agent.
- **frontend/test_onboarding.py** → **REWRITE (split).** Delete the
  email/install/deps/claude-auth steps; keep+rewrite the PATH-check +
  repo-add steps.
- **frontend/test_turn_summary_worktree.py** → **DELETE.** Its observable
  surface is the removed turn-footer; the `DiffTracker`/`changed_files`
  backend is already covered by `diff_tracker_test.py` (incl. a worktree
  regression), `test_workspace_banner`, and `test_file_browser`.
- **frontend/test_workspace_setup_system_reminder.py** → **DELETE.** The
  reminder injection is SDK-only (`process_manager` `user_instructions`);
  terminal agents have no first-message injection. **Product decision: the
  auto-injected setup reminder is intentionally dropped for terminal
  agents** — the setup command still runs and its status card still shows.
- **frontend/test_worktree_edge_cases.py** → **REWRITE (trim).** Drop the
  CLONE/in-place mode-selector case; keep the worktree setup + missing-repo
  cases.
- **real_claude/test_stop_kills_foreground_subprocess.py** → **DELETE.**
  Redundant — process-group teardown is covered by the two frontend
  `test_stop_kills_*` rewrites against terminal agents.
- **(row 7) frontend/test_missing_claude_binary.py** → **REWRITE** (was
  KEEP). The friendly "claude binary missing" behavior survives, but the
  test drives it through removed machinery: it imports `DependencyPaths`,
  sets `dependency_paths={"claude": <stub>}`, and relies on
  `dependency_stubs.create_claude_stub_dir` + `_resolve_claude_binary_path()`
  — all gone under PATH-only resolution. Re-express by making
  `shutil.which("claude")` fail (e.g. an empty `PATH`), asserting the same
  friendly error. KEEP "no change needed" was incorrect because the test's
  *vehicle* (not just subject) sits on deleted surface.
