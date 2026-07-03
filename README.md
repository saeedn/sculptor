# Sculptor

Sculptor is a desktop app for running coding agents in parallel.

This repo is a fork of [imbue-ai/sculptor](https://github.com/imbue-ai/sculptor) that heavily slims down the product. The goal is to emphasize the core value-add of Sculptor — its organization of workspaces and agents, and the supporting tools that enable good development workflows (diffs, PRs, skills).

The biggest change: the rich chat interface is gone, in favor of each agent's own terminal UI. This removes most of Sculptor's complexity, bugs, and slowdowns, and gives users an agent's full feature set without ever lagging behind because Sculptor's UI hasn't caught up.

## Privacy

This version has no telemetry and no data uploads of any kind. Upstream's analytics, crash reporting, session replay, and diagnostics uploads are all removed. Your agent talks to its own provider and git talks to your remotes — nothing else leaves your machine.

- **No auto-update** — Sculptor never phones home to check for updates; you update by pulling this repo.
- **No email needed** — there is no signup or account; onboarding is just a check that your agent is installed.

## Agents

[Claude Code](https://claude.com/claude-code) is bundled as the default agent and needs the `claude` CLI installed. Any terminal-based agent can be added by dropping a registration file into `~/.sculptor/terminal_agents/` — the bundled [claude-code registration](samples/terminal_agents/claude-code/) serves as the reference example.

## Running from source

See [Getting Started](docs/development/getting_started.md) for setup and how to run Sculptor from source.

## Building a packaged app (macOS)

To instead build the packaged desktop app and install it:

```bash
just refresh pkg   # build assets, then an unsigned DMG at dist/Sculptor.dmg
```

`just refresh` rebuilds the pieces the app bundles — the backend sidecar, the `sculpt` CLI, the frontend, and the icons. You only need it when those inputs have changed; on a repeat build you can run `just pkg` on its own.

The DMG is unsigned, which is fine for a local install (a signed, notarized build needs an Apple Developer certificate — pass `SIGN=1` if you have one). Install it the usual way: open `dist/Sculptor.dmg` and drag Sculptor into Applications. Quit any running Sculptor first, since this replaces `/Applications/Sculptor.app`.

## Status

This fork is experimental and changes quickly and significantly. Expect rough edges, and expect things to break or disappear without notice.

## License

MIT, same as the original — see [LICENSE.md](LICENSE.md). Sculptor was created by [Imbue](https://imbue.com).
