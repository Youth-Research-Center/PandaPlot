"""Rendering a series' twin Y column (#402): the (x, y1, y2) shape, with y1 on
the series' own Y axis and y2 on the opposite one."""
import sys

import numpy as np
import pandas as pd
from matplotlib.collections import PathCollection, PolyCollection
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import (
    ChartEditorWidget,
    compute_axis_data_range,
    resolve_series_data,
)
from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, YAxis
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset():
    project = Project(name="Twin Y Project")
    df = pd.DataFrame({"t": [1, 2, 3], "temp": [20.0, 22.0, 21.0], "pressure": [1000.0, 1010.0, 990.0]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _twin_chart(dataset, *, y_axis=YAxis.PRIMARY, series_type=SeriesType.LINE, style=None) -> Chart:
    chart = Chart(name="Twin", chart_type="line")
    if style is None:
        style_cls = LineSeriesStyle if series_type == SeriesType.LINE else ScatterSeriesStyle
        style = style_cls(color="#ff0000", twin_y_column_id=dataset.column_id("pressure"))
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("t"), y_column_id=dataset.column_id("temp"),
        label="Weather", y_axis=y_axis, series_type=series_type, style=style,
    )
    return chart


def _editor_for(project, chart):
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()
    return editor


def test_resolve_series_data_returns_the_twin_y_values():
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset)

    data = resolve_series_data(project, chart.data_series[0])

    assert data.error is None
    pd.testing.assert_series_equal(data.twin_y_data, dataset.data["pressure"])


def test_a_stale_twin_y_column_is_ignored_rather_than_failing_the_series():
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset, style=LineSeriesStyle(twin_y_column_id="missing-id", twin_y_column="gone"))

    data = resolve_series_data(project, chart.data_series[0])

    assert data.error is None
    assert data.twin_y_data is None
    pd.testing.assert_series_equal(data.y_data, dataset.data["temp"])


def test_line_series_draws_y_on_primary_and_twin_on_secondary_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset)

    editor = _editor_for(project, chart)

    canvas = editor.chart_canvas
    assert canvas.axes2 is not None
    assert len(canvas.axes.lines) == 1
    assert len(canvas.axes2.lines) == 1
    primary, twin = canvas.axes.lines[0], canvas.axes2.lines[0]
    np.testing.assert_array_equal(primary.get_ydata(), [20.0, 22.0, 21.0])
    np.testing.assert_array_equal(twin.get_ydata(), [1000.0, 1010.0, 990.0])
    np.testing.assert_array_equal(twin.get_xdata(), primary.get_xdata())
    assert twin.get_color() == "#ff0000"
    assert primary.get_label() == "Weather"
    assert twin.get_label() == "Weather (Y₂)"


def test_series_on_secondary_axis_draws_its_twin_on_the_primary_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset, y_axis=YAxis.SECONDARY)

    editor = _editor_for(project, chart)

    canvas = editor.chart_canvas
    np.testing.assert_array_equal(canvas.axes2.lines[0].get_ydata(), [20.0, 22.0, 21.0])
    np.testing.assert_array_equal(canvas.axes.lines[0].get_ydata(), [1000.0, 1010.0, 990.0])
    assert canvas.axes.lines[0].get_label() == "Weather (Y₁)"


def test_scatter_series_draws_its_twin_points_on_the_secondary_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset, series_type=SeriesType.SCATTER)

    editor = _editor_for(project, chart)

    twin_points = [c for c in editor.chart_canvas.axes2.collections if isinstance(c, PathCollection)]
    assert len(twin_points) == 1
    np.testing.assert_array_equal(twin_points[0].get_offsets()[:, 1], [1000.0, 1010.0, 990.0])


def test_twin_trace_is_mapped_to_its_series_for_click_selection():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset)

    editor = _editor_for(project, chart)

    assert editor._artist_series_map[editor.chart_canvas.axes2.lines[0]] == 0


def test_twin_trace_skips_the_series_area_fill():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset, style=LineSeriesStyle(
        fill_enabled=True, twin_y_column_id=dataset.column_id("pressure")))

    editor = _editor_for(project, chart)

    assert any(isinstance(c, PolyCollection) for c in editor.chart_canvas.axes.collections)
    assert not any(isinstance(c, PolyCollection) for c in editor.chart_canvas.axes2.collections)
    assert chart.data_series[0].style.fill_enabled is True


def test_clearing_the_twin_y_column_removes_the_secondary_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset)
    editor = _editor_for(project, chart)
    assert editor.chart_canvas.axes2 is not None

    chart.data_series[0].style.twin_y_column_id = ""
    editor.update_chart()

    assert editor.chart_canvas.axes2 is None
    assert len(editor.chart_canvas.axes.lines) == 1


def test_axis_ranges_put_the_twin_values_on_the_opposite_axis():
    project, dataset = _project_and_dataset()
    series = _twin_chart(dataset).data_series

    assert compute_axis_data_range(project, series, "y") == (20.0, 22.0)
    assert compute_axis_data_range(project, series, "y2") == (990.0, 1010.0)
    assert compute_axis_data_range(project, series, "x") == (1.0, 3.0)


def test_axis_ranges_follow_a_series_moved_to_the_secondary_axis():
    project, dataset = _project_and_dataset()
    series = _twin_chart(dataset, y_axis=YAxis.SECONDARY).data_series

    assert compute_axis_data_range(project, series, "y") == (990.0, 1010.0)
    assert compute_axis_data_range(project, series, "y2") == (20.0, 22.0)


def test_a_stale_twin_y_column_does_not_create_an_empty_secondary_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(dataset, style=LineSeriesStyle(twin_y_column_id="missing-id", twin_y_column="gone"))

    editor = _editor_for(project, chart)

    assert editor.chart_canvas.axes2 is None
    assert len(editor.chart_canvas.axes.lines) == 1


def test_a_stale_twin_y_column_keeps_the_secondary_axis_for_a_secondary_series():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _twin_chart(
        dataset, y_axis=YAxis.SECONDARY, style=LineSeriesStyle(twin_y_column_id="missing-id", twin_y_column="gone"))

    editor = _editor_for(project, chart)

    assert editor.chart_canvas.axes2 is not None
    assert len(editor.chart_canvas.axes2.lines) == 1
