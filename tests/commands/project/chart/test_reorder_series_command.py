"""Tests for ReorderSeriesCommand (#189)."""
import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.chart.reorder_series_command import ReorderSeriesCommand
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries


@pytest.fixture
def app_context_with_chart():
    chart = Chart(name="Test Chart", chart_type="line")
    for label in ("A", "B", "C"):
        chart.data_series.append(
            DataSeries(
                dataset_id="ds1", x_column="x", y_column="y",
                series_type=SeriesType.LINE, style=LineSeriesStyle(), label=label,
            )
        )

    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def _labels(chart):
    return [s.label for s in chart.data_series]


def test_execute_moves_the_series_to_the_new_position(app_context_with_chart):
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=0, to_index=2)
    assert command.execute() is True

    assert _labels(chart) == ["B", "C", "A"]


def test_execute_emits_chart_updated_with_series_reordered(app_context_with_chart):
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=0, to_index=1)
    command.execute()

    app_context.event_bus.emit.assert_called_once()
    event_type, event_data = app_context.event_bus.emit.call_args.args
    assert event_data["update_type"] == "series_reordered"
    assert event_data["chart_id"] == chart.id


def test_undo_restores_the_original_order(app_context_with_chart):
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=0, to_index=2)
    command.execute()
    assert _labels(chart) == ["B", "C", "A"]

    command.undo()
    assert _labels(chart) == ["A", "B", "C"]


def test_undo_restores_original_order_for_an_adjacent_move(app_context_with_chart):
    """The move-up/move-down UI actions only ever request an adjacent
    step -- a pop-then-insert of one step is exactly a swap of the two
    adjacent positions, so undo (which re-runs the move with from/to
    swapped) must land back on the exact original order."""
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=1, to_index=2)
    command.execute()
    assert _labels(chart) == ["A", "C", "B"]

    command.undo()
    assert _labels(chart) == ["A", "B", "C"]


def test_redo_after_undo_reorders_again(app_context_with_chart):
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=0, to_index=2)
    command.execute()
    command.undo()
    command.redo()

    assert _labels(chart) == ["B", "C", "A"]


def test_execute_logs_a_warning_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    command = ReorderSeriesCommand(app_context, chart_id="missing", from_index=0, to_index=1)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_execute_logs_a_warning_when_index_out_of_range(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = ReorderSeriesCommand(app_context, chart_id=chart.id, from_index=0, to_index=5)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert _labels(chart) == ["A", "B", "C"]
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
