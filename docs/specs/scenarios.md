# Sculptor — User-Facing Scenarios

This document enumerates every user-facing interaction and behavior in the Sculptor
frontend, expressed as Given/When/Then scenarios. It is intended as the source of truth
for building a test plan and integration tests that exercise **100% of user-visible
behavior**.

## Conventions

- **Given** = the precondition / app state the user can observe or that is set up before the action.
- **When** = the concrete user action (a click, key press, hover, drag, type, etc.).
- **Then** = the result that is **visible on screen**. Every assertion in a Then must be
  something a person can see in the UI — visible text, an icon, a color/state change, a
  panel appearing/disappearing, navigation, a toast, a tooltip, focus moving, etc. Do **not**
  assert on invisible markers (DOM attributes, atoms, localStorage, network calls) as the
  primary observable; those may be referenced parenthetically as implementation hints only.
- Each scenario has a stable ID (`AREA-NNN`) so tests can reference it.
- Keybindings are written in the macOS form (`Cmd`); the Windows/Linux equivalent is `Ctrl`.

## Areas / ID prefixes

| Prefix | Area |
|--------|------|
| `SHELL` | App shell: tabs, top bar, window controls, version, status banners |
| `ROUTE` | Routing, redirects, error/404 pages, startup |
| `HELP` | Keyboard-shortcuts (Help) dialog |
| `HOME` | Home page / recent-workspaces list |
| `ONB` | Onboarding (PATH check & add first repo) |
| `ADDWS` | Add-workspace page (create workspace form) |
| `ADDREPO` | Add-repository flow, dialogs, and path autocomplete |
| `WS` | Workspace shell (banner, PR button, agent tabs, terminal agent, peek, layout) |
| `PANEL` | Workspace side panels (files, changes, history, diff, terminal, actions) |
| `CMDP` | Command palette |
| `SET` | Settings page |
| `ACT` | Actions feature components |
| `DEV` | Dev/debug panels and markdown links |

---

# SHELL — App shell, tabs & navigation

## Tabs

- **SHELL-001 — Open a new workspace tab**
  - Given: the app is open on any page.
  - When: the user clicks the `+` button at the end of the tab bar, or presses `Cmd+T`.
  - Then: a new "New Workspace" tab appears, becomes active, and the Add Workspace form is shown.

- **SHELL-002 — Open the Home tab**
  - Given: the app is open.
  - When: the user clicks the Home button in the top bar, or presses the Home keybinding.
  - Then: a "Home" tab is shown (created if absent, otherwise re-activated) and the home page is displayed.

- **SHELL-003 — Open the Settings tab**
  - Given: the app is open.
  - When: the user clicks the Settings (gear) button in the top bar, or presses the Settings keybinding.
  - Then: a "Settings" tab is shown and the settings page is displayed.

- **SHELL-004 — Switch tabs by clicking**
  - Given: multiple tabs are open.
  - When: the user clicks a non-active tab.
  - Then: that tab becomes highlighted/active and its content is shown.

- **SHELL-005 — Cycle to next tab**
  - Given: multiple tabs are open.
  - When: the user presses `Cmd+]`.
  - Then: the next tab to the right becomes active, wrapping to the first after the last.

- **SHELL-006 — Cycle to previous tab**
  - Given: multiple tabs are open.
  - When: the user presses `Cmd+[`.
  - Then: the previous tab becomes active, wrapping to the last before the first.

- **SHELL-007 — Close a tab via its X button**
  - Given: a tab is present.
  - When: the user clicks the tab's X (close) button.
  - Then: the tab disappears; an adjacent tab becomes active, or the Add Workspace page is shown if it was the last tab.

- **SHELL-008 — Close a tab via middle-click**
  - Given: multiple tabs are open.
  - When: the user middle-clicks a tab.
  - Then: that tab closes without changing which tab is active (unless the active one was closed).

- **SHELL-009 — Close the current tab via keyboard**
  - Given: a workspace/Home/Settings tab is active.
  - When: the user presses `Cmd+W`.
  - Then: the active tab closes and a remaining tab (or the Add Workspace page) is shown.

- **SHELL-010 — Reorder tabs by dragging**
  - Given: multiple tabs are open.
  - When: the user drags a tab horizontally past another.
  - Then: a drop indicator appears, and on release the tabs reorder; the active tab is unchanged.

- **SHELL-011 — Tab overflow scrolling**
  - Given: more tabs are open than fit in the bar.
  - When: the user scrolls (wheel or trackpad) over the tab bar.
  - Then: the tab strip scrolls horizontally to reveal hidden tabs.

- **SHELL-012 — Active tab auto-scrolls into view**
  - Given: tabs overflow and the active tab is off-screen.
  - When: a tab becomes active (e.g., via keyboard cycle).
  - Then: the strip scrolls so the active tab is visible.

- **SHELL-013 — Tab label truncates**
  - Given: a tab with a long title.
  - When: the tab is rendered at a constrained width.
  - Then: the label is truncated with an ellipsis.

- **SHELL-014 — Workspace tab status dots**
  - Given: a workspace tab whose agents have a status.
  - When: the tab is displayed.
  - Then: status dot(s) appear next to the name (pulsing for running, solid for waiting/ready, red for error, two dots for mixed states).

- **SHELL-015 — Tab right-click context menu**
  - Given: a tab is present.
  - When: the user right-clicks the tab.
  - Then: a context menu appears with at least Close / Close others / Close all (and Rename/Delete + git actions for workspace tabs).

- **SHELL-016 — Rename a workspace tab inline**
  - Given: a workspace tab's context menu is open, or the user double-clicks the tab.
  - When: the user chooses Rename (or double-clicks), types a new name, and presses Enter.
  - Then: the tab label updates to the new name; pressing Escape instead cancels and restores the old name.

- **SHELL-017 — Delete a workspace from its tab**
  - Given: a workspace tab context menu is open.
  - When: the user chooses Delete and confirms in the dialog.
  - Then: the tab disappears and an adjacent tab/page is shown.

- **SHELL-018 — Close others / Close all from tab menu**
  - Given: multiple tabs open and a tab's context menu is open.
  - When: the user chooses "Close others" or "Close all".
  - Then: all other tabs (or all tabs) close accordingly; "Close all" navigates to the Add Workspace page.

- **SHELL-019 — Tabs persist across restart**
  - Given: the user has tabs open in a particular order with one active.
  - When: the app is closed and reopened.
  - Then: the same tabs reappear in the same order and the previously active tab is shown.

## Closed-workspaces pill

- **SHELL-020 — Closed-workspaces pill appears**
  - Given: the user has closed one or more workspace tabs.
  - When: viewing the top bar.
  - Then: a "Closed N" pill is visible.

- **SHELL-021 — Open the closed-workspaces menu**
  - Given: the closed-workspaces pill is visible.
  - When: the user clicks it.
  - Then: a dropdown lists recently-closed workspaces (showing a spinner while loading).

- **SHELL-022 — Reopen a closed workspace**
  - Given: the closed-workspaces dropdown is open.
  - When: the user clicks a workspace row.
  - Then: that workspace tab reopens and is shown; the dropdown closes.

- **SHELL-023 — Open all closed workspaces**
  - Given: the closed-workspaces dropdown is open.
  - When: the user clicks "Open all".
  - Then: all closed workspace tabs reopen in the bar; the dropdown closes.

- **SHELL-024 — Delete a closed workspace from the menu**
  - Given: the closed-workspaces dropdown is open.
  - When: the user triggers delete on a row and confirms.
  - Then: that row disappears from the list and the workspace is gone.

## Top-bar buttons

- **SHELL-025 — Command palette button**
  - Given: the top bar is visible.
  - When: the user clicks the search/command icon (tooltip "Command palette").
  - Then: the command palette opens with its input focused.

- **SHELL-026 — Help button**
  - Given: the top bar is visible.
  - When: the user clicks the Help (?) icon.
  - Then: the keyboard-shortcuts dialog opens.

- **SHELL-027 — Top-bar button tooltips**
  - Given: the top bar is visible.
  - When: the user hovers a top-bar button.
  - Then: a tooltip shows the button name and its keyboard shortcut.

## Panel toggles

- **SHELL-032 — Toggle individual panels via keyboard**
  - Given: the user is on a workspace page.
  - When: the user presses `Cmd+Alt+Left` / `Cmd+Alt+Down` / `Cmd+Alt+Right`.
  - Then: the left / bottom / right panel toggles hidden/visible respectively.

## Theme

- **SHELL-033 — Toggle theme via keyboard**
  - Given: the app is focused.
  - When: the user presses `Cmd+Shift+D`.
  - Then: the app switches between light and dark mode immediately, with no reload.

## Version indicator

- **SHELL-034 — Version number shown**
  - Given: the user is on a non-workspace page.
  - When: the page renders.
  - Then: the version number is visible in the bottom-right corner.

- **SHELL-035 — Open version popover**
  - Given: the version number is visible.
  - When: the user clicks the version number.
  - Then: a popover opens showing the version number, the git SHA, and diagnostics (platform, uptime, active agents, disk, paths, install info).

- **SHELL-041 — Dev-tools toggles in version popover**
  - Given: the version popover is open.
  - When: the user toggles "React Grab", "TanStack Devtools", or "TanStack event log".
  - Then: the corresponding dev tool appears/disappears.

## Status banners

- **SHELL-042 — Backend-unresponsive banner**
  - Given: the backend becomes unresponsive.
  - When: the status changes.
  - Then: a centered warning banner (triangle-alert icon) reads "The backend process is down or unresponsive. Please restart the application."

- **SHELL-043 — Backend health-warning banner**
  - Given: the backend reports a health warning.
  - When: the status changes.
  - Then: a yellow warning banner appears with the warning message.

- **SHELL-044 — Missing project-folder banner**
  - Given: the active workspace's project folder is not found.
  - When: the page renders.
  - Then: a banner reads "Project folder not found: {name}." with a "Learn more" link that opens a dialog.

- **SHELL-045 — Backend loading splash**
  - Given: the app is starting and the backend is launching.
  - When: viewing the screen.
  - Then: a splash with the Sculptor logo, a "beta" label, and a progress bar (with an optional status message) is shown until the backend is ready.

- **SHELL-046 — Backend shutting-down screen**
  - Given: the app is quitting / restarting the backend.
  - When: the status becomes shutting-down.
  - Then: a "Shutting down..." message with a progress bar is shown; if stalled past ~30s a recovery message appears.

- **SHELL-047 — Dev-mode indicator**
  - Given: the app is running from source (not packaged).
  - When: viewing the page.
  - Then: a dev-mode indicator is shown (bottom-center); hovering it shows a "Running from source" tooltip with the workspace id.

## Window & zoom

- **SHELL-048 — Zoom in / out / reset**
  - Given: the app is focused.
  - When: the user presses `Cmd+=`, `Cmd+-`, or `Cmd+0`.
  - Then: the UI scales up, down, or back to 100% respectively, and the zoom level persists across restarts.

---

# ROUTE — Routing, startup & error pages

- **ROUTE-001 — Startup redirect to last active tab**
  - Given: the user had tabs open previously.
  - When: the app launches and loads `/`.
  - Then: it redirects to the previously active tab's page (or the Add Workspace page if none).

- **ROUTE-002 — New-workspace route generates a draft**
  - Given: the user navigates to `/ws/new`.
  - When: the route loads.
  - Then: it redirects to `/ws/new/{draftId}` and shows the Add Workspace form.

- **ROUTE-003 — 404 page for unknown route**
  - Given: the user navigates to a URL that matches no route.
  - When: the page loads.
  - Then: a Not-Found page shows the Sculptor logo and "The page you are looking for does not exist." with a link back to home.

- **ROUTE-004 — Route error boundary**
  - Given: a route loader or component throws.
  - When: the error occurs.
  - Then: an error page is shown with a generic message and the error details in a scrollable box.

- **ROUTE-005 — Copy error to clipboard**
  - Given: the route error page is shown.
  - When: the user clicks "Copy Error to Clipboard".
  - Then: the error text is copied (a person can paste it elsewhere).

---

# HELP — Keyboard shortcuts dialog

- **HELP-001 — Open the help dialog**
  - Given: the app is focused.
  - When: the user clicks the Help button or presses `Cmd+/`.
  - Then: a modal titled "Help" opens listing all keybindings grouped by category.

- **HELP-002 — Shortcuts formatted per OS**
  - Given: the help dialog is open.
  - When: viewing a shortcut.
  - Then: it is shown in a key-badge formatted for the current OS (e.g., `Cmd+K` on macOS, `Ctrl+K` elsewhere).

- **HELP-003 — Close the help dialog**
  - Given: the help dialog is open.
  - When: the user clicks the X or presses Escape.
  - Then: the dialog closes.

---

# HOME — Home page / recent workspaces

The home page and the Add Workspace page share the recent-workspaces list and its rows.

- **HOME-001 — Loading state**
  - Given: the workspace list is being fetched.
  - When: the page first renders.
  - Then: a spinner is shown in the list area.

- **HOME-002 — Empty state (no workspaces)**
  - Given: the user has no workspaces.
  - When: the list loads.
  - Then: a centered folder icon, "No workspaces yet" heading, and a "Describe what you need above to create your first workspace." message are shown.

- **HOME-003 — Search bar present & autofocused**
  - Given: at least one workspace exists.
  - When: the page loads.
  - Then: a search input with placeholder "Search workspaces..." is shown and focused.

- **HOME-004 — Filter workspaces by query**
  - Given: the workspace list is populated.
  - When: the user types in the search box.
  - Then: the list filters in real time by workspace name, branch, and project (case-insensitive).

- **HOME-005 — No search results**
  - Given: a search query matches nothing.
  - When: filtering completes.
  - Then: a centered message `No results for "{query}"` is shown.

- **HOME-006 — Escape clears search**
  - Given: the search box has text and focus.
  - When: the user presses Escape.
  - Then: the query clears, the full list returns, and focus returns to the search input.

- **HOME-007 — Sort order**
  - Given: multiple workspaces.
  - When: the list is shown.
  - Then: workspaces are ordered by most recent activity first.

- **HOME-008 — Pagination "Show more"**
  - Given: more than 25 workspaces exist.
  - When: the list loads.
  - Then: only 25 rows show, with a "Show more (N remaining)" button; clicking it reveals the next 25.

- **HOME-009 — Search resets visible count**
  - Given: more than 25 rows are shown after "Show more".
  - When: the user types a search query.
  - Then: the visible count resets to the first 25 filtered results.

- **HOME-010 — Workspace row contents**
  - Given: a workspace exists.
  - When: the row is shown.
  - Then: it shows a status dot, the workspace name, the branch name (monospace), a PR button if a branch exists, the project name (revealed on hover), a relative last-activity time, and a delete button (revealed on hover).

- **HOME-011 — Row hover/focus styling**
  - Given: a workspace row.
  - When: the user hovers or keyboard-focuses it.
  - Then: the row background changes and the project name and delete button become visible.

- **HOME-012 — Keyboard navigation into the list**
  - Given: the search box is focused.
  - When: the user presses ArrowDown.
  - Then: the first row gains focus and scrolls into view; ArrowUp from the first row returns focus to the search box.

- **HOME-013 — Open a workspace with Enter / click**
  - Given: a row is focused or visible.
  - When: the user presses Enter on it (or clicks it without a modifier).
  - Then: the current tab becomes that workspace and it opens.

- **HOME-014 — Open a workspace in a new tab**
  - Given: a workspace row is visible.
  - When: the user Cmd/Ctrl-clicks it (or chooses "Open in New Tab" from its right-click menu).
  - Then: the workspace opens in a new tab while the home page remains visible.

- **HOME-015 — Row context menu**
  - Given: a workspace row.
  - When: the user right-clicks it.
  - Then: a menu with "Open in New Tab" and "Delete Workspace" (in red) appears.

- **HOME-016 — Delete via row button / menu**
  - Given: a row is hovered (delete button visible) or its context menu is open.
  - When: the user clicks the delete trash icon or "Delete Workspace".
  - Then: a delete-confirmation dialog opens.

- **HOME-017 — Delete confirmation dialog**
  - Given: the delete dialog is open.
  - When: viewing it.
  - Then: it shows "Delete workspace?", a warning naming the workspace, a Cancel button, and a red Delete button (focused by default).

- **HOME-018 — Cancel deletion**
  - Given: the delete dialog is open.
  - When: the user clicks Cancel or presses Escape.
  - Then: the dialog closes and the workspace remains.

- **HOME-019 — Confirm deletion**
  - Given: the delete dialog is open.
  - When: the user clicks Delete (or presses Enter).
  - Then: the dialog closes and the row disappears from the list immediately.

- **HOME-020 — PR button states on a row**
  - Given: a workspace row with a branch.
  - When: the PR status is known.
  - Then: the button reflects the state: a spinner + "Checking PR…" while loading; "Create PR" when none exists; "PR #N" with pipeline & review status dots when open; a merged/closed badge when merged/closed; an "Assign PR" option when a PR targets a different branch; and an error button (warning/info icon) on failure.
  - (See WS-PR scenarios for full PR-button behavior; rows reuse the same component.)

---

# ONB — Onboarding (PATH check & add first repo)

## Step indicator

- **ONB-034 — Step indicator shows two steps**
  - Given: the onboarding wizard is shown.
  - When: viewing the bottom indicator.
  - Then: two dots represent the PATH check and Add-Repo steps; the current step is visually distinct, a completed step is clickable to return to it, and an upcoming step is not clickable.

## PATH check step

- **ONB-035 — PATH-check screen contents**
  - Given: the PATH check step is shown.
  - When: the page renders.
  - Then: a "Check your tools" heading and an explanatory line stating Sculptor only checks (never installs) the tools are shown, with a status row for `claude` and one for `git`: each found tool shows a green check and "{name} found on your PATH".

- **ONB-036 — Missing tool message & install link**
  - Given: the PATH check step is shown and a required tool is not on PATH.
  - When: the page renders.
  - Then: that tool's row shows a red icon and "{name} not found on your PATH", a message that it can still continue but the tool must be installed, and a "How to install {name}" link (there is no install button).

- **ONB-037 — Continue into the app**
  - Given: the PATH check step is shown.
  - When: the user clicks "Continue".
  - Then: the wizard advances regardless of whether a tool is missing (the check is non-blocking) — to the Add-Repo step if the user has no repos, otherwise straight into the app.

## Add-repo step

- **ONB-027 — Add-repo step header & input**
  - Given: the Add-Repo step is shown.
  - When: viewing the page.
  - Then: "Add your first repo" with a path input (placeholder `~/path/to/repo`, autofocused) is shown.

- **ONB-028 — Browse for folder (desktop)**
  - Given: the Add-Repo step on desktop.
  - When: the user clicks "Or browse for a folder" and selects a folder.
  - Then: the path input is populated with the chosen path.

- **ONB-029 — Add button gating**
  - Given: the Add-Repo step.
  - When: the path is empty.
  - Then: the Add button is disabled with tooltip "Enter a repository path above"; entering a path enables it; clicking it shows a spinner while validating.

- **ONB-030 — Valid repo added**
  - Given: a path to a valid git repo with commits is entered.
  - When: the user clicks Add.
  - Then: validation succeeds, the wizard completes, and the user is taken into the app.

- **ONB-031 — Not-a-git-repo prompt**
  - Given: a path to a non-git directory is entered.
  - When: the user clicks Add.
  - Then: a dialog offers to initialize git; choosing "Initialize Git" shows "Setting up repository…" and on success adds the repo; Cancel returns to the step.

- **ONB-032 — Empty-repo prompt**
  - Given: a git repo with no commits is entered.
  - When: the user clicks Add.
  - Then: a dialog offers "Make Initial Commit"; choosing it creates the commit and adds the repo; Cancel returns.

- **ONB-033 — Invalid path error**
  - Given: a nonexistent/inaccessible path is entered.
  - When: the user clicks Add.
  - Then: the dialog shows an error message with a Close button.

---

# ADDWS — Add-workspace page (create workspace)

- **ADDWS-001 — Page loading then form**
  - Given: the Add Workspace page is opening.
  - When: projects are being fetched.
  - Then: a centered spinner is shown; once loaded the creation form appears.

- **ADDWS-002 — Default project selection**
  - Given: projects exist.
  - When: the page loads.
  - Then: the most-recently-used project (or the first project if no MRU) is pre-selected in the repo selector.

- **ADDWS-003 — Workspace name input**
  - Given: the form is shown.
  - When: viewing it.
  - Then: a name input with placeholder "Untitled workspace (optional)" is shown and autofocused; typing shows the text.

- **ADDWS-004 — Empty / whitespace name defaults**
  - Given: the name is empty or only whitespace.
  - When: the user creates the workspace.
  - Then: it is created as "Untitled workspace".

- **ADDWS-005 — Name draft persists**
  - Given: the user typed a name and navigated away.
  - When: the user returns to the same draft.
  - Then: the previously typed name is restored.

- **ADDWS-006 — Repo selector dropdown**
  - Given: the repo selector is shown.
  - When: the user clicks it.
  - Then: a dropdown lists all projects plus an "Add new repository" entry.

- **ADDWS-007 — Select a different project**
  - Given: the repo dropdown is open.
  - When: the user clicks another project.
  - Then: the selection changes, the branch selector reloads, and any branch-name override clears.

- **ADDWS-008 — Add repository from selector**
  - Given: the repo dropdown is open.
  - When: the user clicks "Add new repository".
  - Then: the add-repository dialog opens; on success the new project is auto-selected.

- **ADDWS-009 — Branch selector loading**
  - Given: a project is selected and branch info is loading.
  - When: viewing the branch control.
  - Then: it shows a spinner and "Loading …" and is disabled.

- **ADDWS-010 — Branch selector dropdown & selection**
  - Given: branch info loaded.
  - When: the user opens the branch selector and clicks a branch.
  - Then: the dropdown lists recent branches with a search filter, and selecting one updates the source branch.

- **ADDWS-012 — Branch-name field**
  - Given: the create-workspace form is shown.
  - When: viewing the form.
  - Then: a required branch-name field for the worktree branch is shown.

- **ADDWS-013 — Branch-name auto-fill preview**
  - Given: the user typed a workspace name.
  - When: the form is shown.
  - Then: the branch-name field auto-fills a preview (with a "…" spinner while fetching) derived from the name, updating as the name changes.

- **ADDWS-014 — Manual branch-name override & reset**
  - Given: the branch-name field has an auto-filled preview.
  - When: the user types into it.
  - Then: the manual value takes over, auto-fill stops, and a reset link appears; clicking reset restores the preview.

- **ADDWS-015 — Branch-name collision error**
  - Given: a branch name is entered that already exists in the repo.
  - When: the collision check completes.
  - Then: a red message "Branch '{name}' already exists" appears below the field and clears when the user edits the name.

- **ADDWS-016 — Agent-type selector options**
  - Given: the form is shown.
  - When: the user opens the agent-type selector.
  - Then: it lists a plain Terminal plus the registered terminal agents (labelled by their display name, e.g. the bundled Claude registration); re-opening rescans for newly registered agents.

- **ADDWS-017 — Select agent type & MRU**
  - Given: the agent-type dropdown is open.
  - When: the user selects a type.
  - Then: the button shows the new type; the selection is remembered as the default for next time. A previously-selected registered agent that is no longer available falls back to a still-available type (Terminal).

- **ADDWS-020 — Create button gating & tooltips**
  - Given: the form is shown.
  - When: required fields are incomplete (e.g., Worktree branch name empty or still loading) or creation is in progress.
  - Then: the Create button is disabled with an explanatory tooltip ("Waiting for branch name…", "Agent is being created…"); when ready it is enabled with tooltip "Cmd/Ctrl+↵ to create workspace".

- **ADDWS-021 — Create the workspace**
  - Given: all fields are valid.
  - When: the user clicks "Create workspace" or presses `Cmd+Enter`.
  - Then: the workspace and its first agent are created and the user is navigated into the new workspace/agent tab.

- **ADDWS-022 — Keyboard focus into form**
  - Given: the page loads with nothing focused.
  - When: the user presses ArrowDown/ArrowUp.
  - Then: focus moves to the workspace-name input.

- **ADDWS-023 — Create error: branch exists**
  - Given: the user submits with a branch name that already exists.
  - When: the request returns a conflict.
  - Then: an error toast "Branch '{name}' already exists" appears and the form stays open for editing.

- **ADDWS-024 — Create error: generic failure**
  - Given: the user submits the form.
  - When: workspace or agent creation fails.
  - Then: an error toast titled "Failed to create workspace" with the failure details is shown.

---

# ADDREPO — Add-repository dialog & path autocomplete

- **ADDREPO-001 — Open add-repo dialog**
  - Given: the repo selector dropdown is open (or another add-repo entry point).
  - When: the user clicks "Add new repository".
  - Then: a modal opens with a path input (focused) and, on desktop, an "Or browse for a folder" link.

- **ADDREPO-002 — Cancel dialog**
  - Given: the dialog is open and not validating.
  - When: the user clicks Cancel / Escape / clicks the overlay.
  - Then: the dialog closes with no changes.

- **ADDREPO-003 — Prevent close during validation**
  - Given: validation is in progress.
  - When: the user tries to close the dialog.
  - Then: it stays open.

- **ADDREPO-004 — Add valid repo**
  - Given: a valid path is entered.
  - When: the user clicks "Add new repository".
  - Then: on success the dialog closes and the new repo is selected in the dropdown.

- **ADDREPO-005 — Dialog resets on reopen**
  - Given: the user previously typed a path and closed the dialog.
  - When: the dialog is reopened.
  - Then: the path input is empty.

- **ADDREPO-006 — Path autocomplete dropdown**
  - Given: a path input.
  - When: the user types a path containing "/" or starting with "~".
  - Then: after a short debounce a spinner shows, then a list of matching directories appears (or "No matching directories").

- **ADDREPO-007 — Navigate directories in autocomplete**
  - Given: the autocomplete list is shown.
  - When: the user clicks a directory.
  - Then: the path gains a trailing "/" and the next level of directories is fetched.

- **ADDREPO-008 — Autocomplete keyboard hints & submit**
  - Given: the autocomplete dropdown has items.
  - When: viewing the footer.
  - Then: hints "Esc: close", "↵: open", "{Meta}↵: add" are shown; pressing Enter with the dropdown closed (or `Cmd+Enter` anytime) submits the trimmed path.

---

# WS — Workspace shell (banner, PR, agent tabs, terminal agent, peek, layout)

## PR button

- **WS-022 — Checking PR status**
  - Given: a workspace with a branch.
  - When: PR status is loading.
  - Then: a spinner with "Checking PR..." is shown.

- **WS-023 — Create PR**
  - Given: no PR exists for the branch.
  - When: the user clicks "Create PR".
  - Then: a default PR-creation prompt (including the target branch) is sent to the agent.

- **WS-024 — Edit PR prompt before creating**
  - Given: the Create PR button is shown.
  - When: the user opens its chevron menu and clicks "Edit prompt…".
  - Then: a dialog opens to edit the prompt; Save updates it and closes.

- **WS-025 — Open PR display**
  - Given: an open PR exists.
  - When: viewing the button.
  - Then: it shows "PR #N" with pipeline and review status dots.

- **WS-026 — Open PR in browser**
  - Given: an open PR button is shown.
  - When: the user clicks the PR number.
  - Then: the PR opens in the browser.

- **WS-027 — PR detail dropdown**
  - Given: an open PR button is shown.
  - When: the user clicks the chevron.
  - Then: a popover shows PR title/link, checks/pipeline status, approvals with reviewer names, and unresolved comments.

- **WS-028 — CI babysitter toggle in PR dropdown**
  - Given: CI babysitter is enabled and the PR dropdown is open.
  - When: the user toggles the babysitter switch.
  - Then: it pauses/resumes and the status text updates.

- **WS-029 — Merged/closed PR**
  - Given: the PR was merged or closed.
  - When: viewing the button.
  - Then: it shows a merge icon with "PR #N merged"/"closed"; clicking opens it in the browser.

- **WS-030 — PR pipeline & review dot tooltips**
  - Given: an open PR with pipeline/review status.
  - When: the user hovers the dots.
  - Then: tooltips show "Pipeline running/passed/failed/No pipeline" and "Approved/Review pending/No reviewers".

- **WS-031 — Assign PR (target mismatch)**
  - Given: a PR exists for a different target than the workspace's.
  - When: viewing the button.
  - Then: an "Assign PR" button is shown; opening it offers "Create PR → {target}" and "switch target to {target}".

- **WS-032 — PR error states**
  - Given: PR status checking failed.
  - When: viewing the button.
  - Then: an error button with a warning triangle (actionable) or info icon (non-actionable) is shown; opening it shows a popover with a title, description, optional details, and an optional copyable remediation command (copy icon turns to a checkmark briefly).

## Target branch & repo segment

- **WS-033 — Target-branch selector**
  - Given: a workspace with a target branch.
  - When: viewing the banner.
  - Then: the target branch name is shown; clicking it opens a dropdown of remote branches, and selecting one updates the target.

- **WS-034 — Target-branch PR mismatch warning**
  - Given: the workspace target differs from an existing PR's target.
  - When: viewing the selector.
  - Then: the branch is shown in a warning color; hovering shows "PR #N targets {branch} — retarget?"; selecting the matching branch updates the target.

- **WS-035 — Repo segment menu**
  - Given: the banner shows the repo name.
  - When: the user clicks the repo segment.
  - Then: a dropdown offers Open folder, Copy relative path, Copy path, and Open in installed apps (VS Code, etc.), each performing its labeled action; the chosen app is remembered.

## Banner & diff summary

- **WS-038 — Banner progressive collapse**
  - Given: the viewport narrows.
  - When: space becomes constrained.
  - Then: banner elements collapse lowest-priority first (diff summary → repo segment → PR button); the PR button is highest priority and collapses last.

- **WS-039 — Copy branch name from banner**
  - Given: the branch name is shown in the banner.
  - When: the user clicks it.
  - Then: it is copied and a "Copied!" tooltip appears briefly.

- **WS-040 — Diff summary button**
  - Given: the workspace has uncommitted changes.
  - When: viewing the banner.
  - Then: a "+X −Y · Z files" summary is shown (with a shimmer while loading); clicking it opens the file browser's Changes tab scoped to the target branch.

## Agent tabs

- **WS-041 — Agent tabs shown**
  - Given: a workspace with one or more agents.
  - When: viewing the workspace.
  - Then: a tab per agent is shown with its title and status dot.

- **WS-042 — Switch agents**
  - Given: multiple agent tabs.
  - When: the user clicks another agent tab (or presses the next/previous-agent keybinding).
  - Then: the view switches to that agent's terminal/state.

- **WS-043 — Agent status-dot tooltip**
  - Given: the workspace peek popover's agent list.
  - When: the user hovers an agent's status dot.
  - Then: a tooltip shows the status label and time since last activity / creation. (The agent-tab status dot reflects the same state but carries no tooltip.)

- **WS-044 — Create a new agent**
  - Given: agent tabs are shown.
  - When: the user clicks the "+" button.
  - Then: a new agent of the default type is created and shown.

- **WS-045 — Choose agent type when creating**
  - Given: the "+" chevron menu.
  - When: the user opens it.
  - Then: it lists a plain Terminal and the registered terminal agents (e.g. "Claude CLI"); selecting one creates that type and remembers it as the default.

- **WS-046 — Rename an agent (double-click)**
  - Given: an agent tab.
  - When: the user double-clicks the title, types a name, and presses Enter.
  - Then: the agent is renamed; Escape cancels.

- **WS-047 — Agent context menu**
  - Given: an agent tab.
  - When: the user right-clicks it.
  - Then: a menu offers Rename, Mark unread, Copy agent name, a Diagnostics submenu (Debug View toggle; Copy agent id; Copy claude session id; Copy Sculptor transcript file path — disabled when unavailable), and Delete (last).

- **WS-048 — Delete an agent**
  - Given: an agent context menu (or close button) is used.
  - When: the user deletes and confirms.
  - Then: the agent is removed and navigation moves to the next agent (or a fresh one if it was the last).

- **WS-049 — Mark agent unread**
  - Given: a read agent.
  - When: the user chooses "Mark unread".
  - Then: the agent's status indicator changes to unread.

- **WS-050 — Reorder agent tabs**
  - Given: multiple agent tabs.
  - When: the user drags a tab to a new position.
  - Then: the order updates.

## Terminal agent panel

- **WS-051 — Terminal agent shows a terminal**
  - Given: an agent in a workspace.
  - When: viewing the agent.
  - Then: a full-pane terminal is shown as the agent surface, streaming output.

- **WS-052 — Terminal persists across agent switches**
  - Given: a terminal agent is active.
  - When: the user switches away and back.
  - Then: the terminal reconnects and previous scrollback is restored.

## Workspace peek

- **WS-061 — Peek popover on hover**
  - Given: workspace tabs are shown.
  - When: the user hovers a workspace tab for a moment.
  - Then: a peek popover appears showing status, agent list, PR info, branch, and diff stats.

- **WS-062 — Smooth peek transitions**
  - Given: a peek popover is open.
  - When: the user moves between tabs within the grace period.
  - Then: the popover content swaps instantly; leaving all tabs closes it after a short delay.

- **WS-063 — Expand more agents in peek**
  - Given: a workspace with more than 6 agents (at least two beyond the first five).
  - When: viewing its peek popover.
  - Then: only 5 agents show with a "+N more agents" button that reveals the rest.

- **WS-064 — Navigate from peek**
  - Given: the peek popover is open.
  - When: the user clicks an agent row or the header.
  - Then: the popover closes and the workspace/agent opens; clicking the branch copies it ("Copied!").

## Bottom bar & layout

- **WS-065 — Panel toggle buttons**
  - Given: the user is on a workspace page.
  - When: viewing the bottom bar.
  - Then: toggle buttons for the left, bottom, and right panels are shown.

- **WS-066 — Toggle a panel from the bottom bar**
  - Given: a panel has content.
  - When: the user clicks its toggle button.
  - Then: the panel hides/shows and the button's active state updates.

- **WS-067 — Empty-panel toggle disabled**
  - Given: a panel has no content.
  - When: viewing/hovering its toggle button.
  - Then: the button is disabled with a "Panel is empty" tooltip and does nothing on click.

- **WS-068 — Panel toggle tooltips show keybinding**
  - Given: a panel toggle button.
  - When: the user hovers it.
  - Then: a tooltip shows the name and keybinding.

- **WS-069 — Diff split resize / collapse / expand**
  - Given: the diff panel is open beside the agent pane.
  - When: the user drags the divider.
  - Then: the panels resize; dragging past a threshold collapses the diff panel; an expand control toggles between maximizing the diff (collapsing the agent pane) and restoring the split.

## Setup config

- **WS-074 — Setup config prompt**
  - Given: a workspace with no setup command configured.
  - When: viewing the workspace, above the terminal agent surface.
  - Then: a prompt with a "Configure a workspace setup command" link is shown; clicking it opens settings to the repositories section.

---

# PANEL — Workspace side panels

## File browser

- **PANEL-001 — Browse / Changes / Commits tabs**
  - Given: the file browser panel.
  - When: the user clicks the Browse, Changes, or Commits tab.
  - Then: the corresponding view is shown; the Changes and Commits tabs show an inline count ("Changes N" / "Commits N") when there are changes/commits.

- **PANEL-003 — Toggle tree/flat view**
  - Given: a file list view.
  - When: the user clicks the tree/list toggle.
  - Then: the list switches between a nested tree and a flat list.

- **PANEL-004 — Collapse all folders**
  - Given: a tree with expanded folders.
  - When: the user clicks collapse-all.
  - Then: all folders collapse.

- **PANEL-005 — Refresh file tree**
  - Given: the file tree.
  - When: the user clicks refresh.
  - Then: the icon spins and the tree re-fetches.

- **PANEL-006 — File search**
  - Given: the Browse tab.
  - When: the user clicks the search icon and types.
  - Then: the header becomes a search input, the list filters in real time, ancestor folders of matches auto-expand, and "No matches" shows when empty; Escape/close exits search.

- **PANEL-007 — Expand/collapse folders**
  - Given: a folder in the tree.
  - When: the user clicks its chevron/row.
  - Then: it expands/collapses to show/hide children.

- **PANEL-008 — Open a file**
  - Given: a file in the tree/flat list.
  - When: the user clicks it.
  - Then: a diff view tab opens for that file.

- **PANEL-009 — Tree keyboard navigation**
  - Given: the tree is focused.
  - When: the user presses arrows / Enter.
  - Then: Up/Down move between visible rows, Right/Left expand/collapse folders, Enter opens the focused file.

- **PANEL-010 — File status & stats**
  - Given: files with git status.
  - When: shown in the tree.
  - Then: each shows a status letter (M/A/D/R) with a color, +added/−removed stats, a change-count badge on folders, an error badge on processing errors, and strike-through styling for deletions.

- **PANEL-011 — Focus highlight on agent file activity**
  - Given: the agent operates on a file.
  - When: the file appears in the tree.
  - Then: the tree scrolls to it, expands its ancestors, and highlights the row.

- **PANEL-012 — File context menu**
  - Given: a file/folder in the tree.
  - When: the user right-clicks it.
  - Then: a menu offers Open diff view, View file, Copy file path, Copy relative path, Open in default app, Open containing folder, and (folders) Expand all children / Collapse all children, plus Close tab / Close other tabs / Close all when a diff tab is open — each performing its labeled action.

- **PANEL-013 — Empty / loading file tree**
  - Given: no files / the tree is loading.
  - When: the Browse tab is shown.
  - Then: "No files yet" / animated skeleton rows are shown.

## Changes & commit

- **PANEL-014 — Diff scope picker**
  - Given: the Changes tab with a target branch.
  - When: the user picks "All" vs "Uncommitted".
  - Then: the list shows all changes vs target or only uncommitted changes, with counts per segment.

- **PANEL-015 — Discard a change**
  - Given: a changed file with a discard control.
  - When: the user clicks it and confirms in the dialog.
  - Then: the file reverts to HEAD and leaves the changes list; Cancel keeps it.

- **PANEL-016 — Commit button states**
  - Given: the Changes tab.
  - When: changes exist / none exist.
  - Then: "Commit N changes" is enabled / disabled accordingly.

- **PANEL-017 — Quick commit**
  - Given: the commit button is enabled.
  - When: the user clicks it.
  - Then: the default commit prompt is sent to the agent.

- **PANEL-018 — Edit commit prompt**
  - Given: the commit button.
  - When: the user right-clicks it and chooses "Edit prompt…", edits, and saves.
  - Then: the commit prompt updates and the dialog closes.

## History

- **PANEL-019 — History loading / empty / error**
  - Given: the Commits tab.
  - When: history is loading / absent / failed.
  - Then: "Loading history…" / "No history available" / an error message is shown.

- **PANEL-020 — Commit graph & entries**
  - Given: commits loaded.
  - When: the tab renders.
  - Then: a commit graph with dots/lines is shown; each entry shows the first line of the message, file count, +/− stats, relative time, and short hash.

- **PANEL-021 — Expand commit files**
  - Given: a commit entry.
  - When: the user clicks it.
  - Then: it expands to list the files in that commit (each with status and stats); clicking again collapses.

- **PANEL-022 — Commit hover popover & copy hash**
  - Given: a commit entry.
  - When: the user hovers it.
  - Then: a popover shows the full message, author, date, full hash with a copy button, and stats; clicking copy copies the hash with a "Copied" indicator.

- **PANEL-023 — Open a commit's file diff**
  - Given: a commit is expanded.
  - When: the user clicks a file.
  - Then: a diff tab opens comparing that file in the commit vs its parent.

- **PANEL-024 — Merge commits & terminus**
  - Given: a merge commit / the end of history.
  - When: rendered / expanded.
  - Then: a merge indicator allows expanding the second-parent branch chain; a terminus/fork-point indicator is shown at the bottom.

## Diff panel / viewer

- **PANEL-025 — Diff tabs**
  - Given: files opened in the diff panel.
  - When: the user opens/switches/closes tabs.
  - Then: each file opens in a tab, clicking switches, the X closes (activating MRU or adjacent per setting); right-click offers Close other / Close all; tabs can be reordered; labels show the filename (full path on hover).

- **PANEL-026 — Diff view controls**
  - Given: a diff is shown.
  - When: the user toggles split/unified, line-wrapping, find, or expand.
  - Then: the layout switches side-by-side/unified, wraps or scrolls long lines, opens an in-file search, or expands the diff to full width (hiding the file browser); a close control closes the panel.

- **PANEL-027 — Diff file header**
  - Given: a diff tab.
  - When: it renders.
  - Then: it shows the breadcrumb path, filename, +/− stats, and a three-dot menu with file operations.

- **PANEL-028 — Special file states**
  - Given: a renamed/deleted/binary file.
  - When: the diff renders.
  - Then: a rename banner (diff-style `--- a/{old}` / `+++ b/{new}` lines), a "This file was deleted" banner, or a "Binary file — cannot preview" message is shown.

- **PANEL-029 — Large-diff truncation**
  - Given: a diff exceeding the line threshold.
  - When: it renders.
  - Then: a truncated diff with a "Show full diff" button is shown; clicking renders the full diff.

- **PANEL-030 — In-file search**
  - Given: a diff is shown.
  - When: the user opens find and types.
  - Then: matches are highlighted with an "X of Y" counter; Enter/Shift+Enter (or arrows) navigate; Escape/close closes it.

- **PANEL-031 — File view (full content)**
  - Given: a file opened via "View file".
  - When: the tab renders.
  - Then: the full file content is shown read-only with syntax highlighting (not a diff).

## Terminal panel

- **PANEL-034 — Terminal tabs**
  - Given: the terminal panel.
  - When: the user clicks + / switches / double-clicks to rename / closes a tab.
  - Then: a new "Terminal N" is created / the selected terminal is shown / an inline rename input appears (Enter confirms, Escape cancels) / the tab closes (closing the last one creates a fresh replacement); right-click offers "Close others"; tabs can be reordered.

- **PANEL-035 — Terminal interaction**
  - Given: an active terminal.
  - When: the user types a command.
  - Then: input goes to the shell and output is displayed; scrollback is available.

- **PANEL-036 — Terminal unread badge**
  - Given: output arrives in a non-active terminal tab.
  - When: it occurs.
  - Then: a pulsing unread dot appears on that tab, cleared when switching to it.

- **PANEL-037 — Terminal starting state**
  - Given: a terminal is starting.
  - When: the panel mounts.
  - Then: a "Starting terminal..." message is shown.

## Actions panel

- **PANEL-047 — Action groups**
  - Given: actions with groups.
  - When: the panel renders.
  - Then: collapsible group headers (with count badges when collapsed) are shown, the built-in "Sculptor" group first, and ungrouped actions at the bottom.

- **PANEL-048 — Trigger an action**
  - Given: an action chip.
  - When: the user clicks it.
  - Then: an auto-submit action types its prompt into the terminal and presses Enter; a draft action types its prompt into the terminal without pressing Enter (the user edits/sends); chips are disabled while the agent is running.

- **PANEL-049 — Queue an action**
  - Given: the agent is running and an action chip's context menu.
  - When: the user chooses "Queue message".
  - Then: the action prompt is delivered to the terminal; the "Queue message" item appears only while the agent is running (there is no separate message queue).

- **PANEL-050 — Add / edit / delete an action**
  - Given: the actions panel.
  - When: the user adds (+), edits, or deletes an action via the menu.
  - Then: an action dialog opens for add/edit (Save persists), and delete shows a confirmation; built-in actions offer no edit/delete.

- **PANEL-051 — Group management**
  - Given: the actions panel.
  - When: the user adds a group, renames a group inline, or deletes a custom group.
  - Then: a group is created (Enter confirms, Escape cancels), renamed (Enter/blur confirms), or deleted via a confirmation dialog.

- **PANEL-052 — Reorder actions & groups by drag**
  - Given: custom actions/groups.
  - When: the user drags an action or group.
  - Then: a drop indicator appears and the order updates on drop; actions can be moved between groups; built-in items are not draggable.

## Panel state persistence

- **PANEL-056 — Panel state persists**
  - Given: the user has set folder-expansion, scroll position, active tab, view mode, diff view type, and line-wrapping.
  - When: switching tabs/files and returning.
  - Then: each of these states is restored.

---

# CMDP — Command palette

## Opening, closing, search

- **CMDP-001 — Open the palette**
  - Given: the app is open on any page.
  - When: the user presses `Cmd+K` (or clicks the command icon).
  - Then: the palette opens with the input focused, commands grouped (Workspaces → Navigation → Theme & Layout → Terminal → Help), and the first row selected.

- **CMDP-002 — Open directly to the workspace switcher**
  - Given: the app is open.
  - When: the user presses `Cmd+P`.
  - Then: the palette opens on the "Go to workspace" sub-page with placeholder "Find a workspace…".

- **CMDP-003 — Toggle closed**
  - Given: the palette is open.
  - When: the user presses `Cmd+K` again.
  - Then: the palette closes without running a command.

- **CMDP-004 — Filter commands**
  - Given: the palette is open at root.
  - When: the user types a query (e.g., "theme").
  - Then: matching commands are shown (fuzzy/keyword, case-insensitive), non-matching rows and empty groups hide, and groups reorder by best match.

- **CMDP-005 — No matches**
  - Given: the palette is open.
  - When: the user types a query with no matches.
  - Then: an empty state "No matches for '{query}'" is shown.

- **CMDP-006 — Clear search restores all**
  - Given: the palette has a query.
  - When: the user clears the input.
  - Then: all commands reappear in group order with the first row selected.

- **CMDP-007 — Escape behavior**
  - Given: the palette is open.
  - When: the user presses Escape.
  - Then: a non-empty search clears first; an empty search at root closes the palette; on a sub-page it returns to root without closing.

- **CMDP-008 — Click outside closes**
  - Given: the palette is open with no pending command.
  - When: the user clicks the overlay.
  - Then: the palette closes.

## Keyboard navigation & pages

- **CMDP-009 — Arrow navigation with wrap**
  - Given: results are showing.
  - When: the user presses Down/Up.
  - Then: the selection moves and scrolls into view, wrapping at the ends.

- **CMDP-010 — Run a command**
  - Given: a command is selected.
  - When: the user presses Enter (or clicks it).
  - Then: it runs and the palette closes (unless the command keeps the palette open).

- **CMDP-011 — Run and keep open**
  - Given: a command is selected.
  - When: the user presses `Cmd+Enter`.
  - Then: it runs, the palette stays open, and focus returns to the input.

- **CMDP-012 — Enter / exit a sub-page**
  - Given: a page-opener command is selected (chevron shown).
  - When: the user presses Tab / ArrowRight (caret at input end) to enter, or Shift+Tab / ArrowLeft (caret at start) / Backspace (empty) to exit.
  - Then: the sub-page opens with a breadcrumb and updated placeholder / it returns to root; the search clears on navigation.

- **CMDP-013 — Breadcrumb on sub-pages**
  - Given: a sub-page is open.
  - When: viewing the header.
  - Then: a breadcrumb shows the page title with an X to return to root (no breadcrumb at root).

- **CMDP-014 — Disabled rows & tooltips**
  - Given: a command is unavailable in the current context.
  - When: viewing/hovering the row.
  - Then: it is greyed out and shows a reason (as a subtitle or hover tooltip), e.g., "Only one agent in this workspace", "No uncommitted changes".

- **CMDP-015 — Shortcut hints & chevrons**
  - Given: rows with a keybinding or sub-page.
  - When: viewing them.
  - Then: a key-badge shortcut and/or a right chevron appears in the trailing area (group label shown during search when no shortcut).

- **CMDP-016 — Async command spinner & close-block**
  - Given: a command performs async work.
  - When: it runs.
  - Then: the row shows a spinner; the palette refuses to close until it completes (or times out after ~30s).

## Built-in commands

- **CMDP-017 — Navigation commands**
  - Given: the palette is open.
  - When: the user runs Open home / Open settings / New workspace / New agent.
  - Then: the app navigates home / to settings / to new-workspace / creates and opens a new agent (New agent is disabled off a workspace).

- **CMDP-018 — Theme commands**
  - Given: the palette is open.
  - When: the user runs "Toggle theme" or opens "Switch theme…" and picks Light/Dark/System.
  - Then: the theme flips or is set accordingly.

- **CMDP-019 — Panel commands**
  - Given: the palette is open on a workspace.
  - When: the user opens "Toggle panel visibility…" and runs a panel toggle (Files, Actions, Terminal, …).
  - Then: the corresponding panel visibly toggles and the palette closes.

- **CMDP-021 — Terminal & help commands**
  - Given: the palette is open.
  - When: the user runs Clear terminal / Show keyboard shortcuts.
  - Then: the terminal clears (hidden without a terminal panel) / the shortcuts dialog opens.

## Workspace & agent commands

- **CMDP-022 — Go to workspace switcher**
  - Given: 2+ workspaces.
  - When: the user opens "Go to workspace…" and selects one.
  - Then: a list with status dots is shown (the current workspace disabled as "Current workspace"); selecting another navigates to it.

- **CMDP-023 — Workspace tab navigation**
  - Given: 2+ workspace tabs.
  - When: the user runs Next/Previous workspace tab.
  - Then: focus moves to the next/previous tab.

- **CMDP-024 — Workspace actions sub-page**
  - Given: a workspace.
  - When: the user opens "Workspace actions…" and runs Commit changes / Create PR / Open PR / Rename / Close / Close others / Close all / Delete.
  - Then: each performs its action (Commit disabled without changes; Open PR disabled without an open PR; Delete and others as labeled).

- **CMDP-025 — Open-in sub-page**
  - Given: external apps are available.
  - When: the user opens "Open in…" and selects Finder / VS Code / Terminal / etc.
  - Then: the repo opens in the chosen app (the preferred app ranks first).

- **CMDP-026 — Go to agent switcher**
  - Given: 2+ agents in a workspace.
  - When: the user opens "Go to agent…" and selects one.
  - Then: a list is shown (current agent disabled); selecting another navigates to it; the opener is disabled with only one agent.

- **CMDP-027 — Agent actions sub-page**
  - Given: an active agent.
  - When: the user opens "Agent actions…" and runs Rename / Mark unread / Delete.
  - Then: the rename dialog opens / the agent is marked unread / a delete confirmation appears.

- **CMDP-028 — Settings sub-page**
  - Given: the palette is open.
  - When: the user opens "Go to settings…" and selects a section (General, Keybindings, Repositories, Git, CI, File browser, Environment variables, Actions).
  - Then: the app navigates to that settings section.

- **CMDP-029 — Pointer & open-time behavior**
  - Given: the palette opens while the cursor is over a row.
  - When: the first pointer move occurs / the user later hovers a row.
  - Then: the first move is ignored (keyboard selection stays); subsequent hovers select the hovered row.

- **CMDP-030 — List resets on open & on search change**
  - Given: the palette opens or the query changes.
  - When: it happens.
  - Then: the list scrolls to the top and the first row is selected.

- **CMDP-031 — Long titles truncate**
  - Given: an agent/workspace with a very long title.
  - When: listed in the palette.
  - Then: the title truncates with "…".

---

# SET — Settings page

## Navigation & common behaviors

- **SET-001 — Section navigation**
  - Given: the settings page.
  - When: the user clicks a sidebar item (or selects from the mobile dropdown).
  - Then: the active section changes and its content is shown; the sections are General, Keybindings, Repositories, Git, CI, File browser, Environment variables, and Actions.

- **SET-002 — Deep-link to a section**
  - Given: a URL with a section parameter.
  - When: the settings page loads.
  - Then: it opens directly to that section.

- **SET-003 — Active section remembered**
  - Given: the user viewed a section.
  - When: they reopen settings.
  - Then: the last-viewed section is shown.

- **SET-004 — Save feedback toast**
  - Given: the user changes a setting.
  - When: it saves successfully / fails.
  - Then: a "Setting updated" success toast / a "Failed to update setting" error toast appears.

## General

- **SET-005 — Theme appearance**
  - Given: the General section.
  - When: the user picks Light / Dark / System.
  - Then: the app appearance changes immediately.

## Keybindings

- **SET-008 — Search keybindings**
  - Given: the Keybindings section.
  - When: the user types in the search field.
  - Then: the list filters by name/description.

- **SET-009 — Assign a hotkey**
  - Given: a keybinding row.
  - When: the user clicks "Click to set" and presses a combination.
  - Then: it shows "Press keys… Esc to cancel" then records and displays the formatted hotkey.

- **SET-010 — Conflict detection**
  - Given: the user assigns a hotkey already in use.
  - When: the conflict is detected.
  - Then: a warning names the conflicting action with Reassign / Cancel options.

- **SET-011 — Clear / reset keybindings**
  - Given: a keybinding (or all).
  - When: the user clicks the X on a chip / "Reset all to defaults".
  - Then: that binding / all bindings revert to default.

## Repositories

- **SET-020 — Add / list repositories**
  - Given: the Repositories section.
  - When: the user clicks "Add new repository".
  - Then: the add-repo dialog opens; the list shows each repo's name, path, agent count, and an accessibility warning when the path is missing.

- **SET-021 — Configure a repository**
  - Given: a repo row.
  - When: the user clicks Configure and edits the setup command or branch-naming pattern.
  - Then: the section expands; values save on blur, with "Using default"/"Reset to default" affordances for the setup command.

- **SET-022 — Remove a repository**
  - Given: a repo row.
  - When: the user clicks "Remove repo & agents" and confirms.
  - Then: a confirmation dialog (showing the agent count) deletes the repo on confirm (with a success/error toast).

## Git

- **SET-023 — Git settings**
  - Given: the Git section.
  - When: the user edits the PR-creation prompt, toggles PR status polling, sets poll interval (10–300s) and closed-workspace multiplier (1–120×), or sets the default target branch.
  - Then: each saves with a toast; polling fields disable when polling is off; values are validated to their ranges; the PR prompt has a reset-to-default.

- **SET-024 — Global defaults**
  - Given: the Git section.
  - When: the user edits the default branch-naming pattern or branch-deletion policy (Never / Delete if safe / Always).
  - Then: each saves with a toast.

## CI babysitter

- **SET-025 — CI babysitter settings**
  - Given: the CI section.
  - When: the user toggles the babysitter, selects the babysitter agent (most-recently-used or a specific registered harness), sets the retry cap (1–10), or edits the pipeline-failed / merge-conflict prompts.
  - Then: each saves with a toast; the dependent fields disable when the babysitter is off; prompts have reset-to-default.

## File browser

- **SET-026 — File-browser settings**
  - Given: the File browser section.
  - When: the user sets the default split ratio (20–80%), tab-close behavior, line-wrapping, default diff view, or the commit prompt.
  - Then: each saves with a toast (commit prompt has reset-to-default).

## Environment variables

- **SET-027 — Env-var settings**
  - Given: the Environment variables section.
  - When: the user toggles "override existing variables" or clicks refresh.
  - Then: the toggle saves with a toast; the list of loaded variables (global and repo-specific) refreshes.

## Actions

- **SET-031 — Manage actions**
  - Given: the Actions section.
  - When: the user adds an action/group, edits, deletes, exports (downloads JSON), or imports (file picker).
  - Then: dialogs handle add/edit/delete with confirmations; export downloads "sculptor-actions.json" (disabled when empty); import validates and merges with a count toast.

- **SET-032 — Action dialog fields**
  - Given: the action dialog (add/edit).
  - When: the user fills Name, Prompt, Group, and the Auto-submit toggle and clicks Save.
  - Then: Save is disabled until valid; `Cmd+Enter` submits; the action is created/updated.

- **SET-033 — Reorder & regroup actions**
  - Given: custom actions/groups.
  - When: the user drags to reorder or rename a group inline.
  - Then: the order updates and the group renames with a success toast.

---

# ACT — Actions feature components

- **ACT-001 — Action chip appearance & trigger**
  - Given: an action chip.
  - When: viewing/clicking it.
  - Then: it shows a play icon (auto-submit) or text-cursor icon (draft), a tooltip with the prompt on hover, and clicking types the prompt into the terminal (auto-submit presses Enter, draft leaves it for the user to send); disabled chips ignore clicks.

- **ACT-002 — Action context menu**
  - Given: an action chip.
  - When: the user right-clicks it.
  - Then: a menu offers "Queue message" (only while the agent runs), "Edit action", a "Move to group…" submenu (current group disabled), and "Delete action" (red).

- **ACT-003 — Action dialog validation & submit**
  - Given: the action dialog (Add/Edit).
  - When: the user fills Name and Prompt, optionally picks/creates a group, toggles Auto-submit, and saves.
  - Then: Save is disabled until Name and Prompt are non-empty; `Cmd+Enter` submits when valid; fields pre-populate when editing.

- **ACT-004 — Delete action / group confirmations**
  - Given: a delete action/group request.
  - When: the dialog appears.
  - Then: it names the target (and, for a group, lists its actions and count); confirming shows a spinner and disables buttons while deleting.

- **ACT-005 — Group header rename & collapse**
  - Given: a custom group header.
  - When: the user uses its context menu to rename (inline; Enter/blur confirms, Escape cancels) or clicks the header to collapse/expand.
  - Then: the name updates / the group collapses (chevron flips, count badge shows when collapsed); renaming does not toggle collapse.

- **ACT-006 — Drag to reorder / regroup**
  - Given: custom actions/groups (built-ins are not draggable).
  - When: the user drags an action or group.
  - Then: drop indicators show before/after positions; dropping into a group moves the action there; dropping outside removes it from the group.

---

# DEV — Dev/debug panels & markdown-diff anchors

- **DEV-001 — TanStack devtools panel modes**
  - Given: the devtools panel is enabled (via the version popover).
  - When: it is shown.
  - Then: a floating or docked-bottom panel appears with a header offering Dock/Float and Close; the floating panel can be dragged and resized within the viewport; the docked panel can be resized from its top edge and pushes app content up; closing hides it.

- **DEV-002 — Markdown external links**
  - Given: a markdown link with an external protocol.
  - When: the user clicks it.
  - Then: it opens in the OS browser and shows an external-link icon.

- **DEV-003 — Markdown fragment links**
  - Given: a `#anchor` markdown link.
  - When: the user clicks it.
  - Then: navigation is prevented; a dashed-underline style and a tooltip ("In-page anchor links aren't supported yet") are shown.

- **DEV-004 — Markdown relative/unsupported links**
  - Given: a relative or unsupported-scheme markdown link.
  - When: the user clicks it.
  - Then: navigation is prevented; a broken-link icon and a tooltip ("Linked-file navigation isn't supported yet") are shown.

---

## Coverage notes

- Some behaviors are gated by capabilities and only appear when enabled: the CI babysitter
  and the dev/devtools panels. Tests should set the relevant state (or assert the gated UI
  is absent when off).
- The home-page rows and the workspace banner reuse the same PR button component, so
  the WS-PR scenarios (WS-022…WS-032) also describe the home-row PR behavior (HOME-020).
- Status dots (running / waiting / error / ready / read / unread, plus the two-dot mixed
  state) use one shared component across tab strips, home rows, agent tabs, peek popovers,
  and the command palette; verify the same color/animation mapping in each surface.
