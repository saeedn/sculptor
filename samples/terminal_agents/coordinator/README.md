# Coordinator terminal-agent registration

Runs the build coordinator (`tools/coordinator/`) — the deterministic
program that executes implementation plans with fresh Claude Code
workers — as a Sculptor tab. Sculptor installs `coordinator.toml` into
`<sculptor folder>/terminal_agents/` on first run.

The launch command invokes plain `coordinator`, so the binary must be
on PATH inside agent shells — install it with
`uv tool install --from tools/coordinator coordinator` (or any
equivalent). For development against this repo, edit the installed
TOML's commands to
`uv run --project tools/coordinator coordinator {args}` (and the resume
template accordingly).

Create a coordinator tab pointed at a plan with:

```bash
sculpt agent create --harness Coordinator \
  --launch-arg run --launch-arg agent_docs/<slug>/plan
```

With no launch args, the coordinator lists plans with incomplete runs
and resumes the one you pick.
