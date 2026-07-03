# Coordinator worker registrations

Repo-level worker registrations for the build coordinator
(`tools/coordinator/`). Each `*.yaml` file here describes how to launch
one worker agent; the registration name is the filename stem, and names
in this directory shadow same-named user-level
(`~/.config/coordinator/workers/`) and built-in registrations. See the
module docstring in `tools/coordinator/coordinator/registrations.py`
for the schema.
