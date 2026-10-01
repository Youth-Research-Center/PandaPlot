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


def test_a_negative_value_is_reported_instead_of_drawing_a_misleading_pie():
    editor, _, _ = _pie_editor(values=[3, -2, 1])

    assert _wedges(editor) == []
    assert "no plottable data" in editor.status_label.text()
