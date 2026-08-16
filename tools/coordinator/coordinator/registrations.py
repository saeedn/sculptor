"""Worker registrations: template-based launch descriptions for workers.

A registration is one YAML file whose filename stem is the registration
name. The plan manifest references registrations by name
(``defaults.worker``, ``defaults.escalation_worker``, per-task
``worker``); reviewer agents for the agentic gate use the same
mechanism. A new harness or model is a new file, not code.

Schema:

.. code-block:: yaml

    display_name: Claude Opus           # human-readable label
    model: opus                         # optional; substituted for {model}
    command:                            # argv template
      - claude
      - -p
      - --dangerously-skip-permissions
      - --model
      - "{model}"
      - --settings
      - "{settings_file}"
      - "{prompt}"
    env:                                # optional extra env for the child
      SOME_VAR: value

Workers run headless: the coordinator spawns them on pipes, observes
them through hooks, and reaps them. A command that needs a terminal has
no way to report a verdict here.

``command`` is an argv LIST, not a shell string — elements are passed
to the child verbatim, so no shell quoting is ever needed (this is why
the format differs from Sculptor's terminal-agent TOML). Placeholders
(``{prompt}``, ``{settings_file}``, ``{attempt_dir}``, ``{cwd}``,
``{model}``) may be a whole element or embedded in one; any other
``{...}`` token is rejected at load so typos fail loudly. ``{prompt}``
must appear exactly once.

Discovery is layered, nearest wins by name:

1. built-ins shipped as package data (``coordinator/data/workers/``);
2. user level: ``$XDG_CONFIG_HOME/coordinator/workers/`` (default
   ``~/.config/coordinator/workers/``);
3. repo level: ``<repo-root>/.sculptor/workers/``.

Unlike Sculptor's terminal-agent menu, a broken registration file is a
hard error at load — a plan referencing it must fail at run start, not
be silently skipped.
"""

import os
import re
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import model_validator

from coordinator.manifest import ManifestError
from coordinator.manifest import PlanManifest
from coordinator.manifest import TaskSpec

PROMPT_PLACEHOLDER = "{prompt}"
MODEL_PLACEHOLDER = "{model}"
ALLOWED_PLACEHOLDERS = frozenset({"{prompt}", "{settings_file}", "{attempt_dir}", "{cwd}", "{model}"})
_PLACEHOLDER_PATTERN = re.compile(r"\{[^}]*\}")


class WorkerRegistration(BaseModel):
    """One registered worker, validated from one YAML file."""

    name: str
    display_name: str
    command: list[str]
    model: str | None = None
    env: dict[str, str] = {}

    @model_validator(mode="after")
    def _validate_placeholders(self) -> "WorkerRegistration":
        for field_name, values in (("command", self.command), ("env", list(self.env.values()))):
            unknown = sorted(
                {
                    token
                    for value in values
                    for token in _PLACEHOLDER_PATTERN.findall(value)
                    if token not in ALLOWED_PLACEHOLDERS
                }
            )
            if unknown:
                raise ValueError(
                    f"{field_name} contains unsupported placeholder(s) {unknown}; "
                    f"allowed: {', '.join(sorted(ALLOWED_PLACEHOLDERS))}"
                )
        prompt_count = sum(element.count(PROMPT_PLACEHOLDER) for element in self.command)
        if prompt_count != 1:
            raise ValueError(f"command must contain {PROMPT_PLACEHOLDER} exactly once, found {prompt_count}")
        uses_model = any(MODEL_PLACEHOLDER in value for value in [*self.command, *self.env.values()])
        if uses_model and self.model is None:
            raise ValueError(f"command uses {MODEL_PLACEHOLDER} but the registration sets no model")
        return self


def render(
    registration: WorkerRegistration,
    *,
    prompt: str,
    settings_file: str,
    attempt_dir: str,
    cwd: str,
) -> tuple[list[str], dict[str, str]]:
    """Render the argv template and extra env for one attempt.

    Substitution is a single regex pass per element, so placeholder-like
    text inside a substituted value (e.g. braces in the prompt) is left
    alone rather than re-expanded.
    """
    values = {
        "{prompt}": prompt,
        "{settings_file}": settings_file,
        "{attempt_dir}": attempt_dir,
        "{cwd}": cwd,
        "{model}": registration.model or "",
    }

    def substitute(text: str) -> str:
        return _PLACEHOLDER_PATTERN.sub(lambda match: values[match.group(0)], text)

    argv = [substitute(element) for element in registration.command]
    env = {key: substitute(value) for key, value in registration.env.items()}
    return argv, env


def user_workers_dir() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "coordinator" / "workers"


def repo_workers_dir(repo_root: Path) -> Path:
    return repo_root / ".sculptor" / "workers"


def _load_yaml_registration(name: str, text: str, source: str, problems: list[str]) -> WorkerRegistration | None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        problems.append(f"{source}: invalid YAML: {e}")
        return None
    if not isinstance(data, dict):
        problems.append(f"{source}: registration must be a YAML mapping, got {type(data).__name__}")
        return None
    try:
        return WorkerRegistration(name=name, **data)
    except (ValidationError, TypeError) as e:
        problems.append(f"{source}: {e}")
        return None


def load_registrations(repo_root: Path) -> dict[str, WorkerRegistration]:
    """Load all registrations, later layers overriding earlier by name.

    Raises :class:`ManifestError` listing every broken file.
    """
    problems: list[str] = []
    registrations: dict[str, WorkerRegistration] = {}

    builtin_dir = resources.files("coordinator") / "data" / "workers"
    for entry in sorted(builtin_dir.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".yaml"):
            registration = _load_yaml_registration(
                Path(entry.name).stem, entry.read_text(), f"built-in {entry.name}", problems
            )
            if registration is not None:
                registrations[registration.name] = registration

    for directory in (user_workers_dir(), repo_workers_dir(repo_root)):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.yaml")):
            registration = _load_yaml_registration(path.stem, path.read_text(), str(path), problems)
            if registration is not None:
                registrations[registration.name] = registration

    if problems:
        raise ManifestError(problems)
    return registrations


def resolve_worker(manifest: PlanManifest, task_spec: TaskSpec, registrations: dict[str, WorkerRegistration]) -> str:
    """The registration name for a task: per-task override, else the default."""
    name = task_spec.worker or manifest.defaults.worker
    if name not in registrations:
        raise ManifestError(
            [f"task {task_spec.id}: unknown worker registration {name!r}; known: {', '.join(sorted(registrations))}"]
        )
    return name
