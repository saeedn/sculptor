# Sculptor — Product Specification

## 1. Overview

Sculptor is a desktop app for running coding agents in parallel — each in its own isolated copy of
your repository. Instead of handing your working tree to a single agent and waiting, you spin up as
many **workspaces** as you have tasks, point an **agent** at each, and let them work at the same
time while you review, steer, or start more.

The shape of the product is a short loop. You **connect a repo**, **create a workspace** (an
isolated copy of your code), and run an **agent** in it — a terminal session where a coding tool
like Claude Code does the work. You watch it work in its terminal and the changes it makes appear
live, and you step in whenever you want. When it's done you **review the changes**, commit them, and
open a pull request, all without leaving the workspace. To explore a different task you open another
workspace; to collaborate on the same one you add another agent.

Sculptor runs entirely on your machine and offers the same capabilities two ways: a **desktop GUI**
for interactive work, and the **`sculpt` CLI** for driving the very same workspaces and agents
headlessly from a terminal, a script, or CI. On top of the basic loop it bundles a library of
**skills** — reusable, multi-step workflows like spec-then-build or test-driven bug fixing — that
run as their own agents.

Sculptor is an experimental research preview: it is under active development, it will have rough
edges, and it can change quickly.

## 2. Problem Statement

Coding agents are useful but awkward to run more than one at a time. Point an agent straight at your
working tree and it competes with you for the same files; run several and they trample each other
and your in-progress work. Keeping each agent's work on its own branch, reviewing what it did, and
getting it safely into a pull request are all manual. And the moment you want to automate any of
this — fan out a fleet of agents, or wire one into CI — a GUI-only tool runs out of room.

Sculptor exists to make running coding agents **parallel, isolated, reviewable, and steerable** the
default. It gives each agent an isolated copy of your repository so it can edit and run freely
without disturbing you; it makes the agent's changes first-class to review and commit; it keeps you
in control of what reaches the outside world; and it exposes everything through both a GUI and a
scriptable CLI. What it is *not* responsible for is being your editor, hosting your code, or serving
the models — it orchestrates agents over your local repositories.

## 3. Goals and Non-Goals

**Goals**
- Run multiple coding agents concurrently, each isolated from your checkout and from each other.
- Make agent work reviewable and safe to land: changes, diffs, commits, and PRs are first-class,
  and nothing reaches a remote without your action.
- Keep you in control of each agent: interrupt, steer, answer its questions, and recover your work
  across restarts and crashes.
- Offer the same capabilities headlessly via the `sculpt` CLI as in the GUI, so work can be scripted.
- Bundle reusable, multi-step workflows (skills) that take work from idea to shipped code.
- Run entirely on your machine, keeping your code private.

**Non-Goals**
- Not a general IDE or editor; it complements your editor rather than replacing it.
- Not a hosted, multi-tenant cloud service; it runs locally on your machine.
- Not a model provider; it orchestrates a coding-agent CLI (Claude, via the terminal), it doesn't
  serve models.
- Not a code host; your repositories and history stay yours.
- Not a finished, stable product — it is an experimental research preview.

## 4. Scenarios

A set of realistic, named end-to-end narratives — each a short story of a stereotypical user
accomplishing a real job.

**S1 — Fix a bug, test-first, without breaking stride.** Dana hits a rounding bug in the checkout
flow. She opens a workspace on a fresh branch off `main` and, rather than hand-write a prompt,
invokes **`/sculptor-workflow:fix-bug`** with "checkout total is off by a cent on multi-item carts."
The skill runs as its own agent and drives a **test-driven** fix: it first reproduces the bug with a
*failing* test, then changes the code until that test — and the rest of the suite — passes, narrating
each step as it goes. Dana goes back to her own editor while it works. A few minutes later she opens
the workspace's **Changes**, sees the new regression test sitting alongside the one-line fix, reads
the diff, commits, and opens a pull request — never having stashed or branched in her own checkout.
(For a bug she's already confident about, she could instead invoke
`/sculptor-workflow:fix-bug --autonomous` and let it run end-to-end and open the PR itself.)

**S2 — Compare two approaches in parallel.** Unsure which approach is better, Priya creates two
workspaces from the same starting branch and gives each agent the same task with a different steer
("smallest possible change" vs. "refactor for clarity"). The two agents run at the same time in
their separate copies; she watches both from their tabs, compares the resulting diffs, and keeps the
one she prefers — discarding the other workspace. (Two *workspaces*, not two agents in one: agents
sharing a workspace would edit the same files.)

**S3 — Drive a feature from spec to shipped.** Sam has a larger feature. He invokes
**`/sculptor-workflow:spec`**, which spawns a "Spec" agent that interviews him and writes an
implementation spec he watches take shape in the diff viewer. When it's right, he hands off down the
pipeline — each stage its own dedicated agent (renamed **Spec → Architect → Plan → Build**) that
produces a durable artifact the next stage reads: the architecture document, then a folder of
self-contained task files, then the built code committed task by task. (For a UI-heavy feature he'd
slot in **mock** near the start to generate interactive HTML mockups to react to first.) The pipeline
ends with **Review**: a final agent that checks the diff against the original spec, re-runs the tests,
and writes up its findings in `review.md` for Sam to act on. Each stage offers to hand off to the
next, so Sam can stop after any one, inspect its artifact, and resume the pipeline whenever he likes.

**S4 — Automate Sculptor from the terminal.** Alex lives at the keyboard, so he drives Sculptor with
the **`sculpt` CLI**: `sculpt run "regenerate the API client and fix any type errors" --follow`
creates a workspace *and* an agent in one command and streams the result; a wrapper script reads the
agent's status as JSON and, when it finishes, reads back the changes. Because both surfaces share one
**local** backend, that same workspace is sitting in the desktop app if Alex wants to take over
interactively — and conversely a workspace he started in the app is drivable from `sculpt`. This is
how he wires a routine repo chore into a local `Makefile` target or a personal cron job, and how he
fans several agents out from a single script. (Sculptor is a server running on *your* machine, so
`sculpt` automates the Sculptor you already have open — not a fresh one conjured inside an ephemeral
remote CI runner, which has no local backend or checkout to drive.)

**S5 — Run a fleet; let the dots route your attention.** Maya is mid-sprint with a dozen things in
flight at once. Three large features are each moving through the workflow skills in their own
workspaces; another seven or eight smaller bugs are each handed to a `fix-bug` agent in a workspace
of its own. She isn't watching any single one — she reads the **status dots** across the workspace
tabs as a dashboard of where her attention is owed: a *ready* dot means an agent has finished and
wants review, a *waiting* dot means one is blocked on a question or plan approval, an *error* dot
means one needs a human. She hovers a tab to **peek** at that workspace's agents, branch, PR status,
and diff stats without leaving the agent she's in, and uses **Cmd+P / Cmd+K** to jump straight to
whichever workspace is asking for her. She approves a plan in its terminal, reviews and commits a finished bug
fix there, unsticks a confused build agent — then drops back into her own work. The win isn't that
any single agent is faster; it's that Sculptor lets her keep ten-plus autonomous agents productive at
once by telling her exactly **where and when** to look, so nothing stalls silently and nothing
demands constant supervision.

**S6 — Ship a batch overnight with self-healing CI.** At the end of the day Raj clears a backlog of
well-understood bugs by firing off **`/sculptor-workflow:fix-bug --autonomous`** in a workspace each:
every one reproduces, fixes, verifies, and opens a pull request with no further input from him. He
turns on the **CI babysitter** so that when a PR's pipeline fails, Sculptor automatically asks an
agent to read the failure, fix it, and push — up to a configured retry cap — and to resolve simple
merge conflicts the same way. He leaves his machine running and steps away for the night (Sculptor is
a local server, so the agents and babysitter keep working only while his machine is on). By morning
most of the PRs are green and ready to merge; the handful the babysitter couldn't rescue are flagged
with an **error** or **waiting** dot for Raj to take over by hand. He spends the morning reviewing
diffs and merging — not babysitting pipelines.

The exhaustive, UI-level Given/When/Then list lives in `scenarios.md` (and `scenario_coverage.md`
maps those to tests); this section holds only the rich narratives.

## 5. System Overview & Components

This section is the **engineering view** — the one place implementation is described. Product
behavior is in §7/§9; the development and quality substrate is in §10.

Sculptor runs entirely on your machine as a small set of cooperating pieces arranged around a
**single local backend server**. Both product surfaces — the **Electron desktop GUI** and the
**`sculpt` CLI** — are clients of that one server, talking to it over HTTP for actions and
subscribing to a **live update stream** for state. There is no separate "CLI backend" and "GUI
backend": a **Workspace** or **Agent** created from the terminal appears in the desktop app and vice
versa, because both surfaces drive the same service and read the same persisted state. The backend
owns the domain — **Projects (Repos)**, **Workspaces**, and **Agents** — and is responsible for
shaping that domain into the view the surfaces render.

The desktop GUI is a **thin client**: it does almost no business logic of its own, instead rendering
backend-derived UI state that is pushed to it live (a full snapshot on connect, then deltas). To
keep the two surfaces from drifting from the backend, **TypeScript types and the API clients are
generated from the backend's models and OpenAPI spec**, so the contract is defined once on the
server and consumed everywhere. Underneath the domain, an **agent runner** supervises the actual
agent CLI process, an **isolation layer** gives each Workspace its own copy of the repo, and **local
persistence** records everything.

| Component | Responsibility |
|---|---|
| **Electron desktop GUI** (React) | Thin client that renders backend-derived UI state streamed live; sends user actions to the backend over HTTP. Built with React/Jotai/Radix, packaged via Electron Forge. |
| **`sculpt` CLI** | First-class headless surface (terminal, scripts, CI) for driving the same local Sculptor as the GUI. See §8. |
| **Local backend server** | The single local service both surfaces talk to — exposes the HTTP API and the live update stream, owns the Project/Workspace/Agent domain, and derives the shaped UI state the frontend renders. |
| **Agent runner** | Launches and supervises the **terminal agent CLI** (a PTY) for each Agent, tracking its lifecycle and surfacing its status and file changes back through the backend. |
| **Isolation layer** | Backs each Workspace with a **git worktree** — its own branch sharing the repo's history — running locally on your machine. |
| **Local persistence** | A local SQLite store — **a single mutable table per entity**, updated with UPSERTs that latch the latest state via `MAX()`, behind versioned migrations — holding Projects, Workspaces, and Agents. |

Deeper detail on how these pieces are built and operated lives in **§10 (Engineering Substrate)**;
the guarantees they uphold are spelled out in **§9**.

## 6. Core Domain Model

Sculptor's vocabulary is small and load-bearing; every feature in §7 is described in these terms.
This section names **only concepts a user sees, names, or configures.** Internal abstractions with
no user-facing presence (Environments, the task primitive, services, the streaming protocol) are not
here — they live in §5 and §10.

**Project (aka Repo).** A connected git repository — "Project" and "Repo" are the same thing; a
project *is* the repo you pointed Sculptor at. It is the parent of its workspaces and carries
repo-level settings the user can configure: a default system prompt, an optional workspace **setup
command**, and a branch-naming pattern.

**Workspace.** An isolated copy of a project's repository where agents do their work, so they never
edit your own checkout directly. A workspace is a **git worktree** — it shares your repo's history
but has its own branch, so the agent's commits land in your repo immediately and you can push them
yourself.

A workspace also has a source branch, a **target branch** (what its changes and any PR are measured
against), a **setup status** (if the project defines a setup command), and a set of **changes** that
may still be computing just after the agent edits files. It is shown as a tab.

**Agent.** One terminal session bound to a workspace — the user-facing unit of work, shown as a tab
inside the workspace. An agent has a **status** the user sees as status dots and tab state:
*building* (its environment is being set up), *running* (actively working), *ready* (idle / done),
*waiting* (it is blocked on input), or *error*. The running/ready/waiting states are driven by the
agent's terminal integration signalling **busy / idle / waiting** (→ §7.3, §8). Several agents can
run in one workspace; they share its files and git state but each keeps its own terminal session and
history.

**Task (internal, not a product concept).** An agent is internally backed by a general-purpose
**task** primitive, now vestigial — every task backs an agent; there are no non-agent task types. A user
never sees or names a "task"; it survives only as a storage and scheduling detail behind an agent.
Its internal status is distinct from the user-visible agent status above — don't conflate them.

**Change / Diff.** A workspace's modifications measured against its target branch — the basis of the
Changes view (§7.5). Just after the agent edits files, the diff may briefly show as still computing.

**Commit / Branch / Pull Request.** The git outputs of a workspace. A workspace owns a branch; the
agent or user makes commits on it; and a workspace can open a **pull request** against its target
branch, after which Sculptor tracks the PR's CI and review status (and can "babysit" CI → §7.6).

**Skill.** An invocable, named workflow — bundled (the spec → mock → architect → plan → build →
review pipeline, plus `fix-bug` and `setup-repo`).
Skills are Claude Code slash commands invoked by typing the command into a terminal agent, and a
skill typically runs as its own agent. (§7.8.)

**Action.** A workspace-scoped helper: a saved, re-runnable prompt (organized into groups) that you
fire into a terminal agent with one click. (§7.11.)

**Notification.** A surfaced system or agent event (e.g. an agent finished, or needs attention).

## 7. The Product, Feature by Feature

This is the body of the spec — each feature described in prose: what it is, how it behaves, and its
notable edge cases.

### 7.1 Onboarding & connecting a repo

The first time you open Sculptor, a short **setup wizard** walks you through two steps — a dependency
check and connecting a repo — with a row of dots at the bottom tracking your progress. Reopening
Sculptor restarts the wizard until you have connected a repo; once a repo is connected, onboarding is
skipped. There is no
account, no sign-up, and no telemetry consent: Sculptor runs locally and nothing about you is
collected.

The first step is a read-only **dependency check**. Sculptor looks for the two tools it needs —
`claude` and `git` — on your `PATH`. Each is shown as found or missing, and a missing tool is flagged
with a "How to install" link. The check is advisory: you can continue into the app whether or not both
are found. It does not install anything for you
and there is no managed binary or path override — you install the tools yourself and they are
resolved from your `PATH`.

Next, you connect your first **repository** (→ §7.2 Workspaces). Point Sculptor at a repo by typing
its path — a directory autocomplete helps as you type a path beginning with `/` or `~` — or, on
desktop, browse for a folder, then click **Add**. If the folder isn't a Git repo yet, or is a repo
with no commits, Sculptor offers to initialize it or make an initial commit for you; a bad path
surfaces an error you can dismiss. Once a valid repo is connected the wizard finishes and drops you
into the app, ready to create a workspace and run your first agent.

### 7.2 Workspaces

A **workspace** is how you start work in Sculptor: you pick a project (repo) and Sculptor creates an
isolated copy of it for agents to work in, rather than touching your own checkout. You create one
from the **Add Workspace** form (titled "Name your workspace") — choosing the repo, the source branch
to start from, a workspace name, the name for the workspace's new branch (with a live preview and a
warning if that branch already exists), and the **type of the first agent** to create (a plain
**Terminal** or a registered terminal agent such as **Claude CLI** → §7.4). The workspace is a
**worktree**: it shares your repo's history but gets its own branch, so the agent's commits show up
in your repo right away and you can push them yourself. Each open workspace is a **tab**.

Inside a workspace, a header **banner** shows where you are: the repo, the workspace's branch (which
you can copy), a one-glance **diff summary**, and the workspace's **target branch** — what its changes
are diffed against, with a selector to change it and a warning if a PR's target wouldn't match. (The
target branch applies to every repo; the PR/MR surface built on it appears only for GitHub or GitLab
repos → §7.6.) The banner collapses progressively as space tightens.

If the project defines a **setup command**, it runs when the workspace is created; its progress and
logs are surfaced, with controls to cancel or re-run, and the workspace's diff isn't meaningful
until setup finishes.

A workspace can hold **multiple agents**, shown as tabs within it. They all share the same files and
git state — there is no locking between them, so two agents editing the same workspace can step on
each other — but each has its own terminal session, status, and history. You can add, rename
(double-click), reorder, mark-unread, and delete agents, and a small **peek** popover previews other
agents' state on hover.

Deleting a workspace removes it and all of its agents and cleans up the underlying git worktree. A
workspace whose underlying repo or working copy has gone away surfaces an error state rather than
failing silently. _(→ Changes §7.5, Agents §7.4, Pull Requests §7.6; isolation guarantees §9.1.)_

### 7.3 Terminal agents

An **agent** is a terminal. Its main panel is an interactive, full-pane terminal — a real shell
session (a PTY) running inside the workspace — that you type into directly. There is no chat input,
message stream, model picker, or plan/queue surface: you drive the agent the way you'd drive any CLI
tool, and Sculptor watches from the outside. An agent is still a first-class object — its own tab,
name, status dot, history, and lifecycle — sharing the workspace's files and git state with its
siblings (→ §7.4). Your terminals and their scrollback persist as you navigate around Sculptor.

Agents come in two flavors. A **plain Terminal** is a bare login shell in the workspace, for running
whatever you like by hand — it cannot be driven by an automated prompt. A **registered terminal
agent** additionally launches a specific command on start (most importantly a CLI coding agent like
Claude Code), so the workspace opens straight into that tool's own terminal UI.

A registered terminal agent is defined by a small **registration**: one TOML file per agent under the
Sculptor folder's `terminal_agents/` directory, named by a `registration_id` (the file's stem) and
declaring a `display_name` (what the create menu shows), a `launch_command` to run when the agent
starts, an optional `resume_command_template` (so the agent can reattach to the same underlying
session after a Sculptor restart), and whether it `accepts_automated_prompts`. The directory is
re-read on demand, so dropping in a new file makes a new agent type available with no restart; and
the launch parameters are stamped onto the agent when you create it, so it keeps working even if you
later edit or delete the registration file.

Sculptor ships one registration out of the box — **"Claude CLI"** (`registration_id` `claude-code`,
`accepts_automated_prompts`), which runs the Claude Code terminal UI in the workspace. It's installed
automatically on first run into your `terminal_agents/` folder, where it's yours to edit or delete
(your edits are never overwritten, and deleting it sticks — Sculptor won't reinstall it). Creating a
new agent defaults to the type you last used, falling back to "Claude CLI". A companion hooks file
wires the CLI back into Sculptor: as the agent works, the hooks call the **`sculpt signal`** CLI
(→ §8) to report **busy / idle / waiting** status — lighting the agent's status dot — and
**files-changed** to refresh the Changes diff, and to hand back the session id Sculptor needs to
resume the conversation after a restart. Plans, questions, and tool activity are rendered by the
coding tool itself inside the PTY, not by Sculptor.

### 7.4 Agents — multiple roles per workspace

A workspace can hold several **agents** at once, each its own terminal session with its own history
and pending changes, shown as a row of **tabs**. Each tab carries the agent's name and a **status
dot**, and hovering the dot tells you the status and how long since its last activity. Click a tab
(or use the next/previous-agent keybinding) to switch between them.

Create a new agent with the **+** button at the end of the tab bar (or the new-agent keybinding); it
creates an agent of your last-used **type**. Next to it, a small **chevron** opens a menu of the types
you can create: a plain **Terminal**, and then each **registered terminal agent** by its display name
— out of the box that's **"Claude CLI"**, which runs the Claude Code TUI in the workspace (→ §7.3).
The menu marks your last-used type with a check, Sculptor remembers it, and a plain **+** click
re-creates that type without opening the menu. **Double-click** a tab to rename it (Enter saves,
Escape cancels), drag tabs to **reorder** them, and right-click for more: rename, **mark unread**,
copy the agent name, a **Diagnostics** submenu (toggle the debug view; copy the agent id, the claude
session id, or the Sculptor transcript path), and delete. **Deleting** an agent (after confirming) moves you to the next one, or
starts a fresh agent if it was the last.

Because every agent in a workspace works on the same copy of your repo, **siblings share its files
and Git state with no locking**. In practice it's rare to have two of them *actively editing* at the
same moment — and you wouldn't want to, since with no lock to stop them, two agents touching the same
file at once can step on each other. The real reason to keep several agents in one workspace is to
hold **separate contexts and roles** over the same code: an *implementer* agent and a *reviewer*
agent, say, or one agent carrying the main feature work while another is a scratch context for a side
investigation or a quick experiment — each with its own terminal session and history, all looking at
the same files. When you do want genuinely *simultaneous* work, divide it across different parts of
the codebase or stagger dependent tasks so the agents don't collide — though for fully independent,
parallel work, separate **workspaces** are usually the better tool (→ §7.2, scenarios S2/S5). The
coding tool running inside an agent may itself spawn its own subagents to fan out work; that happens
within the tool's own terminal, and Sculptor tracks the whole thing as the single agent it launched.

To check on a workspace without leaving the one you're in, hover a workspace tab to open a **peek**
popover: a quick preview of that workspace's status, its list of agents, branch, pull-request state,
and diff stats. Moving between tabs swaps the preview instantly; for a busy workspace it shows the
first few agents with a "+N more" control to reveal the rest. Click an agent row (or the header) to
jump straight there.

### 7.5 Changes — review & commit

When an agent edits files, you review the result in the **Files** panel, which sits at the top-left
of the workspace and carries three tabs: **Browse** (the workspace's full file tree, for opening any
file), **Changes** (every modified file), and **Commits** (the workspace's commit history). The
Changes and Commits tabs show a count badge when there's something to see. Nothing leaves the
workspace until you choose to commit (→ §7.6 Pull Requests).

The file tree can be shown as a nested **tree** or a flat list, and you can toggle between them,
collapse every folder at once, or refresh to re-fetch. A search control filters the tree as you type
— ancestor folders of matches expand automatically, and "No matches" appears when nothing fits. In the
**Changes** view each file carries a status letter (modified, added, deleted, renamed) in a distinct
color along with its added/removed line counts; folders roll those up into a change-count badge,
deletions are struck through, and a file that failed to process shows an error badge. (The **Browse**
tree lists the whole repository and shows the same status letters and folder change-count badges, but
without the per-file line counts or the discard action.) Right-clicking a file or folder opens a menu with actions like opening
its diff, viewing the file, and copying its path (full or relative) — plus, when Sculptor can reach
your local filesystem, opening it in your OS's default app and revealing its containing folder.

Clicking a file in the **Changes** tab opens it in the main **diff** view; clicking a file in
**Browse** opens its read-only contents instead, since an unchanged file has no diff. A scope picker lets you look at only the
**uncommitted** changes or, when the workspace has a target branch,
**all** changes measured against that target branch, with a count on each option. The diff itself can be shown **side-by-side** or **unified** (inline), with line-wrapping, a
find-in-file search that highlights matches and counts them ("X of Y") as you step through, and an
expand control that widens the diff across the whole window. A binary file replaces the diff with an
explanatory banner, and renamed or deleted files show a banner above the diff — and for images, a
before/after preview with zoom and pan — while a very large diff is truncated behind a "Show full
diff" button. You can also open a file's full read-only contents with syntax highlighting rather than
a diff. In the **uncommitted** scope, each changed file has a **Discard changes** action that reverts
just that file to its last committed state after you confirm.

When you're satisfied, the **Commit** button at the top of the Changes tab, above the file list — labeled with the
pending count, e.g. "Commit 2 changes," and disabled when there's nothing to commit — asks the agent
to write a message and make the commit on the workspace branch. Committing does not push; the commit
stays on the branch until you push it or open a PR/MR. Clicking the button does a **quick commit**
with the default prompt; right-clicking it opens a dialog to **edit and save the commit-message
prompt**, which then steers how messages are written on subsequent commits.

The **Commits** tab shows the workspace's history as a **commit graph** with connecting dots and
lines. Each entry shows the first line of its message, the file count, added/removed stats, a
relative time, and a short hash; hovering reveals a popover with the commit's author, date,
and short hash, and a copy button that copies the full hash, confirming by briefly swapping its icon for a checkmark. Clicking an entry expands it to
list the files in that commit, and clicking one of those files opens a diff of that file against its
parent. Merge commits can be expanded to follow the merged-in branch, and a marker at the bottom
shows where the workspace's history forks from its starting point.

### 7.6 Pull Requests

The pull-request surface described here appears **only when the workspace's repo has a GitHub or
GitLab `origin`**; for any other repo there is no PR/MR control — though the target-branch selector still appears — and you
push the branch yourself. Given such a repo, once you've committed work on a workspace branch you can
open a **pull request** (on GitHub) or **merge request** (on GitLab) straight from the workspace's
top bar — Sculptor stays provider-neutral, so the control reads "Create PR" or "Create MR" to match
your repo. Clicking it pushes the branch and
asks the agent to open the request against the workspace's target branch. If you'd rather adjust how
that's done first, the button's chevron menu offers **Edit prompt...**, which opens a dialog to revise
the PR/MR-creation prompt before you create anything. While Sculptor is looking up status, the button
shows a spinner with "Checking PR..."/"Checking MR...".

Once a request exists, the button displays "PR #N"/"MR !N" alongside small status dots for its
**pipeline/CI** and **review** state; hovering the dots explains them ("Pipeline running/passed/
failed," "Approved/Review pending," and so on). Clicking the number opens the request in your browser.
The chevron opens a **detail dropdown** with the title and link, checks/pipeline status, approvals and
reviewer names, and any unresolved comments. If a **CI babysitter** is available, a switch in this
dropdown lets you pause or resume it — when on, Sculptor keeps an eye on the request's CI for you —
and the status text updates as you toggle it.

When the request is **merged** or **closed**, the button switches to a merge icon reading "PR #N
merged"/"closed," and clicking it still opens the request in the browser. If a request already exists
but targets a different branch than the workspace does, the button becomes **Assign PR/MR**, offering
to create a fresh request against the workspace's target or to switch the workspace's target to match
the existing request. The target-branch selector itself flags the mismatch in a warning color, with a
hover hint like "PR #N targets {branch} — retarget?". (A failing CI check itself just shows a red
pipeline dot / "Failed" badge on the normal button.) If Sculptor can't *look up* the request's status
at all — the provider CLI is missing, you're not authenticated, the host is rate-limiting, and so on
— the button turns into an error state: a warning triangle for something you can act on, or an info
icon otherwise, whose popover gives a title, description, optional details, and sometimes a copyable
remediation command.

### 7.7 Terminal

Sculptor includes a built-in **workspace terminal** — a real shell that runs inside the current
workspace, so anything you type operates on the very files the agent is working with. It's handy for
starting a dev server, running tests or linters, inspecting git state, or any command that's quicker
to run yourself than to ask the agent for. You open it from the command palette or the panel controls
in the bottom bar, and it can sit open alongside a running agent without interfering with the agent's
own terminal.

You can keep several terminals going at once. The **+** in the tab bar adds another ("Terminal N"),
double-clicking a tab renames it inline, and each tab is an independent shell in the same workspace;
right-clicking offers rename, close, and "Close others," tabs can be reordered, and closing the last
one spins up a fresh replacement. When output arrives in a tab you're not looking at, a pulsing
**unread** dot appears on it and clears when you switch over. A starting terminal briefly shows
"Starting terminal..." while it
comes up; Ctrl+L clears the focused terminal; and your terminals — along with their scrollback —
persist as you navigate around Sculptor rather than resetting each time.

This section is about your own terminal. It is distinct from a **terminal agent** — an agent whose
terminal is driven by a coding tool rather than by you (→ §7.3, §7.4 Agents).

### 7.8 Skills & Workflows

A **skill** is a reusable agent capability you invoke as a **Claude Code slash command** — you type
`/skill-name` directly into a terminal agent (the agent is Claude Code), and the skill runs as a full
agent with its own tools, so it can read your codebase, spawn parallel subagents, and adapt to your
repo. Sculptor surfaces three kinds: the **built-in** skills Claude Code ships with, the **Sculptor**
plugin skills (the workflow set below, plus the base `sculptor` plugin's
`sculpt-cli`), and any **custom** skills you've installed under your home or repo `.claude/`
directory.

Sculptor also includes a **skill library** panel — a reference surface for browsing what's available
rather than an input. It lists every skill grouped by type under collapsible headers, with its own
search box that filters as you type, arrow-key navigation, and a type filter to narrow which kinds
are shown. Hovering a skill opens a popover with its description; moving to another skill swaps the
content instantly. A custom or Sculptor skill carries an **Open in Sculptor** control that opens the
skill's file in a viewer tab so you can read its definition. The panel has clear loading, empty, and
error states. To actually run a skill you type its slash command into the agent's terminal.

The flagship bundled skills form the **engineering workflow** (the `sculptor-workflow` plugin): a
pipeline that takes a feature from idea to shipped code in focused stages — **spec → mock → architect
→ plan → build → review**. Each stage is its own skill and runs as its own dedicated agent, renamed
to match the stage ("Spec", "Architect", "Plan", and so on) so you can tell the tabs apart, and each
produces a durable artifact on disk that the next stage reads. `spec` writes the implementation spec
through guided Q&A you watch take shape in the diff viewer; `mock` produces interactive HTML mocks
(exploration mode generates several variants to compare, confirmation mode refines one); `architect`
writes the architecture document; `plan` turns it into a folder of self-contained task files; `build`
executes them one at a time, committing as it goes; and `review` checks the diff against the spec,
re-runs the tests, and writes up its findings. You don't have to run the whole pipeline — every stage
takes a feature *slug*, finds the earlier artifacts, and offers to **hand off** to the next stage
when it finishes.

Two more workflow skills stand alone. **`setup-repo`** is run once per repo to create the small
config files that teach the other skills how your codebase builds, tests, and where it keeps docs
(other stages invoke it for you if those configs are missing). **`fix-bug`** is a self-contained,
test-driven bug fix: it reproduces the bug with a failing test, fixes the code, and verifies —
interactively by default, or end-to-end with no questions when run autonomously, optionally opening a
pull request if the repo allows it.

### 7.9 Command Palette & Navigation

Sculptor is organized into **tabs** along the top: a **Home** tab, a **Settings** tab, and a tab for
each open workspace. You switch tabs by clicking, cycle through them with keyboard shortcuts (these
keep working even in zen mode), drag to reorder them, and close them with the tab's minimize button, a middle-click,
or a keyboard shortcut. Workspace tab labels truncate when long and carry a small **status dot**
reflecting the agent's state; double-clicking a tab renames the workspace inline, and right-clicking
opens a context menu to rename it, delete it, or close others/all. When too many tabs are open they overflow into a horizontal
scroller that keeps the active tab in view, and closed workspaces collect into a pill you can reopen
from. Tabs persist across restarts.

The **Command Palette**, opened with **Cmd+K** from anywhere, is the fastest way to get around once
you have several workspaces and agents open. It's a searchable list with the input focused and
commands grouped (Workspaces, Navigation, Theme & Layout, Terminal, Help). Type to filter
(fuzzy and case-insensitive, with groups reordering by best match), move with the arrow keys, press
**Enter** to run a command — or **Cmd+Enter** to run it and keep the palette open for another. Some
commands open **sub-pages** (shown with a chevron and reached with Tab) such as the workspace
switcher, which **Cmd+P** opens directly. From the palette you can switch between or create workspaces
and agents, show or hide panels, open Settings or Help, and toggle the theme. Commands
that don't apply right now are greyed out with a reason ("Only one agent in this workspace", "No
uncommitted changes"), and rows show their keyboard shortcut where one exists.

The **bottom bar** carries toggle buttons for the left, bottom, and right side panels plus a
focus-mode button. Clicking a toggle shows or hides that panel and updates its active state; a panel
with no content is disabled with a "Panel is empty" tooltip; and hovering any toggle shows its name
and keybinding. **Focus mode** (Cmd+\) collapses all side panels so the agent expands, and toggles
back. **Zen mode** (Cmd+Shift+\) goes further, hiding the top bar and side panels entirely to leave
just the agent with a draggable title bar; an "Exit zen mode" button appears when you move to the
top-left corner. The app's **version number** sits in the bottom-right — in the workspace bottom bar
and in the corner of the non-workspace pages; clicking it opens a popover showing the version and git
SHA, read-only **diagnostics** (platform, uptime, active agents, disk, paths, install info), and
toggles for the in-app developer tools.

### 7.10 Settings

**Settings** (opened with Cmd+, or from the top bar) is a single page with a sidebar of sections; it
remembers the last section you viewed and can be deep-linked to a specific one. Changing a setting
saves on the spot with a "Setting updated" toast (or an error toast on failure).

Settings has eight sections. **General** controls appearance — the Light / Dark / System theme.
**Keybindings** lets you search, view, assign, clear, and reset every keyboard shortcut, warning you
when a combination conflicts with an existing one.

The repo-facing sections are **Repositories**, **Git**, and **CI**. Repositories lists your connected
repos with their paths and agent counts and lets you add or remove them and configure each one's
**setup command** and **branch-naming pattern**. Git holds the cross-repo defaults: the pull-request
creation prompt, PR-status polling and its interval (plus a multiplier that throttles polling for
closed workspaces), the default target branch, the global branch-naming pattern, and the
branch-deletion policy. CI configures the **CI babysitter** that watches pipelines and asks an agent
to fix failures — a toggle, the agent that drives it (most-recently-used or a specific registered
agent), a retry cap, and editable prompts for pipeline failures and merge
conflicts.

The remaining sections cover the workspace environment. **File browser** sets diff defaults (split
versus unified, line wrapping, the default split ratio), tab-close behavior, and the commit-message
prompt. **Environment variables** surfaces the global and per-repo `.sculptor/.env` files (which you
edit directly on disk) and controls whether they override existing variables. **Actions** is the full manager
for your saved prompts and groups, including import/export (→ §7.11).

### 7.11 Actions

**Actions** are saved, re-runnable prompts that live in a workspace panel as one-click chips,
organized into **action groups** (the built-in "Sculptor" group — which ships `/help` and `/fix-bug`
shortcuts — sits first, with any ungrouped actions at the bottom; collapsed group headers carry a
count badge). Clicking an action types its prompt **into the agent's terminal**: an **auto-submit**
action (shown with a play icon) types the prompt and presses Enter, running it immediately; a
**draft** action (shown with a text-cursor icon) types the prompt into the terminal without sending,
so you can edit it first. A hover tooltip previews the prompt. You create, edit, and delete actions
through a dialog (Name, Prompt, Group, and an auto-submit toggle), manage groups inline (add, rename,
delete), and drag actions and groups to reorder them or move an action between groups — built-in
items can't be edited, deleted, or dragged. The same actions can be managed in bulk from Settings,
including import and export to a JSON file (→ §7.10).

## 8. The `sculpt` CLI  _(core product surface)_

`sculpt` is a first-class way to drive Sculptor **headlessly** — from a terminal, a shell script, or
CI — against the very same local Sculptor that the desktop app talks to. Anything you create with
`sculpt` shows up in the GUI, and anything you create in the GUI is visible to `sculpt`: a
**Workspace** you spin up on the command line opens as a real workspace in the app, and an **Agent**
you start from a script runs in the same terminal a person would watch. This makes `sculpt` the
natural surface for automating Sculptor, scripting fleets of parallel agents, or wiring coding agents
into a pipeline.

The CLI is organized into a handful of command groups, each mapping to a domain noun or a job:

| Group | What it's for |
|---|---|
| `sculpt repo` | List and show the **Projects (Repos)** Sculptor knows about — their paths and whether they're accessible. |
| `sculpt workspace` | Create, list, show, rename, and delete **Workspaces**. At create time choose the source branch (`--branch`), a name for the workspace's new branch (`--branch-name`), its target (`--target-branch`), a description (`--name`), and the repo (`--repo`); `list` can span all repos (`--all`) or one (`--repo`), and `delete` takes `--yes`/`-y` to skip the prompt. |
| `sculpt agent` | Manage **Agents** in a workspace: `create` one (`--harness` names the agent type — `Terminal` or a registered display name like `Claude CLI`; omit it to use your most-recently-used type — plus `--name` and `--workspace`/`-w`), list (filter by status, scope with `--all` / `--repo` / `--workspace`), show, check `status`, `send` input into its shell, rename, and delete. `status` accepts `--follow` to stream live. |
| `sculpt run` | One-shot convenience: from a single prompt, create a workspace **and** an agent in one step, optionally `--follow` its output live. Accepts the workspace-creation flags (`--branch`, `--branch-name`, `--target-branch`, `--name`, `--repo`) plus `--harness` and `--submit`/`--no-submit`. The agent must be a **registered terminal agent that accepts automated prompts** — a plain `Terminal` is rejected, since it has nothing to receive the prompt. After the agent's terminal is ready, `run` delivers the prompt by typing it into the PTY. |
| `sculpt signal` | Run from **inside an agent's environment** to report state back to Sculptor — `busy`, `idle`, `waiting`, `files-changed` (refreshes the diff), or `session-id <id>` (which takes the session identifier as an argument). This is how a terminal agent's hooks light up the same status indicators the GUI shows. Takes `--agent` and `--json`. |
| `sculpt ui` | Let an agent **drive the app's UI** for the user: `open-file` opens a file or diff tab (with `--mode auto`/`diff`/`file`). |
| `sculpt schema` | Print machine-readable **JSON Schemas** for command output (run with no argument to list the available schema names, including a dedicated `error` schema for `--json` failures), so scripts can validate and parse results reliably. |

Two conventions make the CLI script-friendly. Commands that emit results accept **`--json`** for
structured output (paired with `sculpt schema` for the exact shape) instead of human-readable text
(`sculpt schema` itself already prints JSON), and
**environment variables set sensible defaults** so you don't repeat IDs — most notably
`SCULPT_WORKSPACE_ID` and `SCULPT_AGENT_ID` (and `SCULPT_PROJECT_ID`, which the shell inside every
Sculptor workspace already sets); `SCULPT_API_PORT` (or a per-command `--base-url`) points the CLI at
a non-default local server. Workspace-scoped commands also take an explicit `--workspace`/`-w` flag
that overrides the env-var default, and the WebSocket-backed read commands (`agent show`, `status`) accept a `--timeout`. IDs can be given as short prefixes rather than full values.

A couple of example invocations:

```bash
# Kick off a fresh workspace + agent from a prompt and watch it work
sculpt run "Fix the failing auth tests" --repo ~/code/myapp --harness "Claude CLI" --follow

# Create an agent in an existing workspace (taken from $SCULPT_WORKSPACE_ID), as JSON
sculpt agent create --harness "Claude CLI" --name reviewer --json

# From inside an agent's environment: open a file for the user and refresh the diff
sculpt ui open-file src/server/health.py --mode file
sculpt signal files-changed
```

## 9. Non-Functional Behavior

Beyond any single feature, Sculptor makes a set of cross-cutting promises about how it behaves — what
your agents can touch, how your work survives a crash, and what leaves your machine. These guarantees
hold across every workspace and agent.

#### 9.1 Isolation & safety

An agent always works in an **isolated copy** of your repository — its own git worktree — so it can
read, edit, and run real commands freely without ever touching your own checkout; the files you have
open stay exactly as you left them. An agent's edits are committed onto a **workspace branch** that
belongs to that workspace; nothing is ever pushed to a remote, and no pull request is opened, unless
you take that action yourself. The trust posture is straightforward: agents run real shell commands
inside their workspace and can do real work there, while you remain the gatekeeper for anything that
reaches the outside world — pushes, PRs, and merges back to your code.

#### 9.2 Concurrency

You can run **many agents across many workspaces at once**, and they make progress in parallel without
getting in each other's way. The one thing to watch: agents placed in the **same** workspace share the
same files with no locking between them, so if you point two agents at overlapping work they can step
on each other's changes. Keeping concurrent agents on separate concerns (or separate workspaces) is
your responsibility (→ §7.4).

#### 9.3 Crash recovery & resumption

Quitting Sculptor — or having it crash — and reopening it **restores your workspaces, your agents, and
their terminal history** right where you left them. A registered terminal agent that was running is
reattached by re-launching it through its `resume_command_template` (→ §7.3) against the session id
its hooks reported, so the coding tool picks up the same session. When something does go wrong, the
app **surfaces the error** rather than failing silently, and an agent left in an errored state can
often be restored and continued rather than lost.

#### 9.4 Responsiveness

The UI stays **live**: an agent's output, its changing status, and the file changes it makes appear in
real time as they happen, with no manual refresh. What you see stays consistent with what you clicked
— the app reflects the true current state of each agent and workspace rather than a stale snapshot.

#### 9.5 Persistence & durability

Your work is **stored locally and is durable**. Workspaces, agents, their terminal history, and your
settings are all saved on your own machine and survive restarts.

#### 9.6 Security & auth

Sculptor is **local-first and single-user**: it runs on your machine for you, and your code stays
there. There is **no telemetry, analytics, or crash reporting** — nothing about your usage is
collected or sent anywhere. The only outbound traffic is the work you ask for: GitHub or GitLab for
pull-request status, and the Anthropic API reached through your own `claude` CLI. Credentials and keys
the app needs are handled locally on your behalf, and the boundary stays the same one described in
§9.1 — your code and secrets stay on your machine unless you explicitly send something out.

## 10. Testability & Engineering Substrate

The systems below are **not user-visible and not technically part of the product**, but Sculptor
cannot be built with high quality without them.

**Why this is a top-level concern:** Sculptor's correctness is mostly *emergent behavior* of
nondeterministic agents acting over real repositories — it can't be specified into existence, it
has to be made **reproducible, observable, and verifiable** during development. Each substrate below
exists because Sculptor depends on something nondeterministic, external, slow, or hard to observe.

#### 10.1 Test doubles & determinism
The single most important piece is the **fake terminal agent**
(`sculptor/sculptor/testing/fake_terminal_agent*.py`): a **scripted registered terminal agent** that
the agent runner launches during tests in place of a real coding-tool CLI. Rather than calling a
model, it runs commands pushed to it through a small side-effecting **DSL** — `write_file`,
`edit_file`, `bash`, `multi_step`, `wait_for_file`, and `sleep` — and emits the same **lifecycle
signals** (busy / idle / waiting, files-changed, session-id) a real terminal agent's hooks would.
This turns the product's most nondeterministic dependency into a precise instrument: a test can drive
an exact sequence of file edits and status transitions and assert the UI that results, and the `wait`
primitives let it freeze the agent so transient states (a "waiting" dot, a still-computing diff) can
be observed deterministically. The same idea recurs for other external dependencies, and **test repo
factories** synthesize throwaway git repositories so tests never depend on a real checkout.

#### 10.2 The end-to-end harness
Frontend integration tests drive the *real* app in a real browser via Playwright, structured as a
**Page Object Model**: a `SculptorInstance` owns the backend process, browser page, and test repo,
and typed page/element objects expose semantic actions ("create a task", "open the diff") instead of
raw selectors. The UI honors a stable **test-id contract** (the `ElementIDs` enum), and integration tests are
tagged with a **`@user_story(...)`** describing the behavior they validate — the thread that links a
test back to a scenario.

#### 10.3 Test taxonomy & fidelity tiers
Tests are stratified by a deliberate determinism-vs-fidelity trade: **unit** tests (colocated,
backend and frontend); **integration** tests (Playwright + the fake terminal agent, the bulk of
user-visible coverage); **regression** tests (one per fixed bug); and a model-backed **`real_claude`**
smoke test that runs a flow against the actual `claude` terminal agent to catch protocol drift. The
real-model test is slow and costs API usage, so it's run deliberately. Further pytest markers
segregate tests by **launch mode** — e.g. `electron`, `electron_custom_command`, and
`packaged_electron` — and by sandbox needs (e.g. `custom_sculptor_folder`), so a test runs only in
the environment it requires.

#### 10.4 Scenarios-as-tests methodology
This spec, the exhaustive **`scenarios.md`** (≈446 Given/When/Then behaviors), and
**`scenario_coverage.md`** (which maps each scenario to the integration test covering it) together
form the **English-level acceptance layer**: the spec is the source of truth, the scenarios are
concrete acceptance checks against it, and the coverage report measures how well the product is
actually demonstrated. This methodology is itself testability infrastructure — it is the reason the
scenario corpus exists.

#### 10.5 Test execution
The suites are driven from the repo root through **[just](https://github.com/casey/just)** targets —
`just test-unit`, `just test-integration`, and the regression and real-model targets — which set up
the backend, browser, and a pinned toolchain per run. Integration tests run the *real* packaged app
in a real browser (§10.2), and the launch-mode markers (§10.3) let a run target the environment a
given test needs.

#### 10.6 Static quality gates
Beyond tests, a set of gates keeps quality from eroding silently. **Ratchets** are per-rule violation
budgets that can only be reduced, never raised without justification — they let the codebase tighten
over time (e.g. forbidding raw CSS selectors or `time.sleep()` in integration tests, capping
`logger.warning` use). Alongside them: formatting, linting, and type-checking (ruff, eslint,
pyrefly, tsc), a **design-token stylelint plugin** that forbids hardcoded style values, and
file-hygiene and shell checks.

#### 10.7 Cross-surface contract generation
Sculptor has three surfaces over one backend (GUI, CLI, API), kept from drifting by **generation
rather than hand-maintenance**: TypeScript types and the frontend API client are generated from the
FastAPI/OpenAPI schema, the `sculpt` client is generated similarly, and a **frozen model-schema
snapshot** (→ §10.8) detects unintended backend-model changes. A backend-model change that isn't reflected across surfaces shows
up as a regenerated diff or a failing check, not a runtime surprise.

#### 10.8 Data-durability machinery
User data lives in a local SQLite database whose schema is **a single mutable table per entity**,
updated with UPSERTs that latch the latest state via `MAX()`. The migration history is squashed to
**one initial migration**, and a frozen Pydantic-schema snapshot is wired in to guard the versioned
JSON fields against unintended change. This is what lets the product evolve its data model without
corrupting users' existing state.

#### 10.9 Diagnosability
Finally, infrastructure for understanding failures that escape the tests: distributed **tracing**,
structured logging conventions, the read-only **diagnostics** surfaced in the version popover
(per-agent and system fields, → §7.9), the **auto-qa** headless-browser harness for visual/manual QA,
and **Storybook** for inspecting components in isolation.

## 11. Build, Release & Distribution

This section describes how Sculptor is built and how it reaches users.

#### 11.1 Build & packaging

Sculptor ships as a **desktop application** that combines a **React frontend** with a **packaged
backend**, bundled together into an **Electron app** via Electron Forge. It builds for **macOS**
(Apple Silicon) and **Linux**. The **`sculpt` CLI** is built and shipped alongside the app, so the
command-line surface is available wherever Sculptor is installed.

#### 11.2 Versioning

Development builds carry a `.dev` version suffix; a release drops the suffix and is signed and
notarized before it is published.

#### 11.3 Distribution

Users download Sculptor as a **signed and notarized macOS `.dmg`** or a **Linux** package. Updates are
manual: you download and install a newer build yourself — there is no in-app auto-update.

## 12. Open Issues

Unresolved questions to settle as the spec matures. Each names a specific place the spec is currently
inconsistent about the §9-product-behavior vs. §10-engineering-substrate line:

- **Do user-facing diagnostics belong in §7 or §10?** The read-only **diagnostics** a user can open
  from the version popover are described under §7.9 yet also filed under §10.9 (Diagnosability) as
  engineering substrate. Decide the rule (user-openable ⇒ §7?) and apply it consistently.
- **The cross-surface consistency guarantee** — that a workspace or agent created via `sculpt`
  appears in the GUI and vice versa — is asserted in §5 and §8 but has no entry among the §9
  guarantees, where a user-facing cross-cutting promise would normally live. Decide whether to add
  one.

## Appendix A — Glossary

The core nouns are defined in §6 (Core Domain Model). This is a quick reference for secondary terms
used throughout:

- **Target branch** — the branch a workspace's changes and pull request are measured against.
- **Peek** — the hover popover previewing another workspace's agents, branch, and status.
- **CI babysitter** — an opt-in helper that watches a pull request's CI and asks an agent to fix
  failures.
- **Slug** — the short feature identifier the workflow skills (spec → … → review) use to find each
  other's artifacts.
- **Skill** — a Claude Code slash command, typed into a terminal agent, that runs as its own agent.
- **Registered terminal agent** — an agent type defined by a TOML registration that launches a
  specific coding-tool command (e.g. "Claude CLI"); see §7.3.
- **Zen / Focus mode** — view modes that hide panels (and, for zen, the top bar) to maximize the
  workspace.
