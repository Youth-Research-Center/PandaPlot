"""Tests for AddSeriesCommand."""
import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart import AddSeriesCommand
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_style.scatter import ScatterSeriesStyle
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries


def _make_app_context_with_chart(chart_type: str):
    chart = Chart(name="Test Chart", chart_type=chart_type)

    project = Mock()
    project.find_item.return_value = chart

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


@pytest.fixture
def app_context_with_chart():
    return _make_app_context_with_chart("vector")


@pytest.fixture
def app_context_with_line_chart():
    return _make_app_context_with_chart("line")


def test_execute_appends_the_passed_series(app_context_with_chart):
    app_context, chart = app_context_with_chart

    series = DataSeries(
        dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y",
        series_type=SeriesType.VECTOR,
        style=VectorSeriesStyle(vector_color="#112233", u_column_id="col-u",
                                 v_column_id="col-v", magnitude_column_id="col-m"),
    )
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    assert command.execute() is CommandResult.SUCCESS
    assert chart.data_series[-1] is series
    assert command.added_index == 0
    assert series.style.u_column_id == "col-u"
    assert series.style.v_column_id == "col-v"
    assert series.style.magnitude_column_id == "col-m"


def test_execute_with_line_series_style(app_context_with_line_chart):
    app_context, chart = app_context_with_line_chart

    series = DataSeries(
        dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y",
        series_type=SeriesType.LINE,
        style=LineSeriesStyle(color="#112233"),
    )
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    assert command.execute() is CommandResult.SUCCESS
    assert chart.data_series[-1] is series
    assert series.style.color == "#112233"
    assert not hasattr(series.style, "vector_color")


def test_execute_returns_false_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    series = DataSeries(dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y")
    command = AddSeriesCommand(app_context, chart_id="missing", series=series)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert command.added_index is None
    assert "missing" in caplog.text
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_undo_removes_the_added_series(app_context_with_chart):
    app_context, chart = app_context_with_chart
    series = DataSeries(dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y")
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    command.execute()
    assert len(chart.data_series) == 1

    command.undo()
    assert len(chart.data_series) == 0


def test_redo_re_appends_the_same_series_object_without_duplicating(app_context_with_chart):
    """redo() must not delegate to execute() -- calling execute() twice would
    append the same series object twice if redo simply called self.execute().
    A full undo -> redo cycle should leave exactly one occurrence."""
    app_context, chart = app_context_with_chart
    series = DataSeries(dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y")
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    command.execute()
    command.undo()
    assert len(chart.data_series) == 0

    command.redo()
    assert len(chart.data_series) == 1
    assert chart.data_series[-1] is series
    assert command.added_index == 0


def test_redo_appends_series_type_matching_the_original_construction(app_context_with_line_chart):
    app_context, chart = app_context_with_line_chart
    series = DataSeries(
        dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y",
        series_type=SeriesType.SCATTER,
        style=ScatterSeriesStyle(color="#112233"),
    )
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    command.execute()
    command.undo()
    command.redo()

    assert chart.data_series[-1].series_type == SeriesType.SCATTER
    assert chart.data_series[-1].style.color == "#112233"


def test_cleanup_releases_the_added_index(app_context_with_chart):
    app_context, chart = app_context_with_chart
    series = DataSeries(dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y")
    command = AddSeriesCommand(app_context, chart_id=chart.id, series=series)

    command.execute()
    assert command.added_index is not None

    command.cleanup()
    assert command.added_index is None
