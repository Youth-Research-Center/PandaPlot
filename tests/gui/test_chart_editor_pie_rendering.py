"""Full ChartEditorWidget rendering of a Pie chart (#397)."""
import sys

import pandas as pd
from matplotlib.patches import Wedge
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget, resolve_series_data
from pandaplot.models.chart.series_style import PieSeriesStyle
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _pie_editor(*, label_column: str | None = "fruit", values: list | None = None):
    _qapp()
    app_context = build_app_context()
    project = Project(name="Pie Render Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({
        "fruit": ["apple", "pear", "plum"],
        "count": values if values is not None else [3, 2, 1],
    }))
    project.add_item(dataset)
    app_context.app_state.load_project(project)

    chart = Chart(name="Pie Chart", chart_type="pie")
    chart.add_data_series(
        dataset.id, y_column_id=dataset.column_id("count"), series_type="pie", label="Fruit",
        style=PieSeriesStyle(label_column_id=dataset.column_id(label_column) if label_column else ""),
    )
    project.add_item(chart)

    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()
    return editor, chart, project


def _wedges(editor):
    return [patch for patch in editor.chart_canvas.axes.patches if isinstance(patch, Wedge)]


def test_pie_chart_draws_one_wedge_per_row():
    editor, _, _ = _pie_editor()

    assert len(_wedges(editor)) == 3


def test_pie_label_column_resolves_to_label_data():
    _, chart, project = _pie_editor()

    data = resolve_series_data(project, chart.data_series[0])

    assert data.error is None
    assert list(data.label_data) == ["apple", "pear", "plum"]
    assert data.x_data is None


def test_a_blank_label_column_leaves_the_pie_unlabeled_instead_of_failing_it():
    editor, chart, project = _pie_editor(label_column=None)

    assert resolve_series_data(project, chart.data_series[0]).label_data is None
    assert len(_wedges(editor)) == 3
    assert "Skipped" not in editor.status_label.text()


def test_the_legend_lists_the_wedge_labels():
    editor, _, _ = _pie_editor()

    legend = editor.chart_canvas.axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["apple", "pear", "plum"]


def test_a_pie_chart_draws_no_axes_but_keeps_its_title():
    """A pie has no scale, ticks, spines or grid -- every axis artist is
    turned off at once -- but the title (a figure-level concern) stays."""
    editor, chart, _ = _pie_editor()
    chart.config.x.show_grid = True
    chart.config.y.show_grid = True
    chart.config.subtitle = "by count"
    editor.update_chart()

    axes = editor.chart_canvas.axes
    assert axes.axison is False
    assert editor.chart_canvas.fig._suptitle.get_text() == "Pie Chart"
    assert axes.get_title() == "by count"


def test_a_pie_ignores_stored_manual_limits_and_log_scale():
    """The Axes tab hides itself for a pie, but a config carrying a manual
    range or log scale (e.g. from a hand-edited file) must not crop or
    distort the circle."""
    editor, chart, _ = _pie_editor()
    chart.config.x.auto_limits = False
    chart.config.x.min, chart.config.x.max = 0.0, 0.1
    chart.config.y.scale = "log"
    editor.update_chart()

    axes = editor.chart_canvas.axes
    assert axes.get_xlim()[0] < -1.0 < 1.0 < axes.get_xlim()[1]
    assert axes.get_yscale() == "linear"


def test_a_pie_never_builds_a_secondary_y_axis():
    editor, chart, _ = _pie_editor()
    chart.data_series[0].y_axis = "secondary"
    editor.update_chart()

    assert editor.chart_canvas.axes2 is None
    assert len(_wedges(editor)) == 3


def test_an_emptied_pie_switched_to_a_line_chart_gets_its_frame_and_aspect_back():
    """Axes.pie() turns the frame off and locks an equal aspect, and
    Axes.clear() undoes neither."""
    editor, chart, _ = _pie_editor()
    chart.data_series.clear()
    chart.set_chart_type("line")
    editor.update_chart()

    axes = editor.chart_canvas.axes
    assert axes.axison is True
    assert axes.get_frame_on() is True
    assert axes.get_aspect() == "auto"


def test_a_negative_value_is_reported_instead_of_drawing_a_misleading_pie():
    editor, _, _ = _pie_editor(values=[3, -2, 1])

    assert _wedges(editor) == []
    assert "no plottable data" in editor.status_label.text()
