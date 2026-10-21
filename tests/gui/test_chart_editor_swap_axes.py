"""Tests for the chart editor's "Swap X/Y" toolbar action (#266)."""
import sys

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _make_editor():
    _qapp()
    app_ctx = build_app_context()
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"t": [1.0, 2.0, 3.0], "v": [10.0, 20.0, 30.0]}))
    project.add_item(dataset)
    chart = Chart(name="Test Chart", chart_type="line")
    series = chart.add_data_series(dataset.id, x_column="t", y_column="v", label="Series")
    series.style.fill_enabled = True
    chart.config.x.label = "Time"
    chart.config.y.label = "Voltage"
    project.add_item(chart)
    app_ctx.app_state.load_project(project)
    return app_ctx, chart, ChartEditorWidget(app_context=app_ctx, chart=chart, parent=None)


def test_swap_action_swaps_the_rendered_axes_and_is_undoable():
    app_ctx, chart, widget = _make_editor()

    widget._on_swap_axes()
    assert widget.status_label.text() == "Swapped X and Y ✓"
    widget.update_chart()

    line = widget.chart_canvas.axes.get_lines()[0]
    np.testing.assert_array_equal(line.get_xdata(), [10.0, 20.0, 30.0])
    np.testing.assert_array_equal(line.get_ydata(), [1.0, 2.0, 3.0])
    assert widget.chart_canvas.axes.get_xlabel() == "Voltage"

    app_ctx.command_executor.undo()
    assert chart.data_series[0].x_column == "t"
    assert chart.config.x.label == "Time"


def test_swap_action_reports_why_a_chart_cannot_be_swapped():
    _app_ctx, chart, widget = _make_editor()
    chart.data_series[0].y_axis = YAxis.SECONDARY

    widget._on_swap_axes()

    assert "secondary Y axis" in widget.status_label.text()
    assert chart.data_series[0].x_column == "t"


def test_swap_action_is_hidden_on_chart_types_that_cannot_be_swapped():
    _app_ctx, chart, widget = _make_editor()
    assert widget._swap_axes_action.isVisible()

    chart.chart_type = ChartType.PIE
    widget.update_chart()

    assert not widget._swap_axes_action.isVisible()


def test_swap_action_draws_a_fit_band_horizontally_after_the_swap():
    _app_ctx, chart, widget = _make_editor()
    chart.data_series.append(DataSeries(
        dataset_id=chart.data_series[0].dataset_id, series_type=SeriesType.FIT,
        style=FitStyle(confidence_lower=np.array([0.5, 1.5]), confidence_upper=np.array([1.5, 2.5])),
        precomputed_x_data=np.array([0.0, 1.0]), precomputed_y_data=np.array([1.0, 2.0]),
    ))

    widget._on_swap_axes()
    assert widget.status_label.text() == "Swapped X and Y ✓"
    widget.update_chart()

    band = widget.chart_canvas.axes.collections[-1]
    vertices = band.get_paths()[0].vertices
    assert vertices[:, 1].min() == 0.0
    assert vertices[:, 1].max() == 1.0
