"""Regression tests for line/scatter/bar/hist rendering, added before
Phase 3b's SERIES_RENDERERS rewiring (chart_editor.py had if/elif
branches for these but no dedicated artist-level tests -- only vector
and fit had one, see test_chart_editor_vector_rendering.py /
test_chart_editor_fit_rendering.py). These pin today's actual rendered
output so the rewiring in this same task can be verified not to have
changed it.
"""
import sys

import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style import BarSeriesStyle, HistSeriesStyle, LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset():
    project = Project(name="Series Type Render Project")
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 3, 1, 4, 3]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _editor_for(project, chart):
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()
    return editor


def test_line_chart_draws_a_line_with_style_fields():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(color="#ff0000", line_width=3.0), label="Series 1",
    )

    editor = _editor_for(project, chart)

    lines = editor.chart_canvas.axes.lines
    assert len(lines) == 1
    assert lines[0].get_color() == "#ff0000"
    assert lines[0].get_linewidth() == 3.0
    assert lines[0].get_label() == "Series 1"


def test_scatter_chart_draws_a_scatter_collection():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Scatter Chart", chart_type="scatter")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=ScatterSeriesStyle(color="#00ff00"), label="Series 1",
    )

    editor = _editor_for(project, chart)

    from matplotlib.collections import PathCollection
    scatters = [c for c in editor.chart_canvas.axes.collections if isinstance(c, PathCollection)]
    assert len(scatters) == 1
    assert scatters[0].get_label() == "Series 1"


def test_bar_chart_draws_bars_with_color():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Bar Chart", chart_type="bar")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=BarSeriesStyle(color="#0000ff"), label="Series 1",
    )

    editor = _editor_for(project, chart)

    assert len(editor.chart_canvas.axes.patches) == 5  # one Rectangle per bar


def test_hist_chart_draws_bins_with_color():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Hist Chart", chart_type="hist")
    chart.config["hist_bins"] = 3
    chart.add_data_series(
        dataset.id, y_column_id=dataset.column_id("y"),
        style=HistSeriesStyle(color="#ffaa00"), label="Series 1",
    )

    editor = _editor_for(project, chart)

    assert len(editor.chart_canvas.axes.patches) == 3


def test_line_chart_with_fill_enabled_draws_a_fill():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(color="#123456", fill_enabled=True, fill_color="#654321", fill_alpha=0.5),
    )

    editor = _editor_for(project, chart)

    assert len(editor.chart_canvas.axes.collections) == 1


def test_line_chart_with_fill_to_index_fills_between_the_two_curves():
    """Regression test for the final-review fix routing fill_base/
    fill_to_index through the derived LineSeriesStyle instead of reading
    them off the raw DataSeries in _resolve_fill_baseline. Uses two series
    with clearly different, non-constant y-values so a baseline of the
    literal fill_base=0.0 default would produce different fill geometry
    than genuinely interpolating series 2's curve -- this checks the fill
    polygon actually reaches up to series 2's y-values, not just down to 0.
    """
    _qapp()
    project = Project(name="Fill To Index Project")
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "y1": [10, 11, 9, 12, 10],
        "y2": [20, 22, 19, 23, 21],
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)

    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y1"),
        style=LineSeriesStyle(color="#123456", fill_enabled=True, fill_to_index=1), label="Series 1",
    )
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y2"),
        style=LineSeriesStyle(color="#654321"), label="Series 2",
    )

    editor = _editor_for(project, chart)

    fills = editor.chart_canvas.axes.collections
    assert len(fills) == 1

    # The fill polygon's vertices should span from series 1's y-values up to
    # series 2's y-values, not down to the fill_base default of 0.0.
    vertices = fills[0].get_paths()[0].vertices
    max_y = vertices[:, 1].max()
    min_y = vertices[:, 1].min()
    assert min_y >= 5  # nowhere near the unused fill_base=0.0 baseline
    assert max_y >= 19  # reaches up toward series 2's y-values


def test_line_chart_with_fill_range_restricts_fill_to_the_x_subrange():
    """#280: fill_range_enabled/min/max should mask the fill to just the
    x in [fill_range_min, fill_range_max] segment, not the whole series."""
    _qapp()
    project, dataset = _project_and_dataset()  # x: 1..5
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(color="#123456", fill_enabled=True,
                               fill_range_enabled=True, fill_range_min=2, fill_range_max=4),
    )

    editor = _editor_for(project, chart)

    fills = editor.chart_canvas.axes.collections
    assert len(fills) == 1
    vertices = fills[0].get_paths()[0].vertices
    assert vertices[:, 0].min() >= 2
    assert vertices[:, 0].max() <= 4


def test_line_chart_with_fill_range_disabled_fills_the_whole_series():
    """Sanity check: fill_range_min/max are ignored unless fill_range_enabled
    is set, so an untouched (default) LineSeriesStyle still fills fully."""
    _qapp()
    project, dataset = _project_and_dataset()  # x: 1..5
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(color="#123456", fill_enabled=True,
                               fill_range_min=2, fill_range_max=4),
    )

    editor = _editor_for(project, chart)

    vertices = editor.chart_canvas.axes.collections[0].get_paths()[0].vertices
    assert vertices[:, 0].min() <= 1
    assert vertices[:, 0].max() >= 5


def test_switching_chart_type_after_creation_still_renders():
    """Regression test: changing an existing chart's type via
    Chart.set_chart_type must not leave any series' .style mismatched
    with the new type -- chart_editor.py's renderer would otherwise
    raise AttributeError trying to read a field the old style class
    doesn't declare, and render a silently empty chart."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(color="#112233"), label="Series 1",
    )

    chart.set_chart_type("bar")

    editor = _editor_for(project, chart)

    assert len(editor.chart_canvas.axes.patches) == 5  # one Rectangle per bar (5 x-values)


def test_renderer_dispatch_uses_each_series_own_type_not_the_chart_type():
    """A chart whose nominal type is "line" but whose one series was
    deliberately constructed with series_type=SeriesType.BAR must render
    using the bar renderer -- proving dispatch reads the series' own
    type. Not yet reachable through the UI (that's Phase 4c), but the
    underlying dispatch must already be wired correctly."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Mixed Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        label="Series 1", series_type=SeriesType.BAR,
    )

    editor = _editor_for(project, chart)

    assert len(editor.chart_canvas.axes.patches) == 5  # bar renderer draws Rectangles
    assert len(editor.chart_canvas.axes.lines) == 0    # NOT the line renderer


def test_error_bars_gating_uses_each_series_own_type_not_the_chart_type():
    """A hist-typed chart (which never supports error bars at the chart
    level) containing a line-typed series (which does) must still draw
    that series' error bars -- proving the gate reads the series' own
    type, not the chart's."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Mixed Chart", chart_type="hist")
    series = chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        label="Series 1", series_type=SeriesType.LINE,
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("y"))),
    )
    assert series.has_error_data

    editor = _editor_for(project, chart)

    from matplotlib.container import ErrorbarContainer
    error_containers = [c for c in editor.chart_canvas.axes.containers if isinstance(c, ErrorbarContainer)]
    assert len(error_containers) == 1


def test_error_bars_are_drawn_behind_the_series_not_on_top_of_it():
    """Regression test: error bars must render underneath the series'
    own marker/line, not obscure it. Neither the error-bar errorbar()
    call nor the line renderer sets an explicit zorder, so matplotlib
    falls back to insertion order for artists at the same default
    zorder (a documented, stable rule, not an implementation detail) --
    drawing error bars first is what puts them behind. axes.lines lists
    every Line2D artist (the series' own line AND the errorbar's cap/bar
    lines are all Line2D) in the order each was added to the axes."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="C", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        label="Series 1", series_type=SeriesType.LINE,
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("y"))),
    )

    editor = _editor_for(project, chart)

    from matplotlib.container import ErrorbarContainer
    axes = editor.chart_canvas.axes
    error_container = next(c for c in axes.containers if isinstance(c, ErrorbarContainer))
    # ErrorbarContainer.lines is (data_line, caplines, barlinecols):
    # data_line is None (fmt="none" -- no connecting line drawn), caplines
    # are the Line2D cap markers (what actually shows up in axes.lines
    # alongside the series' own plotted line), barlinecols are the error
    # bar segments themselves as a LineCollection (in axes.collections,
    # not axes.lines).
    _data_line, caplines, _barlinecols = error_container.lines
    assert caplines, "expected error-bar cap lines to exist"

    series_line = next(line for line in axes.lines if line not in caplines)
    cap_indices = [axes.lines.index(cap) for cap in caplines]
    series_line_index = axes.lines.index(series_line)

    assert all(i < series_line_index for i in cap_indices), (
        "error-bar cap lines must be added to the axes BEFORE the series' "
        "own line, so they draw underneath it"
    )
