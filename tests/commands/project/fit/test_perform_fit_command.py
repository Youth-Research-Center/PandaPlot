"""Tests for PerformFitCommand execute, undo, and redo."""

from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.fit.perform_fit_command import PerformFitCommand
from pandaplot.utils.errors import UserFacingError
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


def test_marks_project_modified_is_false(fit_service, task_scheduler):
    """Regression (PR #235 review): this command computes a fit preview
    only and never mutates project state, so it must not flag the project
    as having unsaved changes."""
    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
        task_scheduler=task_scheduler,
    )
    assert command.marks_project_modified() is False


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


def _failing_command(fit_service, task_scheduler, exception, *, fit_type="linear"):
    fit_service.perform_fit.side_effect = exception
    outcomes = []
    command = PerformFitCommand(
        fit_service=fit_service, fit_type=fit_type, x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler, on_complete=outcomes.append,
    )
    assert command.execute() is CommandResult.SUCCESS  # dispatched
    assert outcomes == [CommandResult.FAILURE]
    return command


def test_scipy_non_convergence_becomes_a_plain_reason(fit_service, task_scheduler):
    command = _failing_command(
        fit_service, task_scheduler, RuntimeError("Optimal parameters not found: Number of calls to function has reached maxfev = 800."),
    )

    description = command.error_description
    assert description is not None
    assert description.reason == "The fit did not converge for this data. Try another model or a narrower X range."
    assert description.details == ""
    assert "Optimal parameters" not in description.reason
    assert "starting values" not in description.reason


def test_custom_fit_non_convergence_mentions_starting_values(fit_service, task_scheduler):
    command = _failing_command(
        fit_service, task_scheduler, RuntimeError("Optimal parameters not found: maxfev"), fit_type="Custom Function",
    )

    assert command.error_description is not None
    assert command.error_description.reason == (
        "The fit did not converge for this data. Try other starting values, another model or a narrower X range."
    )


def test_nan_or_inf_data_becomes_a_plain_reason(fit_service, task_scheduler):
    command = _failing_command(fit_service, task_scheduler, ValueError("array must not contain infs or NaNs"))

    assert command.error_description is not None
    assert command.error_description.reason == "The selected data contains empty or infinite values that the fit cannot use."


def test_other_errors_are_described_by_the_shared_rules(fit_service, task_scheduler):
    command = _failing_command(fit_service, task_scheduler, ValueError("bad params"))

    assert command.error_description is not None
    assert command.error_description.reason == "PandaPlot could not process this data with these settings."
    assert command.error_description.details == "ValueError: bad params"
    assert command.error_message == "bad params"


def test_error_description_is_cleared_after_a_successful_fit(fit_service, fit_result, task_scheduler):
    command = _failing_command(fit_service, task_scheduler, RuntimeError("Optimal parameters not found"))
    assert command.error_description is not None

    fit_service.perform_fit.side_effect = None
    fit_service.perform_fit.return_value = fit_result
    assert command.redo() is CommandResult.SUCCESS

    assert command.error_description is None
    assert command.error_message is None


def test_worker_error_signal_sets_a_description(fit_service, task_scheduler):
    outcomes = []
    command = PerformFitCommand(
        fit_service=fit_service, fit_type="linear", x_data=[1, 2, 3], y_data=[2, 4, 6],
        task_scheduler=task_scheduler, on_complete=outcomes.append,
    )

    command._on_fit_error((UserFacingError, UserFacingError("The fit did not converge for this data."), None))

    assert outcomes == [CommandResult.FAILURE]
    assert command.error_description is not None
    assert command.error_description.reason == "The fit did not converge for this data."
    assert command.result is None
