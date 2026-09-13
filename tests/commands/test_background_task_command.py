"""Unit tests for BackgroundTaskCommand base class."""

from unittest.mock import Mock

import pytest

from pandaplot.commands.background_task_command import BackgroundTaskCommand
from pandaplot.commands.base_command import CommandResult
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from tests.commands.project.conftest import SyncTaskScheduler


class DummyBackgroundTaskCommand(BackgroundTaskCommand):
    def execute(self) -> CommandResult:
        return CommandResult.SUCCESS


def test_default_command_properties():
    cmd = DummyBackgroundTaskCommand()
    assert cmd.occupies_undo_slot() is False
    assert cmd.marks_project_modified() is False
    assert cmd.undo() is CommandResult.SUCCESS
    assert cmd.redo() is CommandResult.SUCCESS


def test_notify_complete():
    outcomes = []
    cmd = DummyBackgroundTaskCommand(on_complete=outcomes.append)
    cmd._notify_complete(CommandResult.SUCCESS)
    assert outcomes == [CommandResult.SUCCESS]

    # No error when on_complete is None
    cmd_none = DummyBackgroundTaskCommand(on_complete=None)
    cmd_none._notify_complete(CommandResult.FAILURE)


def test_project_staleness_tracking():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    p1 = Project(name="P1")
    p2 = Project(name="P2")

    app_state.current_project = p1
    app_context.get_app_state.return_value = app_state

    cmd = DummyBackgroundTaskCommand()
    cmd._capture_dispatch_project(app_context)
    assert cmd._is_project_stale(app_context) is False

    # Switch project
    app_state.current_project = p2
    assert cmd._is_project_stale(app_context) is True


def test_run_task_safely():
    # Successful execution returning non-None
    outcome = BackgroundTaskCommand._run_task_safely(lambda x: x * 2, 5)
    assert outcome == {"success": True, "result": 10, "error": None}

    # Execution returning None
    outcome_none = BackgroundTaskCommand._run_task_safely(lambda: None)
    assert outcome_none["success"] is False
    assert outcome_none["result"] is None
    assert "returned no result" in outcome_none["error"]

    # Exception raised
    def _failing():
        raise ValueError("computation failed")

    outcome_err = BackgroundTaskCommand._run_task_safely(_failing)
    assert outcome_err["success"] is False
    assert outcome_err["result"] is None
    assert "computation failed" in outcome_err["error"]


def test_dispatch_task_lifecycle():
    scheduler = SyncTaskScheduler()
    cmd = DummyBackgroundTaskCommand()

    results = []
    finished_called = []

    def task(progress_callback):
        return "done"

    def _on_result(res):
        results.append(res)

    def _on_finished():
        finished_called.append(True)

    assert cmd._is_running is False
    cmd._dispatch_task(
        scheduler,
        task=task,
        on_result=_on_result,
        on_finished=_on_finished,
    )

    # SyncTaskScheduler runs inline and finishes
    assert results == ["done"]
    assert finished_called == [True]
    assert cmd._is_running is False


def test_dispatch_task_resets_is_running_before_calling_on_finished():
    """The re-entrancy guard must already be clear by the time on_finished
    runs, so a callback that dispatches a follow-up execution isn't rejected
    as re-entrant."""
    scheduler = SyncTaskScheduler()
    cmd = DummyBackgroundTaskCommand()

    is_running_during_callback = []

    def task(progress_callback):
        return "done"

    def _on_finished():
        is_running_during_callback.append(cmd._is_running)

    cmd._dispatch_task(scheduler, task=task, on_finished=_on_finished)

    assert is_running_during_callback == [False]


def test_dispatch_task_resets_is_running_on_synchronous_dispatch_failure():
    """task_scheduler.run_task() can raise synchronously (e.g. reserved
    task_arguments keys) before ever scheduling the task -- _is_running must
    not be left stuck at True in that case, or every later execute() call is
    permanently rejected as re-entrant."""
    scheduler = SyncTaskScheduler()
    cmd = DummyBackgroundTaskCommand()

    def task(progress_callback, cancellation_token):
        return "done"

    assert cmd._is_running is False
    with pytest.raises(ValueError):
        cmd._dispatch_task(scheduler, task=task, task_arguments={"cancellation_token": None})

    assert cmd._is_running is False
