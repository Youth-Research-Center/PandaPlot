"""Tests that the line and scatter renderers honor the label subset setting."""
from types import SimpleNamespace

from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.gui.components.tabs.chart.series_renderers.scatter import render_scatter_series
from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle

DATA = SimpleNamespace(x_data=[0, 1, 2, 3], y_data=[3.0, 9.0, 1.0, 5.0])  # min at x=2, max at x=1


def test_line_renderer_labels_only_the_min_and_max_points():
    axes = Figure().add_subplot()
    style = LineSeriesStyle(show_value_labels=True, value_label_subset_mode="extremes")

    render_line_series(axes, DATA, style, "s", 1.0, visible=True, extra={})

    assert [annotation.xy for annotation in axes.texts] == [(1, 9.0), (2, 1.0)]


def test_scatter_renderer_labels_only_the_max_point():
    axes = Figure().add_subplot()
    style = ScatterSeriesStyle(show_value_labels=True, value_label_subset_mode="max")

    render_scatter_series(axes, DATA, style, "s", 1.0, visible=True, extra={})

    assert [annotation.xy for annotation in axes.texts] == [(1, 9.0)]
