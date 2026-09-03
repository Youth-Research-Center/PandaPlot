"""Tests for RemoveSeriesCommand."""
import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.remove_series_command import RemoveSeriesCommand
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries


@pytest.fixture
def app_context_with_chart():
    chart = Chart(name="Test Chart", chart_type="line")

    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def test_undo_restores_series_with_style_as_dataclass_instance(app_context_with_chart):
    """Regression test: execute() captures a series via copy.deepcopy(),
    which preserves series.style as a typed dataclass instance (unlike the
    old asdict()-then-reconstruct path, which flattened style into a plain
    dict on the way out). undo() must restore that same typed instance. A
    plain-dict `.style` would blow up the next Chart.to_dict() call, since
    it does dataclasses.asdict(series.style)."""
    app_context, chart = app_context_with_chart
    chart.data_series.append(
        DataSeries(
            dataset_id="ds1",
            x_column="x",
            y_column="y",
            series_type=SeriesType.LINE,
            style=LineSeriesStyle(color="#112233"),
        )
    )

    command = RemoveSeriesCommand(app_context, chart_id=chart.id, series_index=0)
    assert command.execute() is CommandResult.SUCCESS
    assert len(chart.data_series) == 0

    command.undo()
    assert len(chart.data_series) == 1

    restored = chart.data_series[0]
    assert isinstance(restored.style, LineSeriesStyle)
    assert restored.style.color == "#112233"

    # Must not raise -- this is the exact crash the bug report describes:
    # execute -> undo -> to_dict (e.g. on save).
    data = chart.to_dict()
    assert data["data_series"][0]["style"]["color"] == "#112233"


def test_redo_after_undo_removes_series_again(app_context_with_chart):
    app_context, chart = app_context_with_chart
    chart.data_series.append(
        DataSeries(
            dataset_id="ds1",
            x_column="x",
            y_column="y",
            series_type=SeriesType.LINE,
            style=LineSeriesStyle(),
        )
    )

    command = RemoveSeriesCommand(app_context, chart_id=chart.id, series_index=0)
    command.execute()
    command.undo()
    command.redo()
    assert len(chart.data_series) == 0


def test_execute_logs_a_warning_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    command = RemoveSeriesCommand(app_context, chart_id="missing", series_index=0)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_execute_logs_a_warning_when_series_index_out_of_range(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = RemoveSeriesCommand(app_context, chart_id=chart.id, series_index=5)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "5" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_undo_logs_a_warning_when_nothing_to_undo(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart

    command = RemoveSeriesCommand(app_context, chart_id=chart.id, series_index=0)

    with caplog.at_level(logging.WARNING):
        command.undo()
    assert chart.id in caplog.text


def test_cleanup_releases_the_removed_series_data_snapshot(app_context_with_chart):
    app_context, chart = app_context_with_chart
    chart.data_series.append(
        DataSeries(
            dataset_id="ds1",
            x_column="x",
            y_column="y",
            series_type=SeriesType.LINE,
            style=LineSeriesStyle(),
        )
    )

    command = RemoveSeriesCommand(app_context, chart_id=chart.id, series_index=0)
    command.execute()
    assert command.removed_series_data is not None

    command.cleanup()
    assert command.removed_series_data is None
