"""Regression test: a single fit-data entry must draw exactly one curve.

A botched merge (PR #59, "multiple y axis") left both the old
unconditional `self.chart_canvas.axes.plot(...)` call and the new
axis-aware `fit_axes.plot(...)` call in ChartEditorWidget.update_chart(),
so every fit was rendered twice.
"""
import sys

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _chart_with_one_fit(project, dataset):
    chart = Chart(name="Fit Chart", chart_type="scatter")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A")
    chart.add_fit_series(
        source_dataset_id=dataset.id,
        source_x_column_id=dataset.column_id("x"),
        source_y_column_id=dataset.column_id("y"),
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
        style=FitStyle(color="#ff0000", fit_type="linear"),
    )
    project.add_item(chart)
    return chart


def test_one_fit_draws_exactly_one_line_on_primary_axis():
    _qapp()
    app_context = build_app_context()
    project = Project(name="Fit Render Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = _chart_with_one_fit(project, dataset)
    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    fit_lines = [line for line in editor.chart_canvas.axes.get_lines() if line.get_color() == "#ff0000"]
    assert len(fit_lines) == 1, f"expected 1 line for the fit, got {len(fit_lines)}"


def test_confidence_band_for_a_secondary_axis_fit_is_drawn_on_that_axis():
    _qapp()
    app_context = build_app_context()
    project = Project(name="Fit Render Project 2")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Secondary Fit Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A",
                          y_axis="secondary")
    chart.add_fit_series(
        source_dataset_id=dataset.id,
        source_x_column_id=dataset.column_id("x"),
        source_y_column_id=dataset.column_id("y"),
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
        style=FitStyle(
            color="#00ff00", fit_type="linear",
            confidence_lower=np.array([0.5, 1.5, 2.5]),
            confidence_upper=np.array([1.5, 2.5, 3.5]),
        ),
        y_axis="secondary",
    )
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    assert editor.chart_canvas.axes2 is not None, "secondary axis should have been created"
    assert len(editor.chart_canvas.axes2.collections) == 1, (
        "confidence band should be drawn on the secondary axis, not the primary one"
    )
    assert len(editor.chart_canvas.axes.collections) == 0, (
        "confidence band leaked onto the primary axis"
    )


def test_fit_line_alpha_is_rendered():
    """Regression: FitData.alpha must reach the plotted line -- it used to
    be hardcoded to 1.0 in chart_editor.py regardless of the model value."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Fit Alpha Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Fit Alpha Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A")
    chart.add_fit_series(
        source_dataset_id=dataset.id,
        source_x_column_id=dataset.column_id("x"),
        source_y_column_id=dataset.column_id("y"),
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
        style=FitStyle(color="#ff0000", fit_type="linear"),
        alpha=0.4,
    )
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    fit_lines = [line for line in editor.chart_canvas.axes.get_lines() if line.get_color() == "#ff0000"]
    assert len(fit_lines) == 1
    assert fit_lines[0].get_alpha() == 0.4


def test_band_fill_disabled_draws_no_confidence_band():
    """Regression test for the new opt-out: band_fill_enabled=False must
    suppress the fill_between call even when confidence data exists."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Fit Render Project 2")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Secondary Fit Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A",
                          y_axis="secondary")
    chart.add_fit_series(
        source_dataset_id=dataset.id,
        source_x_column_id=dataset.column_id("x"),
        source_y_column_id=dataset.column_id("y"),
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
        style=FitStyle(
            color="#00ff00", fit_type="linear", band_fill_enabled=False,
            confidence_lower=np.array([0.5, 1.5, 2.5]),
            confidence_upper=np.array([1.5, 2.5, 3.5]),
        ),
        y_axis="secondary",
    )
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    assert editor.chart_canvas.axes2 is not None, "secondary axis should have been created"
    assert len(editor.chart_canvas.axes2.collections) == 0, (
        "band_fill_enabled=False should suppress the confidence band"
    )
    assert len(editor.chart_canvas.axes.collections) == 0  # no band drawn


def test_reordering_a_fit_relative_to_a_plain_series_changes_render_order():
    """Regression/coverage test for the spec's z-order acceptance
    criterion (final-review Important finding #5): "Reordering a FIT
    series relative to other series (drag/move_data_series) changes its
    draw order, verified with a new test." Series later in data_series
    draw on top of earlier ones (Chart.move_data_series's own docstring,
    #189) -- this builds [fit, line], renders, checks draw order, then
    reorders to [line, fit] via move_data_series, re-renders, and confirms
    the artist order actually changed to match."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Fit Z-Order Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Z-Order Chart", chart_type="line")
    chart.add_fit_series(
        source_dataset_id=dataset.id,
        source_x_column_id=dataset.column_id("x"),
        source_y_column_id=dataset.column_id("y"),
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Linear Fit",
        style=FitStyle(color="#ff0000", fit_type="linear"),
    )
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A")
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    colors_before = [line.get_color() for line in editor.chart_canvas.axes.get_lines()]
    assert colors_before[0] == "#ff0000", "fit (index 0) must draw before the plain series"

    assert chart.move_data_series(0, 1) is True
    editor.update_chart()

    colors_after = [line.get_color() for line in editor.chart_canvas.axes.get_lines()]
    assert colors_after[-1] == "#ff0000", (
        "after reordering to [line, fit], the fit must now draw last (on top)"
    )
    assert colors_before != colors_after, "reordering must actually change the render order"


def test_a_fit_without_stored_curve_data_is_skipped_without_breaking_the_chart():
    """PR #416 review: a legacy fit_data entry with no x_data migrates to a
    FIT series with no curve; rendering it used to raise and take the
    whole chart down. Only that entry is skipped now."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Broken Fit Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"),
                          y_column_id=dataset.column_id("y"), label="Series A")
    chart.data_series.append(
        DataSeries(dataset_id=dataset.id, series_type=SeriesType.FIT, style=FitStyle(), label="Broken Fit")
    )
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()

    assert len(editor.chart_canvas.axes.get_lines()) >= 1  # Series A still drawn
    status = editor.status_label.text()
    assert status.startswith("Skipped:")
    assert "Broken Fit" in status
