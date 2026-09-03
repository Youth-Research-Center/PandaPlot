"""Tests for PerformFitCommand execute, undo, and redo."""

from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.fit.perform_fit_command import PerformFitCommand

from tests.commands.project.conftest import SyncTaskScheduler


@pytest.fixture
def fit_service():
    return Mock()


@pytest.fixture
def fit_result():
    return Mock()


@pytest.fixture
def task_scheduler():
    return SyncTaskScheduler()


def test_execute_performs_fit(fit_service, fit_result, task_scheduler):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )

    assert command.execute() is CommandResult.SUCCESS
    assert command.result is fit_result

    fit_service.perform_fit.assert_called_once_with(
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
        fit_points=500,
        calculate_r_squared=True,
        confidence_bands=False,
        sigma_y=None,
        custom_function=None,
        custom_parameters=None,
        fixed_parameters=None,
        x_min=None,
        x_max=None,
    )


def test_execute_logs_a_warning_when_fit_service_returns_no_result(fit_service, task_scheduler, caplog):
    import logging

    fit_service.perform_fit.return_value = None

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.SUCCESS  # dispatched
    assert command.result is None
    assert "linear" in caplog.text


def test_execute_forwards_custom_range_to_fit_service(fit_service, fit_result, task_scheduler):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
        x_min=-10.0,
        x_max=20.0,
        task_scheduler=task_scheduler,
    )

    assert command.execute() is CommandResult.SUCCESS

    _, kwargs = fit_service.perform_fit.call_args
    assert kwargs["x_min"] == -10.0
    assert kwargs["x_max"] == 20.0


def test_cleanup_clears_fit_result(fit_service, fit_result, task_scheduler):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )
    command.execute()
    assert command.result is fit_result

    command.cleanup()

    assert command.result is None


def test_undo_clears_fit_result(fit_service, fit_result, task_scheduler):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )

    command.execute()
    assert command.result is fit_result

    assert command.undo() is CommandResult.SUCCESS
    assert command.result is None


def test_redo_performs_fit_again(fit_service, fit_result, task_scheduler):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )

    command.execute()
    command.undo()

    assert command.result is None
    assert fit_service.perform_fit.call_count == 1

    assert command.redo() is CommandResult.SUCCESS

    assert command.result is fit_result
    assert fit_service.perform_fit.call_count == 2


def test_occupies_no_undo_slot(fit_service, task_scheduler):
    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )
    assert command.occupies_undo_slot() is False


def test_execute_fails_fast_when_already_running(fit_service, task_scheduler):
    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )
    command._is_running = True

    assert command.execute() is CommandResult.FAILURE


def test_on_complete_reports_failure_on_exception(fit_service, task_scheduler):
    fit_service.perform_fit.side_effect = ValueError("bad params")
    outcomes = []

    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler, on_complete=outcomes.append,
    )

    assert command.execute() is CommandResult.SUCCESS  # dispatched
    assert outcomes == [CommandResult.FAILURE]
    assert command.error_message == "bad params"
