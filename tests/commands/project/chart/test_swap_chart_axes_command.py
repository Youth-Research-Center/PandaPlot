"""Tests for SwapChartAxesCommand (#266)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.swap_chart_axes_command import SwapChartAxesCommand
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis


@pytest.fixture
def app_context_with_chart():
    chart = Chart(name="Test Chart", chart_type="line")
    chart.data_series.append(DataSeries(dataset_id="ds1", x_column_id="cx", y_column_id="cy"))
    chart.config.x.label = "X title"
    chart.config.y.label = "Y title"

    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def _columns(chart):
    series = chart.data_series[0]
    return series.x_column_id, series.y_column_id, chart.config.x.label, chart.config.y.label


def test_execute_swaps_and_emits_chart_updated(app_context_with_chart):
    app_context, chart = app_context_with_chart

    command = SwapChartAxesCommand(app_context, chart_id=chart.id)
    assert command.execute() is CommandResult.SUCCESS

    assert _columns(chart) == ("cy", "cx", "Y title", "X title")
    event_type, event_data = app_context.event_bus.emit.call_args.args
    assert event_type == ChartEvents.CHART_UPDATED
    assert event_data["chart_id"] == chart.id
    assert event_data["chart"] is chart
    assert event_data["update_type"] == "axes_swapped"


def test_undo_restores_and_redo_swaps_again(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = SwapChartAxesCommand(app_context, chart_id=chart.id)
    command.execute()

    assert command.undo() is CommandResult.SUCCESS
    assert _columns(chart) == ("cx", "cy", "X title", "Y title")

    assert command.redo() is CommandResult.SUCCESS
    assert _columns(chart) == ("cy", "cx", "Y title", "X title")
    assert app_context.event_bus.emit.call_count == 3


def test_execute_fails_with_a_message_when_the_chart_cannot_be_swapped(app_context_with_chart):
    app_context, chart = app_context_with_chart
    chart.data_series[0].y_axis = YAxis.SECONDARY

    command = SwapChartAxesCommand(app_context, chart_id=chart.id)
    assert command.execute() is CommandResult.FAILURE

    assert _columns(chart) == ("cx", "cy", "X title", "Y title")
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.event_bus.emit.assert_not_called()


def test_execute_fails_when_the_chart_is_missing(app_context_with_chart):
    app_context, chart = app_context_with_chart
    app_context.get_app_state.return_value.current_project.find_item.return_value = None

    command = SwapChartAxesCommand(app_context, chart_id=chart.id)
    assert command.execute() is CommandResult.FAILURE
    app_context.event_bus.emit.assert_not_called()


def test_undo_aborts_when_the_chart_can_no_longer_be_swapped(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = SwapChartAxesCommand(app_context, chart_id=chart.id)
    command.execute()
    chart.data_series[0].y_axis = YAxis.SECONDARY

    assert command.undo() is CommandResult.ABORTED
    assert command.redo() is CommandResult.ABORTED
    assert chart.data_series[0].x_column_id == "cy"
