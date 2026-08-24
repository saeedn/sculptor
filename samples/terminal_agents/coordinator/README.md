# Coordinator terminal-agent registration

Runs the build coordinator (`tools/coordinator/`) — the deterministic
program that executes implementation plans with fresh Claude Code
workers — as a Sculptor tab. Sculptor installs `coordinator.toml` into
`<sculptor folder>/terminal_agents/` on first run.

The launch command invokes plain `coordinator`, and Sculptor puts its
own bundled CLIs first on the PATH of every agent shell, so no install
is needed: the packaged app ships a `coordinator` binary alongside
`sculpt`, and a source checkout exposes the one its dev venv builds.
Nothing stops you pointing the registration elsewhere — edit the
installed TOML's `launch_command` and `resume_command_template` to any
command you prefer.

Create a coordinator tab pointed at a plan with:

```bash
sculpt agent create --harness Coordinator \
  --launch-arg run --launch-arg agent_docs/<slug>/plan
```

With no launch args, the coordinator lists plans with incomplete runs
and resumes the one you pick.
