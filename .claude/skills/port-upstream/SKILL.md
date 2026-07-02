---
name: port-upstream
description: |
  Triage new upstream (imbue-ai/sculptor) commits against this slimmed-down
  fork and port the relevant fixes. Reads
  docs/development/upstream-ports.md for the last-triaged baseline,
  classifies each new upstream PR (port / partial / skip), cherry-picks or
  manually ports the keepers, and advances the baseline. Use when asked to
  "port upstream fixes", "catch up with upstream", or to triage what's new
  upstream.
argument-hint: [optional: specific upstream PR numbers to port]
---

# Port Upstream Fixes

This repo diverged permanently from [imbue-ai/sculptor](https://github.com/imbue-ai/sculptor)
at commit `d457af55b2` (see the README and `agent_docs/slim-down/`). Upstream
changes are consumed **only** by selective porting — never by merging
`upstream/main`. Bookkeeping is one recorded SHA: the baseline in
`docs/development/upstream-ports.md`, the single source of truth for
"triaged up to here".

If specific upstream PR numbers were passed as arguments, skip the triage
sweep and go straight to **Porting** for those PRs (do not advance the
baseline past commits you did not triage).

## Prerequisites

```bash
git remote get-url upstream || {
  git remote add upstream https://github.com/imbue-ai/sculptor.git
  git remote set-url --push upstream DISABLED
}
git fetch upstream
```

## Procedure

### 1. Enumerate the new upstream delta

Read the **baseline** SHA from `docs/development/upstream-ports.md`, then:

```bash
git log --first-parent --oneline <baseline>..upstream/main
```

Each first-parent commit is one upstream PR (or a direct push). Work oldest
to newest.

### 2. Triage each PR

For each, inspect what it touched (`git show --stat <commit>`; read the diff
when paths alone don't decide it) and assign a verdict:

| Verdict | Meaning |
|---|---|
| PORT | Applies to surviving code; fix/improvement worth having |
| PARTIAL | Mixed; only the hunks touching surviving code are worth porting |
| SKIP-removed | Touches only features this fork removed |
| SKIP-irrelevant | Version bumps, upstream CI/release/telemetry infra, churn |
| SKIP-already | Fork already has an equivalent change |

**Removed on this fork** (changes touching only these are SKIP-removed):
rich Claude/Pi chat agents and the chat UI (chat-alpha, ChatInput,
ask-user-question/plan-mode blocks, mentions, attachments, model/effort
selectors, TipTap, chat scroll), message parsing/conversion, telemetry
(PostHog/Sentry), report-a-problem, auto-update, dependency management, the
onboarding wizard, the theme builder, panel drag-and-drop docking, zen/focus
mode, the Skills/browser/Notes panels, frontend plugins and experimental
flags, in-place/clone workspaces, custom/remote backend, GitLab support,
file uploads, upstream's CI + release pipeline, FakeClaude/fake_pi test
fakes.

**Kept** (fixes here are PORT candidates): worktree workspaces, multi-agent,
terminal agents + PTY/xterm, diff/file viewer, git operations, GitHub PR
tracking, CI Babysitter, sculpt CLI, workflow skills, settings
(appearance/keybindings/actions/env-vars), backend services, Electron shell,
the fake-terminal-agent test harness, justfile dev tooling.

Lean toward PORT for: terminal/PTY fixes, worktree/git handling, PR
tracking/babysitter, sculpt CLI, skill fixes, security fixes, data-model/DB
fixes, and test-flake stabilizations for surviving tests.

### 3. Port the keepers

Branch off `main`. For each PORT, oldest first:

- **Clean pick** (surrounding code hasn't diverged):
  `git cherry-pick -x -m 1 <merge-commit>` — one commit per upstream PR,
  with the upstream SHA recorded in the message by `-x`. Small conflicts are
  fine to resolve by hand.
- **Manual port** (code moved/rewritten on the fork, or PARTIAL): apply the
  surviving hunks by hand in a fresh commit titled
  `Port upstream #<PR>: <what it fixes>`, explaining any adaptation in the
  body.

Fork-specific porting gotchas:

- **DB schema changes**: do NOT port upstream's migration file — the
  chains diverged (this fork squashed its history into a single initial
  migration), so upstream revisions won't chain onto the fork's head. Port
  the model changes, then follow the repo's standard flow
  (`sculptor/sculptor/database/README.md`): run `bump_migrations` to
  autogenerate a new incremental migration + version-test stub, reconcile
  the generated migration against upstream's intent, and fill in the
  version test. The same flow handles the frozen pydantic schemas when
  persisted JSON models change.
- **Ratchets are at their caps** — an upstream hunk that adds a flagged
  pattern fails `just check`; fix the pattern, don't bump the budget.
- **Generated types** (`frontend/src/api`, sculpt client) are gitignored and
  regenerate during `just check` — never port upstream edits to them.
- **Removed API routes fall through to the SPA catch-all and return 200**,
  not 404 — beware upstream tests that probe routes this fork removed.
- Upstream test hunks written against FakeClaude must be re-expressed
  against the fake terminal agent (see the write-integration-test skill) or
  dropped with the feature.

### 4. Gate

Per repo convention: `just format && just check && just test-unit` before
each commit is finalized. If the port touches runtime behavior, also run the
affected integration tests via the run-integration-test skill. Before
attributing any test failure to the port, re-run it in isolation (and, if it
still fails, at the pre-port commit): a failure that only reproduces under
parallel load or on some runs is a flake, not a port regression.

### 5. Advance the baseline

In `docs/development/upstream-ports.md`, set the baseline to the newest
upstream commit you triaged (do this even if nothing was ported). This is
the only file update; the per-session record lives in the porting PR.

### 6. Open the PRs

Group by fate, not by size. Since every port is its own commit, revert and
bisect granularity is already per-commit — a separate PR is only warranted
when a port needs something the batch doesn't:

- **The batch PR** (the default): all clean/near-clean picks from the
  session, as ordered commits on one branch off `main`. One gate run, one
  review.
- **A separate PR** for any port that needs focused review against the
  upstream diff (manual ports with real adaptation), extra verification
  beyond the standard gates, or independent hold/revert consideration
  (DB migrations, data-model or babysitter/PR-polling behavior changes) —
  or that might not merge at all. Rule of thumb: if its entry in the batch
  PR description wouldn't fit on one line, it wants its own PR.
- **No stacked PRs.** If port B depends on port A, put them in the same PR
  as ordered commits (they share fate by definition). All PRs branch
  independently off `main` and can merge in any order; rebase only on
  actual conflict.

The batch PR's body is the session's record: list the upstream PR numbers
ported and a one-line reason per skip (grouped is fine — e.g. "12 PRs touch
removed chat UI"); separate PRs reference it. Follow the repo's public-repo
scrubbing and sign-off rules for all PR bodies.
