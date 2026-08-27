"""Tests for PerformFitCommand execute, undo, and redo."""

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.fit.perform_fit_command import PerformFitCommand


@pytest.fixture
def fit_service():
    return Mock()


@pytest.fixture
def fit_result():
    return Mock()


def test_execute_performs_fit(fit_service, fit_result):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
    )

    assert command.execute() is True
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
    )


def test_execute_logs_a_warning_when_fit_service_returns_no_result(fit_service, caplog):
    fit_service.perform_fit.return_value = None

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
    )

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "linear" in caplog.text


def test_cleanup_clears_fit_result(fit_service, fit_result):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
    )
    command.execute()
    assert command.result is fit_result

    command.cleanup()

    assert command.result is None


def test_undo_clears_fit_result(fit_service, fit_result):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
    )

    command.execute()
    assert command.result is fit_result

    assert command.undo() is True
    assert command.result is None


def test_redo_performs_fit_again(fit_service, fit_result):
    fit_service.perform_fit.return_value = fit_result

    command = PerformFitCommand(
        fit_service=fit_service,
        fit_type="linear",
        x_data=[1, 2, 3],
        y_data=[2, 4, 6],
    )

    command.execute()
    command.undo()

    assert command.result is None
    assert fit_service.perform_fit.call_count == 1

    assert command.redo() is True

    assert command.result is fit_result
    assert fit_service.perform_fit.call_count == 2
