# Sculptor — Scenario Test Coverage Report (integration tests only)

This report assesses, for every scenario in [`scenarios.md`](./scenarios.md), whether the
existing **integration** test suite adequately covers it, and names the specific integration
tests to add where coverage is missing or partial.

## Scope of this report

**Only integration tests count as coverage here**, so the report reflects end-to-end coverage that
drives the real UI and asserts user-visible outcomes.

Integration tests considered:

- `sculptor/tests/integration/frontend/test_*.py` — Playwright-driven UI tests backed by the
  fake registered terminal agent (`sculptor/sculptor/testing/fake_terminal_agent*.py`), the
  deterministic harness that drives agent behavior for the bulk of user-visible coverage.
- `sculptor/tests/integration/regression/test_*.py` — regression tests.
- `sculptor/tests/integration/real_claude/` — model-backed end-to-end flows.

## Status definitions

- **Complete** — an integration test performs the user action *and* asserts the user-visible
  outcome the scenario describes.
- **Partial** — an integration test exists but misses part of the Given/When/Then (only the happy
  path, only one state of several, drives the action but asserts nothing visible, etc.).
- **Missing** — no integration test meaningfully covers it.

> Note on SET-* : several settings scenarios are umbrella entries covering multiple controls in one
> section; they are Partial when only some controls in that section have an integration test.

## Executive summary

| Area | Complete | Partial | Missing | Total |
|------|---------:|--------:|--------:|------:|
| SHELL | 17 | 10 | 16 | 43 |
| ROUTE | 1 | 1 | 3 | 5 |
| HELP | 0 | 2 | 1 | 3 |
| HOME | 2 | 4 | 14 | 20 |
| ADDWS | 7 | 11 | 3 | 21 |
| ADDREPO | 1 | 5 | 2 | 8 |
| ONB | 1 | 7 | 3 | 11 |
| WS | 13 | 11 | 16 | 40 |
| PANEL | 15 | 17 | 14 | 46 |
| CMDP | 4 | 8 | 18 | 30 |
| SET | 4 | 9 | 7 | 20 |
| DEV | 0 | 1 | 3 | 4 |
| SKILL | 0 | 0 | 3 | 3 |
| ACT | 2 | 3 | 1 | 6 |
| **Total** | **67** | **89** | **104** | **260** |

**Under the integration-only standard, 26% of scenarios are completely covered, 34% partially, and
40% not at all.** (Counts are derived directly from the two sections below.)

The per-scenario detail is split into two sections: **Coverage gaps — Partial & Missing** (every
scenario needing work, with the test to add) and **Complete coverage** (every scenario already fully
covered, with the test that covers it). Each scenario appears in exactly one.

## Coverage gaps — Partial & Missing

Every scenario that is **not** Complete, grouped by area. **Missing** = no integration coverage (the *to add* column describes a new test to write); **Partial** = some integration coverage exists (the *Existing* column shows what, the *to add* column the assertion still needed).

### SHELL / ROUTE / HELP

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| SHELL-002 | Partial | test_home_page_tab.py::test_home_page_opens_as_tab (uses navigate helper, not the top-bar Home button) | Click the top-bar Home button (and one pressing the Home keybinding); assert a Home tab appears/re-activates with the home page shown. |
| SHELL-004 | Partial | test_home_page_tab.py::test_clicking_workspace_replaces_home_tab (clicks a workspace row, not a non-active tab) | With 2+ open tabs, click a non-active tab and assert it becomes active and its content renders. |
| SHELL-005 | Missing | — | With multiple tabs, press Cmd+] and assert the next tab activates, including wrap from last to first. |
| SHELL-006 | Missing | — | Press Cmd+[ and assert the previous tab activates, including wrap from first to last. |
| SHELL-008 | Missing | — | Middle-click a non-active tab and assert it closes while the active tab is unchanged. |
| SHELL-010 | Missing | — | Drag-reorder one tab past another; assert the drop indicator, the order change on release, and an unchanged active tab. |
| SHELL-011 | Missing | — | Open more tabs than fit; dispatch a wheel event over the tab bar; assert horizontal scroll position changes. |
| SHELL-012 | Missing | — | With overflowing tabs, activate an off-screen tab (keyboard cycle); assert it scrolls into the viewport. |
| SHELL-013 | Missing | — | Long-titled tab at constrained width; assert the label is ellipsis-truncated. |
| SHELL-014 | Partial | test_terminal_agent_signals.py::test_terminal_agent_signals_drive_tab_status_dot | Assert the visual variants: pulsing running vs solid waiting/ready, red error dot, two-dot mixed-status case. |
| SHELL-015 | Partial | test_workspace_tab_context_menu_icons.py::test_workspace_context_menu_rename; test_tab_context_menus.py::test_terminal_tab_context_menu_close_others | Right-click a workspace tab and assert the full menu set (Close, Close others, Close all, Rename, Delete, git actions). |
| SHELL-018 | Partial | test_tab_context_menus.py::test_terminal_tab_context_menu_close_others (terminal tabs only) | On workspace tabs, exercise "Close others" and "Close all"; assert all-others/all close and "Close all" lands on the Add Workspace page. |
| SHELL-019 | Partial | test_restarts.py::test_tasks_persist_on_restart; test_restart_mru.py::test_restart_restores_active_workspace_and_agent | Open 3+ tabs in a specific order with a known active one, restart, assert same tabs/order/active tab. |
| SHELL-026 | Partial | test_keybindings.py::test_help_dialog_reflects_customized_bindings (opens via Cmd+/, not the Help button) | Click the top-bar Help (?) button and assert the keyboard-shortcuts dialog opens. |
| SHELL-027 | Missing | — | Hover a top-bar button and assert a tooltip showing the button name plus its keyboard shortcut. |
| SHELL-033 | Partial | test_regression_terminal_theme_toggle.py::test_terminal_theme_updates_on_toggle (presses Cmd+Shift+D; asserts xterm colors, not the app-level theme) | Press Cmd+Shift+D and assert the app-level light/dark theme flips without a reload. |
| SHELL-034 | Missing | — | Assert the version number is visible bottom-right on a non-workspace page, and hidden in zen mode. |
| SHELL-035 | Missing | — | Click the version number (or bug icon); assert the popover opens showing version, git SHA, and the diagnostics fields: platform, uptime, active agents, disk, paths, install info. |
| SHELL-041 | Partial | test_tanstack_devtools_panel.py::test_tanstack_devtools_panel_mounts_with_content (TanStack Devtools only) | Toggle "React Grab" and "TanStack event log" from the version popover and assert each dev tool appears/disappears. |
| SHELL-042 | Missing | — | Make the backend unresponsive and assert the yellow bottom banner reads "Backend not responding. Please try restarting the app." |
| SHELL-043 | Missing | — | Inject a backend health warning and assert a yellow warning banner with the message (and link if present). |
| SHELL-044 | Partial | test_project_path_monitoring.py::test_project_path_monitoring (currently skipped) | Un-skip/rewrite to assert the "Project folder not found: {name}." banner with a "Learn more" link that opens the dialog. |
| SHELL-045 | Missing | — | Assert the backend loading splash shows the Sculptor logo, "Loading" message, and progress bar until ready. |
| SHELL-046 | Missing | — | Drive the backend into the shutting-down state; assert a "Shutting down…" message with a progress bar, and a recovery message once stalled past ~30s. |
| SHELL-047 | Missing | — | In dev/from-source mode, assert the bottom-left dev-mode indicator renders and hovering shows a "Running from source" tooltip with the workspace id. |
| SHELL-048 | Missing | — | Press Cmd+= / Cmd+- / Cmd+0; assert the zoom scales up/down/resets to 100% and persists across restart. |
| ROUTE-002 | Partial | test_restart_mru.py::test_restart_with_no_mru_lands_on_new; test_add_workspace_page.py::test_workspace_form_draft_persists_after_navigation | Navigate to bare `/ws/new` and assert the URL is rewritten to `/ws/new/{draftId}` with the Add Workspace form displayed. |
| ROUTE-003 | Missing | — | Navigate to an unknown route; assert the Not-Found page shows the logo, "The page you are looking for does not exist.", and a home link. |
| ROUTE-004 | Missing | — | Force a loader/component to throw; assert the error page renders a generic message plus error details in a scrollable box. |
| ROUTE-005 | Missing | — | On the route error page, click "Copy Error to Clipboard"; assert the clipboard contains the error text. |
| HELP-001 | Partial | test_keybindings.py::test_help_dialog_reflects_customized_bindings; ::test_help_dialog_hides_unbound | Add opening via the Help button (see SHELL-026) and assert the modal title is "Help" with shortcuts grouped by category. |
| HELP-002 | Missing | — | Open the help dialog and assert a shortcut renders an OS-formatted key badge (e.g. `Cmd+K` on macOS, `Ctrl+K` elsewhere). |
| HELP-003 | Partial | test_keybindings.py::test_help_dialog_reflects_customized_bindings (closes via dialog.close()/Escape) | Assert both the X button and the Escape key close the help dialog. |

### HOME / ADDWS / ADDREPO

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| HOME-001 | Missing | — | Delay the workspace-list fetch and assert the list-area spinner is visible. |
| HOME-003 | Partial | test_home_page.py::test_workspace_search_filters_list (uses get_search_input) | Assert placeholder "Search workspaces…" and that the input is focused on load. |
| HOME-004 | Partial | test_home_page.py::test_workspace_search_filters_list (filters by name only) | Extend to assert filtering by branch and project, plus case-insensitivity. |
| HOME-005 | Missing | — | Type a non-matching query; assert centered `No results for "{query}"`. |
| HOME-006 | Missing | — | Fill search, press Escape; assert query cleared, full list back, focus returns to the search input. |
| HOME-007 | Missing | — | Create 3+ workspaces with distinct activity; assert most-recent-first row order. |
| HOME-008 | Missing | — | Create >25 workspaces; assert 25 rows + "Show more (N remaining)"; click reveals next 25. |
| HOME-009 | Missing | — | After "Show more", type a query; assert visible count resets to first 25 filtered. |
| HOME-010 | Partial | test_home_page.py::test_workspace_row_shows_current_branch_not_source_branch; test_backend_pr_polling.py::test_home_page_shows_pr_badge | Add row assertions for status dot, name, project name on hover, relative last-activity time, hover-revealed delete button. |
| HOME-011 | Missing | — | Hover/focus a row; assert background change and project name + delete button become visible. |
| HOME-012 | Missing | — | From the search box, ArrowDown focuses first row (scrolled into view); ArrowUp from first row returns to search box. |
| HOME-014 | Missing | — | Cmd/Ctrl-click a row (and "Open in New Tab" via context menu) opens it in a new tab with Home still visible. |
| HOME-015 | Missing | — | Right-click a row; assert "Open in New Tab" and a red "Delete Workspace" entry. |
| HOME-016 | Missing | — | Hover-click the trash icon (and via context menu) opens the delete-confirmation dialog. |
| HOME-017 | Missing | — | Assert "Delete workspace?" title, warning naming the workspace, Cancel, and a red default-focused Delete button. |
| HOME-018 | Missing | — | Open dialog, click Cancel / press Escape; assert dialog closes and row remains. |
| HOME-019 | Missing | — | Open dialog from a home row, click Delete; assert dialog closes and row disappears. (test_optimistic_deletion.py covers the tab menu, not the home-row dialog.) |
| HOME-020 | Partial | test_backend_pr_polling.py::test_home_page_shows_pr_badge; ::test_multiple_workspaces_independent_pr_status | Add home-row assertions for "Checking PR…", "Create PR"/"Create MR", merged/closed badge, "Assign PR", error button. |
| ADDWS-001 | Partial | test_add_workspace_page.py (asserts form/submit button) | Delay project fetch; assert the centered spinner before the form. |
| ADDWS-002 | Partial | test_multi_repo.py::test_mru_project_updates_after_creating_workspace | Add the no-MRU case (first project pre-selected). |
| ADDWS-003 | Missing | — | Assert placeholder "Untitled workspace (optional)" and autofocus on initial load. |
| ADDWS-004 | Partial | test_worktree_create_happy_path.py::test_worktree_create_with_empty_workspace_name_random_slug | Assert created workspace named "Untitled workspace" (+ whitespace-only case). |
| ADDWS-006 | Partial | test_multi_repo.py::test_create_new_project_from_add_workspace_page; ::test_adding_duplicate_repo_shows_error | Open selector; assert all projects plus an "Add Repository" entry. |
| ADDWS-007 | Partial | test_multi_repo.py::test_create_workspaces_in_multiple_projects_and_switch | Assert selecting another project reloads the branch selector and clears any branch-name override. |
| ADDWS-008 | Partial | test_multi_repo.py::test_create_new_project_from_add_workspace_page (adds via Settings UI) | Trigger "Add Repository" from the repo-selector dropdown; assert the new project is auto-selected. |
| ADDWS-009 | Missing | — | Assert the branch control shows spinner + "Loading …" and is disabled while branch info loads. |
| ADDWS-010 | Partial | test_worktree_create_happy_path.py::test_worktree_create_with_default_branch_name | Open the branch selector; assert recent branches + "Fetch more branches"; selecting one updates the source branch and clears the override. |
| ADDWS-012 | Partial | test_worktree_create_happy_path.py::test_worktree_create_with_default_branch_name; ::test_worktree_create_with_custom_branch_name | Assert branch-name field across all three modes (Worktree required / Clone optional / In-place absent). |
| ADDWS-014 | Partial | test_worktree_create_happy_path.py::test_worktree_create_with_custom_branch_name | Assert auto-fill stops, a reset link appears, and clicking reset restores the preview. |
| ADDWS-020 | Partial | test_branch_name_collisions.py::test_worktree_mode_collision_blocks_creation | Assert the Create button's explanatory disabled tooltips and the "Cmd/Ctrl+↵" ready tooltip. |
| ADDWS-023 | Partial | test_branch_name_collisions.py::test_worktree_mode_collision_blocks_creation (pre-submit) | Force a submit-time 409; assert toast "Branch '{name}' already exists" and the form stays open. |
| ADDWS-024 | Missing | — | Force creation to fail; assert "Failed to create workspace"/"Failed to create agent" toast with details. |
| ADDREPO-001 | Partial | test_multi_repo.py::test_adding_duplicate_repo_shows_error; test_regression_settings_delete_repo_stays_on_page.py::test_adding_repo_stays_on_settings_page | Assert the path input is focused on open and a Browse button is present on desktop. |
| ADDREPO-002 | Missing | — | Open the dialog, click Cancel / Escape / overlay; assert it closes with no changes. |
| ADDREPO-003 | Partial | test_path_autocomplete_keyboard.py::test_cmd_enter_submits_path | While validation is in progress, attempt to close; assert the dialog stays open. |
| ADDREPO-004 | Partial | test_multi_repo.py::test_create_new_project_from_add_workspace_page (adds via Settings UI) | Focused dialog test: enter a valid path, click "Add Repository"; assert it closes and the new repo is selected in the dropdown. |
| ADDREPO-005 | Missing | — | Type a path, close the dialog, reopen it; assert the path input is empty. |
| ADDREPO-006 | Partial | test_path_autocomplete_keyboard.py::test_autocomplete_shows_submit_hint; test_path_tilde_display.py::test_path_autocomplete_shows_tilde_for_home_directory | Assert the debounce spinner before results and the "No matching directories" message when empty. |
| ADDREPO-008 | Partial | test_path_autocomplete_keyboard.py::test_autocomplete_shows_submit_hint; ::test_cmd_enter_submits_path | Assert all three footer hints verbatim ("Esc: close", "↵: open", "{Meta}↵: add") and the Enter-with-dropdown-closed submit path. |

### ONB / SKILL / ACT

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| ONB-027 | Partial | test_onboarding.py::test_full_onboarding_flow | Assert "Add your first repo" header, the `~/path/to/repo` placeholder, and input autofocus. |
| ONB-028 | Missing | — | On desktop, click "Or browse for a folder", select a folder; assert the path input is populated. |
| ONB-029 | Missing | — | Assert Add disabled + tooltip "Enter a repository path above" when empty; enabled after typing; spinner while validating. |
| ONB-031 | Partial | test_multi_repo.py::test_git_init_dialog_for_non_git_directories (via Add Workspace page, not onboarding) | Add the same flow on the onboarding Add-Repo step; assert "Setting up repository…" and Cancel-returns. |
| ONB-032 | Partial | test_multi_repo.py::test_empty_repo_initial_commit_dialog (via Settings, not onboarding) | Cover the empty-repo prompt on the onboarding Add-Repo step incl. Cancel-returns. |
| ONB-033 | Partial | test_multi_repo.py::test_adding_duplicate_repo_shows_error (via Settings) | Add an onboarding-step test for a nonexistent/inaccessible path → error dialog with a Close button. |
| ONB-034 | Missing | — | Assert the onboarding step indicator renders two dots (PATH check + Add-Repo) with the current step visually distinct, a completed step clickable to return, and an upcoming step not clickable. |
| ONB-035 | Partial | test_onboarding.py::test_full_onboarding_flow (asserts the claude + git status rows) | Assert the "Check your tools" heading, the explanatory line stating Sculptor only checks (never installs) tools, and the green-check "{name} found on your PATH" wording per found tool. |
| ONB-036 | Partial | test_missing_claude_binary.py::test_missing_claude_binary_shows_friendly_error (asserts the missing-claude message and that Continue stays enabled) | Assert the missing tool's red icon and the "{name} not found on your PATH" wording, plus the "How to install {name}" link and the absence of an install button. |
| ONB-037 | Partial | test_onboarding.py::test_full_onboarding_flow (Continue advances to the Add-Repo step); test_missing_claude_binary.py::test_missing_claude_binary_shows_friendly_error (Continue enabled while a tool is missing) | With a required tool missing, click Continue and assert it still advances (non-blocking); also cover the branch that goes straight into the app when a repo already exists. |
| SKILL-001 | Missing | — | Assert a skill chip shows `/skill-name`, exposes an "Open in Sculptor" button for custom/sculptor skills (none for built-in), renders disabled chips as non-interactive, and highlights the keyboard-target chip. |
| SKILL-002 | Missing | — | Hover skill chip A then chip B; assert the popover shows the type badge, skill id, and description, swaps content instantly between chips, and suppresses flapping while scrolling. |
| SKILL-003 | Missing | — | Drive the skills search input ("Search skills…"); assert real-time filtering, arrow-key selection movement, and Escape/clear closing search. |
| ACT-002 | Partial | test_custom_actions.py::test_builtin_chips (built-in group exposes no delete) | Right-click a regular action chip; assert "Queue message" (run-only), "Edit action", "Move to group…" (current disabled), red "Delete action". |
| ACT-003 | Partial | test_custom_actions.py::test_create_action_from_settings; ::test_edit_action_from_settings | Assert Save disabled until Name+Prompt non-empty, and `Cmd+Enter` submits when valid. |
| ACT-005 | Partial | test_custom_actions.py::test_create_group_from_settings; ::test_builtin_chips | Add inline rename (Enter/blur confirm, Escape cancel, no collapse-toggle) and header-click collapse/expand (chevron + count badge). |
| ACT-006 | Missing | — | Drag-simulation: drop indicators before/after, drop into group moves action, drop outside removes; built-ins not draggable. |

### WS

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| WS-022 | Missing | — | While PR status loads, assert spinner with "Checking PR…"/"Checking MR…". |
| WS-023 | Partial | test_pr_button_errors.py::test_github_happy_paths (Create PR visible) | Click Create PR; assert the default PR-creation prompt (incl. target branch) is sent to the agent. |
| WS-024 | Missing | — | Open Create-PR chevron, click "Edit prompt…", edit and Save; assert prompt updated and dialog closes. |
| WS-025 | Partial | test_pr_button_errors.py::test_github_happy_paths ("PR #42") | Assert pipeline and review status dots render on the open-PR button. |
| WS-026 | Missing | — | Click the PR number; assert PR/MR opens in browser (intercept window.open / browser-open RPC). |
| WS-027 | Missing | — | Open chevron popover; assert title/link, checks/pipeline status, approvals with reviewer names, unresolved comments. |
| WS-029 | Partial | test_backend_pr_polling.py::test_closed_not_merged_pr_shows_closed_state | Add the merged-PR case: merge icon + "merged" text; clicking opens browser. |
| WS-030 | Missing | — | Hover pipeline/review dots; assert tooltip text ("Pipeline running/passed/failed/No pipeline", "Approved/Review pending/No reviewers"). |
| WS-031 | Missing | — | PR with different target shows "Assign PR"/"Assign MR"; opening offers "Create PR → {target}" and "switch target to {target}". |
| WS-032 | Partial | test_pr_button_errors.py::test_github_cli_error_variants; ::test_gitlab_cli_error_variants | Assert warning-triangle vs info icon distinction and the remediation-command copy icon turning to a checkmark briefly. |
| WS-033 | Partial | test_target_branch.py::test_switching_to_all_scope_shows_target_branch_diff; test_pr_management.py::test_banner_hides_pr_ui_for_non_gitlab_origin | Click the selector; assert the dropdown lists remote branches; select one; assert target updates. |
| WS-034 | Missing | — | Target differs from PR target → warning color; hover "PR #N targets {branch}"; selecting matching branch updates target. |
| WS-035 | Missing | — | Click repo segment; assert menu (Open folder, Copy path, Copy relative path, Open in installed apps); each action fires; chosen app remembered. |
| WS-038 | Partial | test_workspace_banner_overflow.py::test_collapsed_banner_has_no_inert_overflow_menu | Assert collapse priority order at successive widths: PR button → diff summary → repo segment. |
| WS-039 | Missing | — | Click the banner branch name; assert the branch is copied and a "Copied!" tooltip appears briefly. |
| WS-042 | Partial | test_multi_agent_workspace.py::test_workspaces_have_isolated_agent_tabs (click switches) | Add a next/previous-agent keybinding test asserting the view switches. |
| WS-043 | Missing | — | Hover agent status dot; assert tooltip shows status label + time-since-activity/creation. |
| WS-046 | Partial | test_agent_tab_context_menu.py::test_agent_context_menu_rename | Add double-click-to-rename + Enter; add Escape-cancels-rename. |
| WS-050 | Missing | — | Drag an agent tab to a new position; assert the tab order updates. |
| WS-061 | Partial | test_workspace_peek.py::test_workspace_peek_popover_idle_state; ::test_workspace_peek_popover_waiting_state; ::test_peek_popover_shows_diff_stats | Assert a single popover surfaces status, agent list, PR/MR info, branch, and diff stats together. |
| WS-062 | Partial | test_workspace_peek.py::test_workspace_peek_popover_hover_mechanics; test_regression_workspace_peek_stuck_on_close.py::test_workspace_peek_dismissed_on_middle_click_close | Assert content swaps instantly within grace period and close-after-delay on leaving all tabs. |
| WS-063 | Missing | — | Workspace with >5 agents shows only 5 + "+N more agents" button that reveals the rest. |
| WS-064 | Missing | — | Click peek agent row/header closes popover and opens workspace/agent; click branch copies it with "Copied!". |
| WS-065 | Partial | test_side_toggle.py::test_right_side_toggle_hides_and_shows_panels; test_zen_mode.py::test_focus_mode_hides_panels_but_keeps_chrome | Assert left, bottom, right toggle buttons + focus-mode button all present (and hidden in zen mode). |
| WS-067 | Missing | — | Empty panel toggle is disabled, shows "Panel is empty" tooltip, does nothing on click. |
| WS-068 | Missing | — | Hover a panel toggle; assert tooltip shows the panel name and its keybinding. |
| WS-069 | Missing | — | Drag the diff-panel divider; assert it resizes, dragging past the threshold collapses the diff panel, and the expand control maximizes the diff while collapsing the agent pane (and vice-versa). |

### PANEL

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| PANEL-003 | Missing | — | Click the tree/list toggle; assert the same file list renders nested vs flat. |
| PANEL-005 | Partial | test_file_browser.py::test_refresh_button_reflects_file_operations; ::test_refresh_button_updates_uncommitted_tab_for_external_changes | Assert the refresh icon shows the animated/spinning state while re-fetching. |
| PANEL-009 | Missing | — | Focus tree; Up/Down moves selection, Right/Left expand/collapse, Enter opens the focused file. |
| PANEL-010 | Partial | test_file_browser.py::test_file_tree_shows_status_indicators (A); ::test_moved_file_shows_r_status_without_rename_label (R); test_file_browser_uncommitted.py::test_diff_header_line_stats_reflect_uncommitted_only (M) | Assert D status + strike-through, per-row +/− stats, folder change-count badge, processing-error badge. |
| PANEL-011 | Missing | — | Agent edits a nested file; assert tree auto-scrolls, expands ancestors, applies highlight/focus styling. |
| PANEL-012 | Partial | test_diff_tab_close_others.py::test_diff_tab_close_others | Assert each menu item acts: Open diff view, View file, Copy relative path, Copy absolute path, Open in OS, folder Expand all/Collapse all. |
| PANEL-013 | Partial | test_file_browser.py::test_file_browser_populates_after_workspace_created_without_prompt | Assert the "No files yet" empty state and the animated skeleton/loading rows. |
| PANEL-016 | Partial | test_commit_from_changes_tab.py::test_commit_button_reflects_uncommitted_change_count | Assert the button is disabled (label reflects 0) when no changes exist. |
| PANEL-017 | Missing | — | Click the enabled commit button; assert the default commit prompt is sent to the agent. |
| PANEL-018 | Missing | — | Right-click commit button → "Edit prompt…", edit, Save; assert prompt persists and dialog closes. |
| PANEL-019 | Partial | test_history_panel.py::test_history_panel_shows_commits; ::test_terminus_visible_with_no_commits | Assert the "Loading history…" and error-message states. |
| PANEL-022 | Partial | test_history_panel.py::test_commit_hover_popover_shows_details; ::test_click_dismisses_popover | Click the copy-hash button; assert the hash is copied and the "Copied" indicator shows. |
| PANEL-025 | Partial | test_file_browser.py::test_multiple_tabs_and_close; ::test_clicking_tab_switches_displayed_file; ::test_cmd_w_closes_active_diff_tab; test_diff_tab_close_others.py::test_diff_tab_close_others | Assert tab drag-reorder, MRU-vs-adjacent close per setting, "Close all" menu item, full-path tooltip on hover. |
| PANEL-026 | Partial | test_file_browser.py::test_split_view_toggle; ::test_line_wrap_toggle; ::test_in_file_search_bar; ::test_close_diff_panel_button; test_diff_scope_and_fullscreen.py::test_expand_toggle_expands_and_collapses; test_expand_escape.py::test_escape_exits_expand_mode | Assert expand/fullscreen hides the file browser (current tests assert chat-panel hide). |
| PANEL-027 | Partial | test_file_browser.py::test_diff_file_header_shows_line_stats; test_file_browser_uncommitted.py::test_diff_header_line_stats_reflect_uncommitted_only; test_history_panel_diffs.py::test_commit_diff_file_header_shows_line_counts | Assert the breadcrumb path and the three-dot file-operations menu in the diff header. |
| PANEL-028 | Partial | test_history_panel.py::test_clicking_renamed_file_in_commits_shows_rename_banner | Assert the "Deleted" banner and the "Binary file (cannot display)" message. |
| PANEL-029 | Missing | — (test_regression_large_diff_crash.py checks no-crash only) | Open a diff over the threshold; assert truncated diff + "Show full diff" button; click → full diff renders. |
| PANEL-030 | Partial | test_file_browser.py::test_in_file_search_bar; ::test_in_file_search_works_in_file_view | Assert the "X of Y" counter, Enter/Shift+Enter (or arrows) navigation, Escape closing. |
| PANEL-036 | Partial | test_terminal_agent_basic.py::test_terminal_agent_basic; test_registered_terminal_agent.py (tab data-dot-status read/unread) | Produce output in a non-active tab; assert a pulsing unread dot appears, then clears after switching to it. |
| PANEL-037 | Missing | — (test_terminal.py references "Starting terminal…" only incidentally in an .or_(), not as a deterministic assertion) | Assert the "Starting terminal…" message renders while a terminal is starting. |
| PANEL-041 | Missing | — | Assert skills grouped into Custom/Sculptor/Built-in collapsible headers with a count badge when collapsed. |
| PANEL-042 | Missing | — | Hover a skill chip → description popover; hover another → swaps; mouse-leave closes after delay. |
| PANEL-044 | Missing | — | Open a custom/sculptor skill popover, click "open in Sculptor"; assert a file-view tab opens; built-in skills lack the option. |
| PANEL-045 | Missing | — | Drive the skills panel search: assert real-time filtering, arrow-key selection that auto-scrolls, Escape closing search, and the type-filter popover toggling which types are shown (active filters highlight the icon). |
| PANEL-046 | Missing | — | Assert Loading / error / "No skills found" / "Skills unavailable" states and chips disabled while the agent is running. |
| PANEL-047 | Partial | test_custom_actions.py::test_builtin_chips (Sculptor group first; no delete on builtin) | Assert collapsible group headers with count badges when collapsed and ungrouped actions at the bottom. |
| PANEL-048 | Partial | test_custom_actions.py::test_draft_action_drafts_prompt_into_terminal_pty; ::test_builtin_chips | Assert an auto-submit action sends immediately and chips are disabled while the agent runs. |
| PANEL-049 | Missing | — | Agent running, action chip context menu → "Queue message"; assert prompt queued (not auto-submitted). |
| PANEL-051 | Partial | test_custom_actions.py::test_create_group_from_settings; ::test_delete_group_deletes_actions_from_settings; ::test_delete_group_deletes_actions_from_panel | Assert inline group rename (Enter/blur confirms) and Escape-cancel on group create. |
| PANEL-052 | Missing | — | Drag an action/group → drop indicator + order updates; move action between groups; built-in items not draggable. |
| PANEL-056 | Partial | test_file_browser.py::test_split_view_toggle_persists_across_panel_reopen; ::test_line_wrap_toggle_persists_across_panel_reopen | Assert folder-expansion, scroll position, active-tab, view-mode (tree/flat), and diff-scope restored after switching tabs/files and returning. |

### CMDP

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| CMDP-001 | Partial | test_command_palette.py::test_open_command_palette_via_topbar_button; ::test_open_command_palette_via_keyboard_shortcut (palette visible + input focused only) | Assert group headers render in spec order (Workspaces → Navigation → Theme & Layout → Chat → Terminal → Help) with the first row selected on open. |
| CMDP-002 | Missing | — | Press Cmd+P; assert the palette opens on the "Go to workspace" sub-page (breadcrumb + "Find a workspace…" placeholder). |
| CMDP-003 | Missing | — | Open via Cmd+K, press Cmd+K again; assert the palette closes and no command ran. |
| CMDP-005 | Partial | test_command_palette.py::test_command_palette_filters_on_input (empty-state element only) | Assert the exact `No matches for '{query}'` copy including the typed query string. |
| CMDP-006 | Missing | — (test_command_palette_filters_on_input clears search with no post-assert) | Clear input; assert all commands reappear in group order with the first row re-selected. |
| CMDP-007 | Partial | test_command_palette.py::test_command_palette_escape_closes (empty-root close only) | Add: (a) non-empty search: Escape clears search first, second Escape closes; (b) sub-page: Escape returns to root without closing. |
| CMDP-008 | Missing | — | Open palette (no pending command), click the overlay/backdrop; assert the palette closes. |
| CMDP-009 | Missing | — | Press Down/Up; assert selection moves, scrolls into view, and wraps at both ends. |
| CMDP-013 | Partial | test_command_palette.py::test_command_palette_subpage_push_pop (breadcrumb visible/absent only) | Assert the breadcrumb shows the page title and its X control returns to root. |
| CMDP-014 | Missing | — | Surface a context-disabled command; assert the row is greyed out and shows its reason as subtitle/tooltip. |
| CMDP-015 | Missing | — | Assert the trailing area shows a kbd-badge shortcut / right chevron on page-openers / group label during search per case. |
| CMDP-016 | Missing | — | Run an async command; assert the row shows a spinner and the palette refuses to close until it completes. |
| CMDP-017 | Partial | test_command_palette.py::test_command_palette_navigates_to_settings; ::test_command_palette_creates_new_agent | Add Open home navigates home, New workspace opens add-workspace, and assert New agent disabled/hidden off a workspace. |
| CMDP-018 | Partial | test_command_palette.py::test_command_palette_keep_open_command (runs theme.toggle but does NOT assert the appearance changed); ::test_command_palette_subpage_push_pop | Assert running a theme command actually changes the applied appearance. |
| CMDP-019 | Missing | — | On a workspace, run panel/mode toggles; assert the panel/mode visibly toggled (focus/zen close palette; zone toggles keep it open). |
| CMDP-021 | Missing | — | Add Clear terminal clears the active terminal; Show keyboard shortcuts opens the dialog; terminal command hidden without a terminal panel. |
| CMDP-022 | Missing | — | With 2+ workspaces, open "Go to workspace…"; assert status dots + current disabled; select another to navigate. |
| CMDP-023 | Missing | — | With 2+ tabs, run Next/Previous workspace tab; assert the active tab changes. |
| CMDP-024 | Missing | — | Open "Workspace actions…"; assert the labeled actions list; run one (e.g. Rename) end-to-end. |
| CMDP-025 | Missing | — | On a local backend, open "Open in…"; assert ordering (preferred first) + a disabled-on-remote case + an app launching. |
| CMDP-026 | Missing | — | In a multi-agent workspace, open "Go to agent…"; assert current disabled; select another to navigate; opener disabled with one agent. |
| CMDP-027 | Missing | — | Open "Agent actions…" and run each (rename dialog / marked unread / delete confirmation) from the palette. |
| CMDP-028 | Partial | test_command_palette.py::test_command_palette_cross_page_reveal_finds_subpage_item (visibility only) | Open "Go to settings…", select a section (e.g. Keybindings); assert that section is shown. |
| CMDP-029 | Missing | — | Under real pointer events, assert the first pointer move is ignored (keyboard selection stays) and a subsequent hover selects the hovered row. |
| CMDP-030 | Partial | test_command_palette.py::test_command_palette_top_result_is_not_scrolled_past; ::test_command_palette_list_does_not_animate_scrolls | Assert the list scroll position resets to top on each open and the first row is selected. |
| CMDP-031 | Missing | — | Render a very long agent/workspace title in the palette; assert it truncates with "…". |

### SET / DEV

| Scenario | Status | Existing integration test(s) | Integration tests to add |
|----------|--------|------------------------------|--------------------------|
| SET-001 | Partial | test_settings_tab.py::test_settings_opens_as_tab; piecemeal section-clicks across test_settings_integration.py, test_keybindings.py, test_custom_actions.py | One nav test clicking every sidebar item asserting active content; cover the mobile dropdown; CI, File Browser, Git, Env-Vars, Experimental are never opened-and-asserted as a nav target. |
| SET-002 | Missing | — | Load `/#/settings?section=<x>` and assert it opens directly to that section. |
| SET-003 | Missing | — | View a non-default section, reopen Settings; assert the last-viewed section is restored. |
| SET-004 | Partial | test_settings_integration.py::test_env_vars_override_toggle_saves_setting; test_keybindings.py; test_custom_actions.py (success toast broadly) | Assert the "Failed to update setting" error-toast path (induce a save failure). |
| SET-005 | Missing | — | In General, pick Light/Dark/System; assert app appearance changes immediately. |
| SET-020 | Partial | test_multi_repo.py::test_create_workspaces_in_multiple_projects_and_switch; test_regression_settings_delete_repo_stays_on_page.py | Assert per-repo path, agent count, and the accessibility/missing-path warning. |
| SET-021 | Partial | test_workspace_setup_command.py::test_setup_command_input_visible_in_settings; ::test_setup_command_saves_on_blur; ::test_setup_edit_button_deep_links_to_focused_textarea; test_regression_setup_command_backfill.py | Cover the branch-naming pattern field and the setup-command "Using default"/"Reset to default" affordances. |
| SET-022 | Partial | test_delete_last_repo.py::test_deleting_last_repo_shows_onboarding_add_repo_step; test_regression_settings_delete_repo_stays_on_page.py::test_deleting_repo_stays_on_settings_page | Assert the confirmation dialog showing the agent count and the success/error toast on remove. |
| SET-023 | Missing | — (no Git-settings UI test) | Edit PR-creation prompt (+reset), toggle PR polling (dependent fields disable), poll-interval 10–300s validation, closed-workspace multiplier 1–120× validation, default target branch — each with save toast. |
| SET-024 | Missing | — | Edit default branch-naming pattern (toast); set branch-deletion policy Never / Delete-if-safe / Always (toast). |
| SET-025 | Missing | — (test_ci_babysitter.py configures via API, not the Settings UI) | Toggle babysitter, retry-cap 1–10 validation, edit pipeline-failed & merge-conflict prompts (+reset), dependent fields disable when off, save toast. |
| SET-026 | Missing | — | Split-ratio 20–80%, tab-close behavior, line-wrapping, default diff view, commit prompt (+reset) — each with save toast. |
| SET-027 | Partial | test_settings_integration.py::test_env_vars_section_shows_setup_instructions; ::test_env_vars_override_toggle_saves_setting; ::test_env_vars_loaded_names_shows_no_vars_without_env_file; test_project_env_vars.py::test_env_var_names_shown_in_settings | Cover the refresh button and the global-vs-repo-specific grouping of the loaded list. |
| SET-031 | Partial | test_custom_actions.py::test_create_action_from_settings; ::test_edit_action_from_settings; ::test_delete_action_from_settings; ::test_create_group_from_settings; ::test_delete_group_deletes_actions_from_settings; ::test_builtin_chips | Cover Export ("sculptor-actions.json" download, disabled-when-empty) and Import (file picker, validate+merge+count toast). |
| SET-032 | Partial | test_custom_actions.py::test_create_action_from_settings; ::test_edit_action_from_settings | Assert Save disabled until valid, Cmd+Enter submits, and the Auto-submit toggle behavior within the dialog. |
| SET-033 | Partial | test_custom_actions.py::test_create_group_from_settings; ::test_delete_group_deletes_actions_from_settings | Assert drag-to-reorder and inline group rename + success toast. |
| DEV-001 | Partial | test_tanstack_devtools_panel.py::test_tanstack_devtools_panel_mounts_with_content (panel mounts only) | Cover header Dock/Float/Close controls, floating drag + resize within viewport, docked resize-from-top-edge + pushes content up, and closing hides it. |
| DEV-002 | Missing | — | Click a markdown link with an external protocol; assert it opens in the OS browser and shows an external-link icon. |
| DEV-003 | Missing | — | Click a `#anchor` markdown link; assert navigation is prevented and a dashed-underline style + "In-page anchor links aren't supported yet" tooltip are shown. |
| DEV-004 | Missing | — | Click a relative or unsupported-scheme markdown link; assert navigation is prevented and a broken-link icon + "Linked-file navigation isn't supported yet" tooltip are shown. |

---

## Complete coverage

Every scenario an integration test fully covers — it performs the user action *and* asserts the user-visible outcome — with the test(s) that cover it. Partial and Missing scenarios are in the gaps section above, not here.

### SHELL / ROUTE / HELP

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| SHELL-001 | test_workspace_tab_enhancements.py::test_cmd_t_opens_new_workspace_page |
| SHELL-003 | test_settings_tab.py::test_settings_opens_as_tab |
| SHELL-007 | test_workspace_tab_enhancements.py::test_new_workspace_tab_x_navigates_to_mru_workspace; test_home_page_tab.py::test_home_tab_is_closeable |
| SHELL-009 | test_workspace_tab_enhancements.py::test_cmd_w_closes_workspace_tab_without_deletion; ::test_cmd_w_on_new_workspace_page_navigates_to_mru_workspace |
| SHELL-016 | test_workspace_tab_context_menu_icons.py::test_workspace_context_menu_rename; ::test_workspace_context_menu_rename_escape_cancels |
| SHELL-017 | test_workspace_tab_enhancements.py::test_context_menu_delete_removes_workspace |
| SHELL-020 | test_closed_workspaces_dropdown.py::test_pill_visibility_toggles_with_closed_workspace_count |
| SHELL-021 | test_closed_workspaces_dropdown.py::test_dropdown_opens_and_shows_closed_workspace_rows |
| SHELL-022 | test_closed_workspaces_dropdown.py::test_reopen_workspace_from_dropdown |
| SHELL-023 | test_closed_workspaces_dropdown.py::test_open_all_reopens_all_closed_workspaces |
| SHELL-024 | test_closed_workspaces_dropdown.py::test_delete_workspace_from_dropdown |
| SHELL-025 | test_command_palette.py::test_open_command_palette_via_topbar_button |
| SHELL-028 | test_zen_mode.py::test_zen_mode_hides_chrome_and_panels |
| SHELL-029 | test_zen_mode.py::test_exit_zen_mode_button_works |
| SHELL-030 | test_zen_mode.py::test_workspace_tab_navigation_works_in_zen_mode |
| SHELL-031 | test_zen_mode.py::test_focus_mode_hides_panels_but_keeps_chrome |
| SHELL-032 | test_zen_mode.py::test_panel_toggle_in_zen_mode_persists_on_exit |
| ROUTE-001 | test_restart_mru.py::test_restart_restores_active_workspace_and_agent; ::test_restart_with_no_mru_lands_on_new |

### HOME / ADDWS / ADDREPO

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| HOME-002 | test_home_page.py::test_empty_state_shown_for_new_user |
| HOME-013 | test_home_page.py::test_clicking_workspace_row_navigates_to_workspace; test_home_page_tab.py::test_clicking_workspace_replaces_home_tab |
| ADDWS-005 | test_add_workspace_page.py::test_workspace_form_draft_persists_after_navigation; ::test_multiple_new_workspace_tabs_with_independent_drafts |
| ADDWS-013 | test_worktree_create_happy_path.py::test_worktree_create_with_default_branch_name |
| ADDWS-015 | test_branch_name_collisions.py::test_worktree_mode_collision_blocks_creation |
| ADDWS-016 | test_add_workspace_agent_type.py::test_agent_type_select_visible_with_claude_default; ::test_terminal_first_agent; test_agent_type_menu.py::test_registered_terminal_agent_appears_in_menu_and_creates |
| ADDWS-017 | test_add_workspace_agent_type.py::test_first_agent_type_defaults_to_shared_last_used; test_agent_type_menu.py::test_agent_type_menu_creates_terminal_agent_and_remembers_type |
| ADDWS-021 | test_worktree_create_happy_path.py::test_worktree_create_with_default_branch_name; test_add_workspace_page.py::test_cmd_enter_in_workspace_name_creates_workspace |
| ADDWS-022 | test_add_workspace_page.py::test_arrow_down_focuses_name_input_when_nothing_focused; ::test_arrow_up_focuses_name_input_when_nothing_focused |
| ADDREPO-007 | test_path_autocomplete_keyboard.py::test_enter_on_directory_highlights_first_subentry; ::test_selected_folder_submit_shows_correct_repo_name |

### ONB / ACT

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| ONB-030 | test_onboarding.py::test_full_onboarding_flow |
| ACT-001 | test_custom_actions.py::test_draft_action_drafts_prompt_into_terminal_pty; ::test_builtin_chips; ::test_create_action_from_panel |
| ACT-004 | test_custom_actions.py::test_delete_action_from_settings; ::test_delete_group_deletes_actions_from_settings; ::test_delete_group_deletes_actions_from_panel |

### WS

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| WS-028 | test_ci_babysitter.py::test_scenario_4_pause_toggle_prevents_prompt |
| WS-037 | test_zen_mode.py::test_zen_mode_hides_chrome_and_panels; ::test_focus_mode_hides_panels_but_keeps_chrome |
| WS-040 | test_workspace_banner.py::test_banner_shows_diff_stats; ::test_banner_click_navigates_to_changes_all |
| WS-041 | test_multi_agent_workspace.py::test_multiple_agent_tabs_shown_for_shared_workspace; ::test_single_agent_shows_one_agent_tab |
| WS-044 | test_multi_agent_workspace.py::test_create_second_agent_in_existing_workspace |
| WS-045 | test_agent_type_menu.py::test_agent_type_menu_creates_terminal_agent_and_remembers_type; ::test_registered_terminal_agent_appears_in_menu_and_creates |
| WS-047 | test_agent_tab_context_menu.py::test_agent_context_menu_has_rename_and_delete; test_agent_diagnostics_context_menu.py::test_agent_diagnostics_claude_items_disabled_for_terminal_agent; ::test_agent_context_menu_copy_name_and_id |
| WS-048 | test_agent_tab_context_menu.py::test_agent_context_menu_delete; test_multi_agent_workspace.py::test_workspace_survives_when_other_agents_remain |
| WS-049 | test_mark_unread.py::test_mark_adjacent_tab_unread |
| WS-051 | test_terminal_agent_basic.py::test_terminal_agent_basic |
| WS-052 | test_terminal_agent_basic.py::test_terminal_agent_basic (switch away/back, scrollback restored); test_terminal_tab_enhancements.py::test_terminal_compact_layout_no_heading |
| WS-066 | test_side_toggle.py::test_right_side_toggle_hides_and_shows_panels; ::test_bottom_toggle_hides_and_shows_terminal |
| WS-074 | test_workspace_setup_command.py::test_setup_config_prompt_deep_links_to_focused_textarea; test_regression_setup_command_backfill.py; test_regression_setup_command_rerun.py::test_setup_rerun_button_runs_command_again |

### PANEL

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| PANEL-001 | test_file_browser.py::test_filter_tabs_switch_between_all_and_changes; ::test_changes_tab_shows_count; test_file_browser_tabs.py::test_tab_switching_shows_correct_content |
| PANEL-004 | test_file_browser.py::test_collapse_all_folders_button; ::test_collapse_all_changes_folders_button; ::test_collapse_all_commits_button |
| PANEL-006 | test_file_browser.py::test_file_search; ::test_file_search_filters_visible_rows; ::test_file_search_escape_closes; ::test_file_search_no_matches_shows_empty_state; ::test_file_search_folders_are_collapsible |
| PANEL-007 | test_file_browser.py::test_folder_expand_and_collapse; ::test_collapse_all_folders_button |
| PANEL-008 | test_file_browser.py::test_click_file_opens_diff_panel; ::test_changes_tab_click_opens_diff; test_file_open_diff_modes.py::test_browse_tab_opens_file_view |
| PANEL-014 | test_diff_scope_switching.py::test_scope_switch_toggles_active_scope; test_file_open_diff_modes.py::test_committed_file_visible_in_all_scope_only; test_file_browser_tabs.py::test_tab_switching_shows_correct_content |
| PANEL-015 | test_discard_file.py::test_discard_file_removes_from_changes; ::test_discard_cancel_preserves_file; test_discard_preserves_all_tab.py::test_discard_last_uncommitted_keeps_all_tab_populated |
| PANEL-020 | test_history_panel.py::test_commit_entry_shows_metadata_line; ::test_merge_commit_shows_spur |
| PANEL-021 | test_file_browser.py::test_collapse_all_commits_button; test_history_panel_diffs.py::test_click_file_in_multi_file_commit; ::test_switch_files_within_same_commit |
| PANEL-023 | test_history_panel_diffs.py::test_commit_diff_shows_committed_content_not_uncommitted; ::test_commit_diff_file_header_shows_line_counts; ::test_same_file_two_commits_shows_correct_content |
| PANEL-024 | test_history_panel.py::test_merge_commit_shows_spur; ::test_terminus_shows_fork_point_hash; ::test_terminus_visible_with_no_commits |
| PANEL-031 | test_file_open_diff_modes.py::test_browse_tab_opens_file_view; test_sculpt_ui_open_file.py::test_mode_file_opens_file_view_tab; test_open_in_viewer.py::test_open_created_file_in_diff_viewer |
| PANEL-034 | test_terminal.py::test_add_terminal_tab_creates_new_session; ::test_close_terminal_tab_switches_to_neighbor; ::test_terminal_tab_reuses_lowest_available_number; test_terminal_tab_enhancements.py::test_terminal_tab_double_click_rename; ::test_terminal_context_menu_has_close_all_and_rename |
| PANEL-035 | test_terminal.py::test_opt_left_moves_cursor_back_by_word; ::test_ctrl_c_cancels_input; ::test_ctrl_d_shows_process_exited_message; test_terminal_agent_basic.py::test_terminal_agent_basic |
| PANEL-050 | test_custom_actions.py::test_create_action_from_panel; ::test_edit_action_from_settings; ::test_delete_action_from_settings; ::test_builtin_chips |

### CMDP

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| CMDP-004 | test_command_palette.py::test_command_palette_filters_on_input |
| CMDP-010 | test_command_palette.py::test_command_palette_navigates_to_settings |
| CMDP-011 | test_command_palette.py::test_command_palette_cmd_enter_keeps_palette_open |
| CMDP-012 | test_command_palette.py::test_command_palette_subpage_push_pop |

### SET

| Scenario | Existing integration test(s) |
|----------|------------------------------|
| SET-008 | test_keybindings.py::test_search_filters_keybindings |
| SET-009 | test_keybindings.py::test_record_new_keybinding; ::test_escape_cancels_recording; ::test_click_outside_cancels_recording; ::test_starting_second_recording_cancels_first |
| SET-010 | test_keybindings.py::test_duplicate_detection_reassign; ::test_duplicate_detection_cancel |
| SET-011 | test_keybindings.py::test_clear_keybinding; ::test_reset_all_to_defaults |

---

## How to use this report

- **Fill Missing first** where the behavior is user-critical and entirely untested by integration
  tests (see "Highest-value gaps" above).
- **Upgrade Partials** by adding the single missing assertion named in the right-hand column — these
  are cheap because a related integration test already drives the relevant state.
- Add new integration tests under `sculptor/tests/integration/frontend/` using the
  `write-integration-test` skill (the fake registered terminal agent for deterministic agent
  behavior). Reach for `real_claude` only when the behavior genuinely needs a live model.
- The command palette (CMDP) is the single biggest integration gap: most commands have no end-to-end
  "ran the command → saw the on-screen result" assertion. A focused pass over `test_command_palette.py`
  that opens each sub-page and asserts the visible outcome would move ~18 scenarios from
  Missing/Partial to Complete.

*Coverage assessed by reading the cited integration tests, not filenames alone. Counts are derived
from the per-area tables; where a single scenario spans multiple controls (notably SET-*), status
reflects the weakest uncovered part.*
