"""Tests for ApplyChartPropertiesCommand undo/redo with a pre-captured baseline."""

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.chart import ApplyChartPropertiesCommand
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.project.items.chart import Chart, snapshot_chart_state


@pytest.fixture
def app_context_with_chart():
    chart = Chart(name="Chart")
    chart.add_data_series("ds1", "x", "y", style=LineSeriesStyle(color="#112233"))

    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def test_undo_restores_provided_baseline_snapshot(app_context_with_chart):
    app_context, chart = app_context_with_chart
    baseline = snapshot_chart_state(chart)

    # Simulate the live edits the panel makes before Apply is clicked
    chart.config["x_label"] = "live edited"
    chart.data_series[0].style.color = "#ffffff"

    command = ApplyChartPropertiesCommand(
        app_context, chart.id, apply_fn=lambda c: None, old_snapshot=baseline)
    assert command.execute() is True

    command.undo()
    assert chart.config["x_label"] == ""
    assert chart.data_series[0].style.color == "#112233"


def test_redo_reapplies_the_edited_state(app_context_with_chart):
    app_context, chart = app_context_with_chart
    baseline = snapshot_chart_state(chart)
    chart.config["x_label"] = "live edited"

    command = ApplyChartPropertiesCommand(
        app_context, chart.id, apply_fn=lambda c: None, old_snapshot=baseline)
    command.execute()
    command.undo()
    command.redo()
    assert chart.config["x_label"] == "live edited"


def test_execute_without_baseline_snapshots_at_execute_time(app_context_with_chart):
    app_context, chart = app_context_with_chart

    def apply_fn(c):
        c.config["x_label"] = "applied"

    command = ApplyChartPropertiesCommand(app_context, chart.id, apply_fn=apply_fn)
    command.execute()

    command.undo()
    assert chart.config["x_label"] == ""
    command.redo()
    assert chart.config["x_label"] == "applied"


def test_execute_logs_a_warning_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    command = ApplyChartPropertiesCommand(app_context, "missing", apply_fn=lambda c: None)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_undo_logs_a_warning_when_nothing_to_undo(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = ApplyChartPropertiesCommand(app_context, chart.id, apply_fn=lambda c: None)

    with caplog.at_level(logging.WARNING):
        command.undo()
    assert chart.id in caplog.text


def test_redo_logs_a_warning_when_nothing_to_redo(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = ApplyChartPropertiesCommand(app_context, chart.id, apply_fn=lambda c: None)

    with caplog.at_level(logging.WARNING):
        command.redo()
    assert chart.id in caplog.text
