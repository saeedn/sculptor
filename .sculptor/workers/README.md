# Coordinator worker registrations

Repo-level worker registrations for the build coordinator
(`tools/coordinator/`). Each `*.yaml` file here describes how to launch
one worker agent; the registration name is the filename stem, and names
in this directory shadow same-named user-level
(`~/.config/coordinator/workers/`) and built-in registrations. See the
module docstring in `tools/coordinator/coordinator/registrations.py`
for the schema.

This directory holds no registrations today: the built-in
`claude-sonnet` and `claude-opus` cover what this repo's plans need. Add
a file here to point the coordinator at a different harness or model, or
to override a built-in for everyone working in this repo.
