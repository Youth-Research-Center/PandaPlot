"""Tests for RemoveFitDataCommand execute/undo/redo."""

import logging
from unittest.mock import Mock

import numpy as np
import pytest

from pandaplot.commands.project.chart.remove_fit_data_command import RemoveFitDataCommand
from pandaplot.models.project.items.chart import Chart, FitData


@pytest.fixture
def chart_with_fit():
    chart = Chart(id="chart-1", name="C")
    fit = FitData(
        source_dataset_id="ds-1",
        source_x_column="x",
        source_y_column="y",
        fit_type="linear",
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
    )
    chart.fit_data.append(fit)
    return chart, fit


@pytest.fixture
def app_context_with_chart(chart_with_fit):
    chart, _ = chart_with_fit
    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def test_execute_removes_fit_data(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=0)

    assert command.execute() is True
    assert len(chart.fit_data) == 0


def test_execute_out_of_range_returns_false(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart
    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=5)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert len(chart.fit_data) == 1
    assert "5" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_execute_logs_a_warning_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    command = RemoveFitDataCommand(app_context, chart_id="missing", fit_index=0)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_undo_logs_a_warning_when_nothing_to_undo(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=0)

    with caplog.at_level(logging.WARNING):
        command.undo()
    assert "chart-1" in caplog.text


def test_undo_restores_the_removed_fit(app_context_with_chart, chart_with_fit):
    app_context, chart = app_context_with_chart
    _, original_fit = chart_with_fit

    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=0)
    command.execute()

    command.undo()

    assert len(chart.fit_data) == 1
    restored = chart.fit_data[0]
    assert restored.label == original_fit.label
    assert restored.source_dataset_id == original_fit.source_dataset_id
    np.testing.assert_array_equal(restored.x_data, original_fit.x_data)
    np.testing.assert_array_equal(restored.y_data, original_fit.y_data)


def test_redo_removes_fit_data_again(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=0)

    command.execute()
    command.undo()
    command.redo()

    assert len(chart.fit_data) == 0


def test_undo_restores_the_fit_with_its_typed_style_object_intact(app_context_with_chart):
    from pandaplot.models.chart.fit_style import FitStyle

    app_context, chart = app_context_with_chart
    chart.fit_data[0].style = FitStyle(color="#abcdef", band_fill_enabled=False)
    command = RemoveFitDataCommand(app_context, chart_id="chart-1", fit_index=0)
    command.execute()

    command.undo()

    restored = chart.fit_data[0]
    assert isinstance(restored.style, FitStyle)
    assert restored.style.color == "#abcdef"
    assert restored.style.band_fill_enabled is False
