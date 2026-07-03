"""Retry/escalation ladder arithmetic and retry-context formatting.

The ladder: ``defaults.attempts`` base attempts (default 2 — initial +
one seeded retry) on the task's registration, then one escalated
attempt on ``defaults.escalation_worker`` seeded with ALL prior
attempts' failure context. Per-task ``attempts`` overrides the base
count. Rate-limited attempts never burn budget.

Pure arithmetic and string formatting — no journal, no processes.
"""

from dataclasses import dataclass

from coordinator.manifest import ManifestDefaults
from coordinator.manifest import TaskSpec

# Cap per-attempt excerpts in the retry context; full logs stay in the
# attempt dirs.
_EXCERPT_CAP = 2048


@dataclass(frozen=True)
class AttemptBudget:
    base_count: int
    escalation_worker: str | None


@dataclass
class AttemptRecordLite:
    """The slice of attempt history the ladder counts."""

    attempt_index: int
    registration: str | None
    rate_limited: bool = False


@dataclass(frozen=True)
class NextAttempt:
    escalated: bool
    registration_override: str | None


@dataclass(frozen=True)
class Exhausted:
    pass


@dataclass(frozen=True)
class FailureRecord:
    """One failed attempt, as seen by the retry context and the report."""

    attempt_index: int
    registration: str | None
    status: str | None
    findings: str | None
    last_assistant_message: str | None


def attempt_plan(task_spec: TaskSpec | None, defaults: ManifestDefaults) -> AttemptBudget:
    base = defaults.attempts
    if task_spec is not None and task_spec.attempts is not None:
        base = task_spec.attempts
    return AttemptBudget(base_count=base, escalation_worker=defaults.escalation_worker)


def next_attempt(history: list[AttemptRecordLite], budget: AttemptBudget) -> NextAttempt | Exhausted:
    """Decide the next rung after a failure, given the attempts so far."""
    counted = sum(1 for record in history if not record.rate_limited)
    if counted < budget.base_count:
        return NextAttempt(escalated=False, registration_override=None)
    if budget.escalation_worker is not None and counted < budget.base_count + 1:
        return NextAttempt(escalated=True, registration_override=budget.escalation_worker)
    return Exhausted()


def _excerpt(text: str | None) -> str:
    if not text:
        return "(none)"
    if len(text) > _EXCERPT_CAP:
        return text[:_EXCERPT_CAP] + "\n[...truncated]"
    return text


def format_seed_context(failures: list[FailureRecord]) -> str:
    """Markdown retry context for the next attempt's ``context.md``."""
    lines = [
        "# Retry context: prior failed attempts",
        "",
        "This task was attempted before and failed. Do not repeat these mistakes.",
        "",
    ]
    for failure in failures:
        registration = failure.registration or "(unknown worker)"
        lines.append(f"## Attempt {failure.attempt_index} ({registration})")
        if failure.status is not None:
            lines.append(f"- worker status: {failure.status}")
        lines.append("- gate findings:")
        lines.append(_excerpt(failure.findings))
        lines.append("- final worker message:")
        lines.append(_excerpt(failure.last_assistant_message))
        lines.append("")
    return "\n".join(lines)
