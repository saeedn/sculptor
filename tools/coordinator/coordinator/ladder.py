"""Retry/escalation ladder arithmetic and retry-context formatting.

The ladder: ``defaults.attempts`` base attempts (default 2 — initial +
one seeded retry) on the task's registration, then one escalated
attempt on ``defaults.escalation_worker`` seeded with ALL prior
attempts' failure context. Per-task ``attempts`` overrides the base
count. Rate-limited attempts never burn budget.

Pure arithmetic and string formatting — no journal, no processes.
"""

from pydantic import BaseModel
from pydantic import ConfigDict

from coordinator.manifest import ManifestDefaults
from coordinator.manifest import TaskSpec

# Cap per-attempt excerpts in the retry context; full logs stay in the
# attempt dirs.
_EXCERPT_CAP = 2048


class AttemptBudget(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_count: int
    escalation_worker: str | None


class AttemptRecordLite(BaseModel):
    """The slice of attempt history the ladder counts.

    Mutable: ``rate_limited``/``discarded`` are set after construction,
    when the attempt's fate becomes known.
    """

    attempt_index: int
    registration: str | None
    # Neither burns budget: rate-limited attempts are the provider's
    # fault, discarded ones never ran to a verdict (crash/pause mid-flight).
    rate_limited: bool = False
    discarded: bool = False


class NextAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    escalated: bool
    registration_override: str | None


class Exhausted(BaseModel):
    model_config = ConfigDict(frozen=True)


class FailureRecord(BaseModel):
    """One failed attempt, as seen by the retry context and the report."""

    model_config = ConfigDict(frozen=True)

    attempt_index: int
    registration: str | None
    status: str | None
    findings: str | None
    last_assistant_message: str | None


def attempt_plan(task_spec: TaskSpec | None, defaults: ManifestDefaults) -> AttemptBudget:
    base = defaults.attempts
    escalation = defaults.escalation_worker
    if task_spec is not None:
        if task_spec.attempts is not None:
            base = task_spec.attempts
        if task_spec.escalation_worker is not None:
            escalation = task_spec.escalation_worker
    return AttemptBudget(base_count=base, escalation_worker=escalation)


def next_attempt(history: list[AttemptRecordLite], budget: AttemptBudget) -> NextAttempt | Exhausted:
    """Decide the next rung after a failure, given the attempts so far."""
    counted = sum(1 for record in history if not record.rate_limited and not record.discarded)
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
