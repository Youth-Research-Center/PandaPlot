"""Widget-level tests for Stacked Bar rendering (#396) through the real
ChartEditorWidget.update_chart() pass: the one place where the running
stack is created and shared across every series' render call.

Follows the same helper-function pattern as test_chart_editor_3d_rendering.py.
"""
import sys

import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget, compute_axis_data_range
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset():
    project = Project(name="Stacked Bar Project")
    df = pd.DataFrame({
        "x": [1, 2, 3],
        "a": [1.0, 2.0, 3.0],
        "b": [10.0, 20.0, 30.0],
        "c": [100.0, 200.0, 300.0],
        "err": [0.5, 0.5, 0.5],
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _series(dataset, y, series_type=SeriesType.STACKED_BAR, **kwargs) -> DataSeries:
    return DataSeries(
        dataset_id=dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id(y),
        label=y, series_type=series_type, style=build_series_style(series_type, error_bars=kwargs.pop("error_bars", None)),
        **kwargs,
    )


def _editor_for(project, chart):
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    return ChartEditorWidget(app_context=app_context, chart=chart, parent=None)


def _bar_extents(axes) -> list[list[tuple[float, float]]]:
    """Per bar container (one per bar series, in draw order), each bar's
    (bottom, height)."""
    from matplotlib.container import BarContainer
    return [
        [(patch.get_y(), patch.get_height()) for patch in container]
        for container in axes.containers if isinstance(container, BarContainer)
    ]


def _stacked_chart(dataset, *columns) -> Chart:
    chart = Chart(name="Stacked", chart_type=ChartType.STACKED_BAR)
    for column in columns:
        chart.data_series.append(_series(dataset, column))
    return chart


def test_three_stacked_series_each_start_where_the_previous_one_ended():
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _stacked_chart(dataset, "a", "b", "c"))

    editor.update_chart()

    assert editor.status_label.text() == "Ready"
    assert _bar_extents(editor.chart_canvas.axes) == [
        [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)],
        [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)],
        [(11.0, 100.0), (22.0, 200.0), (33.0, 300.0)],
    ]


def test_rerendering_does_not_stack_on_the_previous_render():
    """The stack lives for one update_chart() pass -- were it kept on the
    widget, every refresh would draw the bars higher than the last."""
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _stacked_chart(dataset, "a", "b"))

    editor.update_chart()
    editor.update_chart()

    assert _bar_extents(editor.chart_canvas.axes) == [
        [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)],
        [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)],
    ]


def test_a_scatter_overlay_neither_stacks_nor_breaks_the_stack():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _stacked_chart(dataset, "a")
    chart.data_series.append(_series(dataset, "c", series_type=SeriesType.SCATTER))
    chart.data_series.append(_series(dataset, "b"))
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert _bar_extents(editor.chart_canvas.axes)[1] == [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)]


def test_a_secondary_axis_series_stacks_separately_from_the_primary_axis():
    """Different Y axes have different scales, so a series moved to the
    secondary axis must start from its own zero."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _stacked_chart(dataset, "a")
    chart.data_series.append(_series(dataset, "b", y_axis=YAxis.SECONDARY))
    chart.data_series.append(_series(dataset, "c", y_axis=YAxis.SECONDARY))
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert _bar_extents(editor.chart_canvas.axes) == [[(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]]
    assert _bar_extents(editor.chart_canvas.axes2) == [
        [(0.0, 10.0), (0.0, 20.0), (0.0, 30.0)],
        [(10.0, 100.0), (20.0, 200.0), (30.0, 300.0)],
    ]


def test_error_bars_are_centered_on_the_top_of_each_stacked_segment():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _stacked_chart(dataset, "a")
    chart.data_series.append(_series(dataset, "b", error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("err"))))
    editor = _editor_for(project, chart)

    editor.update_chart()

    from matplotlib.container import ErrorbarContainer
    (errorbar,) = [c for c in editor.chart_canvas.axes.containers if isinstance(c, ErrorbarContainer)]
    (y_lines,) = errorbar.lines[2]
    centers = [(x0, (y0 + y1) / 2) for (x0, y0), (_x1, y1) in y_lines.get_segments()]
    assert centers == [(1.0, 11.0), (2.0, 22.0), (3.0, 33.0)]
    # ...and the bars themselves still stack normally after the error bars
    # were placed (placing them must not advance the stack on its own).
    assert _bar_extents(editor.chart_canvas.axes)[1] == [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)]


def test_the_axes_tab_y_range_reaches_the_top_of_the_stack():
    """Seeding a Manual Y range from the raw values alone would clip every
    stacked bar above the tallest single series."""
    project, dataset = _project_and_dataset()
    chart = _stacked_chart(dataset, "a", "b", "c")

    assert compute_axis_data_range(project, chart.data_series, "y") == (1.0, 333.0)
