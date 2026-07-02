"""Tests for CodingAgentTaskView.status for terminal agents."""

from sculptor.config.settings import SculptorSettings
from sculptor.database.models import AgentTaskInputsV2
from sculptor.database.models import AgentTaskStateV2
from sculptor.database.models import Task
from sculptor.database.models import TaskID
from sculptor.interfaces.agents.agent import EnvironmentAcquiredRunnerMessage
from sculptor.interfaces.agents.agent import TerminalAgentConfig
from sculptor.interfaces.agents.agent import TerminalAgentSignalRunnerMessage
from sculptor.interfaces.agents.agent import TerminalStatusSignal
from sculptor.interfaces.agents.tasks import TaskState
from sculptor.primitives.ids import AgentMessageID
from sculptor.primitives.ids import OrganizationReference
from sculptor.primitives.ids import ProjectID
from sculptor.primitives.ids import UserReference
from sculptor.primitives.ids import WorkspaceID
from sculptor.web.derived import CodingAgentTaskView
from sculptor.web.derived import TaskStatus
from sculptor.web.derived import create_initial_task_view
from sculptor.web.derived import is_agent_busy_or_waiting


def _make_task_view(task: Task) -> CodingAgentTaskView:
    settings = SculptorSettings()
    view = create_initial_task_view(task, settings)
    assert isinstance(view, CodingAgentTaskView)
    view.update_task(task)
    return view


def _make_terminal_task(*, outcome: TaskState = TaskState.RUNNING) -> Task:
    return Task(
        object_id=TaskID(),
        user_reference=UserReference("test-user"),
        organization_reference=OrganizationReference("test-org"),
        project_id=ProjectID(),
        input_data=AgentTaskInputsV2(
            agent_config=TerminalAgentConfig(),
        ),
        current_state=AgentTaskStateV2(workspace_id=WorkspaceID()),
        outcome=outcome,
    )


def test_terminal_task_status_is_building_before_environment() -> None:
    # A prompt-less terminal task with no environment is still building — the
    # "no user message → READY" special case must not apply.
    view = _make_task_view(_make_terminal_task())
    assert view.status == TaskStatus.BUILDING


def test_terminal_task_status_is_ready_after_environment() -> None:
    view = _make_task_view(_make_terminal_task())
    view.add_message(
        EnvironmentAcquiredRunnerMessage.model_construct(
            message_id=AgentMessageID(),
            environment=None,
        )
    )
    assert view.status == TaskStatus.READY


def test_terminal_task_status_outcome_short_circuits_unchanged() -> None:
    assert _make_task_view(_make_terminal_task(outcome=TaskState.QUEUED)).status == TaskStatus.BUILDING
    assert _make_task_view(_make_terminal_task(outcome=TaskState.FAILED)).status == TaskStatus.ERROR
    assert _make_task_view(_make_terminal_task(outcome=TaskState.DELETED)).status == TaskStatus.READY


def _env_acquired() -> EnvironmentAcquiredRunnerMessage:
    return EnvironmentAcquiredRunnerMessage.model_construct(
        message_id=AgentMessageID(),
        environment=None,
    )


def _signal(signal: TerminalStatusSignal) -> TerminalAgentSignalRunnerMessage:
    return TerminalAgentSignalRunnerMessage(signal=signal)


def test_terminal_status_follows_latest_signal_since_run_start() -> None:
    view = _make_task_view(_make_terminal_task())
    view.add_message(_env_acquired())

    view.add_message(_signal(TerminalStatusSignal.BUSY))
    assert view.status == TaskStatus.RUNNING

    view.add_message(_signal(TerminalStatusSignal.WAITING))
    assert view.status == TaskStatus.WAITING

    # Latest wins.
    view.add_message(_signal(TerminalStatusSignal.BUSY))
    assert view.status == TaskStatus.RUNNING

    view.add_message(_signal(TerminalStatusSignal.IDLE))
    assert view.status == TaskStatus.READY


def test_terminal_status_resets_at_each_run_start() -> None:
    # A pre-re-run WAITING must NOT survive the next run's anchor
    # (stale-status risk).
    view = _make_task_view(_make_terminal_task())
    view.add_message(_env_acquired())
    view.add_message(_signal(TerminalStatusSignal.WAITING))
    assert view.status == TaskStatus.WAITING

    view.add_message(_env_acquired())
    assert view.status == TaskStatus.READY

    view.add_message(_signal(TerminalStatusSignal.BUSY))
    assert view.status == TaskStatus.RUNNING


def test_terminal_status_neutral_after_restart_until_signals_re_drive() -> None:
    # Signals are ephemeral: after a backend restart a fresh view only sees
    # persistent messages, so status is BUILDING pre-anchor and neutral READY
    # once the new run acquires its environment.
    view = _make_task_view(_make_terminal_task())
    assert view.status == TaskStatus.BUILDING
    view.add_message(_env_acquired())
    assert view.status == TaskStatus.READY


def test_terminal_status_outcome_short_circuit_beats_signals() -> None:
    view = _make_task_view(_make_terminal_task(outcome=TaskState.FAILED))
    view.add_message(_env_acquired())
    view.add_message(_signal(TerminalStatusSignal.BUSY))
    assert view.status == TaskStatus.ERROR


def test_is_agent_busy_or_waiting_true_for_working_agent() -> None:
    """The CI babysitter's all-idle gate blocks on the agent status the UI shows:
    a busy terminal agent is WORKING, so the predicate is True (busy).

    (Upstream exercised this with a mid-turn chat agent; this fork has no chat
    agent, so a terminal BUSY signal stands in for the WORKING status.)"""
    task = _make_terminal_task()
    messages = [_env_acquired(), _signal(TerminalStatusSignal.BUSY)]
    view = _make_task_view(task)
    for message in messages:
        view.add_message(message)
    assert view.status == TaskStatus.RUNNING
    assert is_agent_busy_or_waiting(task, messages) is True


def test_is_agent_busy_or_waiting_true_for_waiting_agent() -> None:
    """Yellow/waiting (an agent blocked on the user) counts as occupied — the
    babysitter must not inject while a question or plan approval is pending."""
    task = _make_terminal_task()
    messages = [_env_acquired(), _signal(TerminalStatusSignal.WAITING)]
    view = _make_task_view(task)
    for message in messages:
        view.add_message(message)
    assert view.status == TaskStatus.WAITING
    assert is_agent_busy_or_waiting(task, messages) is True


def test_is_agent_busy_or_waiting_false_for_idle_agent() -> None:
    """Just the run-start anchor → READY/IDLE, with no settings or streaming view,
    so the predicate is False and the babysitter may act."""
    task = _make_terminal_task(outcome=TaskState.RUNNING)
    assert is_agent_busy_or_waiting(task, [_env_acquired()]) is False
