from coordinator.ladder import AttemptBudget
from coordinator.ladder import AttemptRecordLite
from coordinator.ladder import Exhausted
from coordinator.ladder import FailureRecord
from coordinator.ladder import NextAttempt
from coordinator.ladder import attempt_plan
from coordinator.ladder import format_seed_context
from coordinator.ladder import next_attempt
from coordinator.manifest import ManifestDefaults
from coordinator.manifest import TaskSpec


def defaults(attempts: int = 2, escalation_worker: str | None = "opus-worker") -> ManifestDefaults:
    return ManifestDefaults(worker="w", verification=[], attempts=attempts, escalation_worker=escalation_worker)


def record(index: int, rate_limited: bool = False) -> AttemptRecordLite:
    return AttemptRecordLite(attempt_index=index, registration="w", rate_limited=rate_limited)


def test_attempt_plan_defaults() -> None:
    budget = attempt_plan(TaskSpec(id="1", file="a.md"), defaults())
    assert budget == AttemptBudget(base_count=2, escalation_worker="opus-worker")


def test_attempt_plan_per_task_override() -> None:
    budget = attempt_plan(TaskSpec(id="1", file="a.md", attempts=3), defaults())
    assert budget.base_count == 3


def test_attempt_plan_phase_review_node_uses_defaults() -> None:
    assert attempt_plan(None, defaults(attempts=5)).base_count == 5


def test_ladder_two_plus_one() -> None:
    budget = attempt_plan(TaskSpec(id="1", file="a.md"), defaults())
    assert next_attempt([record(0)], budget) == NextAttempt(escalated=False, registration_override=None)
    assert next_attempt([record(0), record(1)], budget) == NextAttempt(
        escalated=True, registration_override="opus-worker"
    )
    assert next_attempt([record(0), record(1), record(2)], budget) == Exhausted()


def test_ladder_without_escalation_worker() -> None:
    budget = attempt_plan(TaskSpec(id="1", file="a.md"), defaults(escalation_worker=None))
    assert next_attempt([record(0)], budget) == NextAttempt(escalated=False, registration_override=None)
    assert next_attempt([record(0), record(1)], budget) == Exhausted()


def test_rate_limited_attempts_do_not_count() -> None:
    budget = attempt_plan(TaskSpec(id="1", file="a.md"), defaults())
    history = [record(0, rate_limited=True), record(1)]
    assert next_attempt(history, budget) == NextAttempt(escalated=False, registration_override=None)


def failure(index: int, findings: str = "gate failed") -> FailureRecord:
    return FailureRecord(
        attempt_index=index,
        registration="w",
        status="completed",
        findings=findings,
        last_assistant_message=f"message {index}",
    )


def test_seed_context_contains_findings_and_grows() -> None:
    one = format_seed_context([failure(0, "lint broke")])
    assert "Attempt 0" in one
    assert "lint broke" in one
    assert "message 0" in one
    two = format_seed_context([failure(0, "lint broke"), failure(1, "tests broke")])
    assert "Attempt 1" in two
    assert "tests broke" in two
    assert len(two) > len(one)


def test_seed_context_caps_long_excerpts() -> None:
    text = format_seed_context([failure(0, "x" * 10_000)])
    assert "[...truncated]" in text
    assert len(text) < 6_000


def test_discarded_attempts_do_not_count() -> None:
    budget = AttemptBudget(base_count=2, escalation_worker=None)
    history = [
        AttemptRecordLite(attempt_index=0, registration="w", discarded=True),
        AttemptRecordLite(attempt_index=1, registration="w"),
    ]
    decision = next_attempt(history, budget)
    assert isinstance(decision, NextAttempt) and not decision.escalated


def test_per_task_escalation_worker_override() -> None:
    defaults = ManifestDefaults(worker="w", verification=[], attempts=2, escalation_worker="opus")
    task = TaskSpec(id="1.1", file="t.md", escalation_worker="fable")
    budget = attempt_plan(task, defaults)
    assert budget.escalation_worker == "fable"
    assert attempt_plan(None, defaults).escalation_worker == "opus"
