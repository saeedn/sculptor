"""Plan manifest (``plan.yaml``) schema, parsing, and validation.

A plan folder contains human-readable task files plus one ``plan.yaml``
holding the DAG. The coordinator parses only the manifest; workers read
only the task files. This module is the coordinator's public contract —
the Plan skill emits manifests matching this schema and humans may
hand-edit them.

Full schema (version 1):

.. code-block:: yaml

    version: 1                       # required; must be 1
    defaults:
      worker: claude-print           # worker registration name
      escalation_worker: claude-print-opus   # optional
      reviewer: claude-print-opus    # optional; worker used by agentic
                                     # review gates (defaults to the
                                     # node's worker)
      attempts: 2                    # base attempts before escalation; >= 1
      verification:                  # commands run by the mechanical gate
        - just format
        - just check
        - just test-unit
      process_doc: process.md        # optional; overrides the built-in
                                     # per-task process document
    phases:
      - id: 1
        name: Core executor
        review: agentic              # phase-boundary review: agentic|human|none
        tasks:
          - id: "1.2"
            file: 01_02_manifest_parser.md   # relative to the plan folder
            deps: ["1.1"]            # task ids this task depends on
            kind: task               # task|spec|mock|architect|plan|review|gate
                                     # (only "task" executes in increment 1)
            worker: claude-opus      # optional per-task override
            gates: [mechanical, agentic]     # optional per-task override;
                                             # allowed: mechanical|agentic|human
            attempts: 3              # optional per-task override; >= 1
            no_change: false         # true for tasks expected to not commit

Validation collects every problem into one :class:`ManifestError` so a
hand-edited manifest gets a full report, not just the first failure.
Cycle detection and worker-registration resolution are deliberately not
done here — they happen at run start (DAG construction and registration
loading respectively).
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import field_validator

ALLOWED_GATES = ("mechanical", "agentic", "human")
ALLOWED_PHASE_REVIEWS = ("agentic", "human", "none")
# Reserved node kinds for later increments; increment 1 executes only "task".
TASK_KINDS = ("task", "spec", "mock", "architect", "plan", "review", "gate")


class ManifestError(Exception):
    """Raised by ``load_manifest`` with every problem found in the manifest."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


def _coerce_scalar_to_str(value: Any) -> Any:
    # YAML parses an unquoted 1.2 as a float and an unquoted 1 as an int;
    # task ids are strings, so coerce scalars rather than reject them.
    if isinstance(value, (int, float)):
        return str(value)
    return value


class ManifestDefaults(BaseModel):
    worker: str
    escalation_worker: str | None = None
    reviewer: str | None = None
    attempts: int = 2
    verification: list[str]
    process_doc: str | None = None


class TaskSpec(BaseModel):
    id: str
    file: str
    deps: list[str] = []
    kind: str = "task"
    worker: str | None = None
    gates: list[str] | None = None
    attempts: int | None = None
    no_change: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: Any) -> Any:
        return _coerce_scalar_to_str(value)

    @field_validator("deps", mode="before")
    @classmethod
    def _coerce_deps(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [_coerce_scalar_to_str(entry) for entry in value]
        return value


class PhaseSpec(BaseModel):
    id: int | str
    name: str
    review: str = "agentic"
    tasks: list[TaskSpec]


class PlanManifest(BaseModel):
    version: int
    defaults: ManifestDefaults
    phases: list[PhaseSpec]


def _format_pydantic_errors(error: ValidationError) -> list[str]:
    problems = []
    for entry in error.errors():
        location = ".".join(str(part) for part in entry["loc"])
        problems.append(f"{location}: {entry['msg']}")
    return problems


def _validate_task_file(task: TaskSpec, plan_dir: Path, problems: list[str]) -> None:
    file_path = Path(task.file)
    if file_path.is_absolute():
        problems.append(f"task {task.id}: file must be relative to the plan folder, got absolute path {task.file!r}")
        return
    resolved = (plan_dir / file_path).resolve()
    if not resolved.is_relative_to(plan_dir.resolve()):
        problems.append(f"task {task.id}: file {task.file!r} escapes the plan folder")
        return
    if not resolved.is_file():
        problems.append(f"task {task.id}: file {task.file!r} does not exist in {plan_dir}")


def _validate_manifest(manifest: PlanManifest, plan_dir: Path) -> list[str]:
    problems: list[str] = []
    if manifest.version != 1:
        problems.append(f"version: must be 1, got {manifest.version}")
    if manifest.defaults.attempts < 1:
        problems.append(f"defaults.attempts: must be >= 1, got {manifest.defaults.attempts}")

    all_task_ids: set[str] = set()
    seen_duplicates: set[str] = set()
    for phase in manifest.phases:
        for task in phase.tasks:
            if task.id in all_task_ids and task.id not in seen_duplicates:
                problems.append(f"task {task.id}: duplicate task id")
                seen_duplicates.add(task.id)
            all_task_ids.add(task.id)

    for phase in manifest.phases:
        if phase.review not in ALLOWED_PHASE_REVIEWS:
            problems.append(
                f"phase {phase.id}: review must be one of {', '.join(ALLOWED_PHASE_REVIEWS)}, got {phase.review!r}"
            )
        for task in phase.tasks:
            for dep in task.deps:
                if dep not in all_task_ids:
                    problems.append(f"task {task.id}: dep {dep!r} does not reference an existing task id")
            if task.kind not in TASK_KINDS:
                problems.append(f"task {task.id}: kind must be one of {', '.join(TASK_KINDS)}, got {task.kind!r}")
            if task.gates is not None:
                for gate in task.gates:
                    if gate not in ALLOWED_GATES:
                        problems.append(
                            f"task {task.id}: gate must be one of {', '.join(ALLOWED_GATES)}, got {gate!r}"
                        )
            if task.attempts is not None and task.attempts < 1:
                problems.append(f"task {task.id}: attempts must be >= 1, got {task.attempts}")
            _validate_task_file(task, plan_dir, problems)
    return problems


def load_manifest(plan_dir: Path) -> PlanManifest:
    """Load and validate ``<plan_dir>/plan.yaml``.

    Raises :class:`ManifestError` carrying every problem found.
    """
    manifest_path = plan_dir / "plan.yaml"
    if not manifest_path.is_file():
        raise ManifestError([f"manifest not found: {manifest_path}"])
    try:
        data = yaml.safe_load(manifest_path.read_text())
    except yaml.YAMLError as e:
        raise ManifestError([f"invalid YAML in {manifest_path}: {e}"])
    if not isinstance(data, dict):
        raise ManifestError([f"manifest must be a YAML mapping, got {type(data).__name__}"])
    try:
        manifest = PlanManifest.model_validate(data)
    except ValidationError as e:
        raise ManifestError(_format_pydantic_errors(e))
    problems = _validate_manifest(manifest, plan_dir)
    if problems:
        raise ManifestError(problems)
    return manifest
