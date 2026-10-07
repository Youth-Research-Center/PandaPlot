"""Regression tests for #278: a filled/area line series' legend entry should
show a swatch matching the fill color/alpha, not just a plain line -- see
ChartEditorWidget._add_fill_legend_swatches/_find_fill_artist_for_series."""
import sys

import pandas as pd
from matplotlib.collections import PolyCollection
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _make_project_and_chart(*, fill_enabled: bool):
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y1": [4, 5, 6], "y2": [7, 8, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)

    chart = Chart(name="Test Chart", chart_type="line")
    series1 = chart.add_data_series(dataset.id, x_column="x", y_column="y1", label="Filled")
    series1.style.fill_enabled = fill_enabled
    series1.style.fill_color = "#00ff00"
    chart.add_data_series(dataset.id, x_column="x", y_column="y2", label="Plain")
    project.add_item(chart)

    return project, dataset, chart


def test_filled_series_gets_combined_patch_line_legend_handle():
    """_add_fill_legend_swatches (used by update_chart before build_legend)
    should pair the "Filled" series' Line2D handle with its actual fill
    PolyCollection artist, and leave the "Plain" series' handle untouched."""
    _qapp()
    app_ctx = build_app_context()
    project, _dataset, chart = _make_project_and_chart(fill_enabled=True)
    app_ctx.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_ctx, chart=chart, parent=None)

    fill_artist = widget._find_fill_artist_for_series(0)
    assert isinstance(fill_artist, PolyCollection)

    handles, labels = widget.chart_canvas.axes.get_legend_handles_labels()
    augmented = widget._add_fill_legend_swatches(handles)
    by_label = dict(zip(labels, augmented, strict=True))

    assert by_label["Filled"] == (handles[labels.index("Filled")], fill_artist)
    assert by_label["Plain"] == handles[labels.index("Plain")]
    assert not isinstance(by_label["Plain"], tuple)

    # And build_legend/axes.legend() accepts the augmented list without error.
    legend = widget.chart_canvas.axes.get_legend()
    assert legend is not None


def test_unfilled_series_keeps_plain_line_legend_handle():
    _qapp()
    app_ctx = build_app_context()
    project, _dataset, chart = _make_project_and_chart(fill_enabled=False)
    app_ctx.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_ctx, chart=chart, parent=None)

    assert widget._find_fill_artist_for_series(0) is None

    handles, _labels = widget.chart_canvas.axes.get_legend_handles_labels()
    augmented = widget._add_fill_legend_swatches(handles)
    assert augmented == handles
    assert all(not isinstance(h, tuple) for h in augmented)
