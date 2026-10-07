"""ChartEditorWidget integration tests for Density (KDE) charts (#398):
the full update_chart() path through resolve_series_data and
SERIES_RENDERERS, including the per-series degenerate-data message, a Hist
overlay sharing the KDE's normalized Y scale, and the filled-area legend
swatch."""
import sys

import numpy as np
import pandas as pd
import pytest
from matplotlib.collections import PolyCollection
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.series_style import DensitySeriesStyle, HistSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset() -> tuple[Project, Dataset]:
    project = Project(name="Density Render Project")
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "v": rng.normal(loc=10.0, scale=3.0, size=100),
        "const": [7.0] * 100,
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _editor_for(project: Project, chart: Chart) -> ChartEditorWidget:
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()
    return editor


def test_density_chart_draws_a_kde_curve_with_style_fields():
    project, dataset = _project_and_dataset()
    chart = Chart(name="Density", chart_type="density")
    series = chart.add_data_series(
        dataset.id, y_column_id=dataset.column_id("v"),
        style=DensitySeriesStyle(color="#ff0000", line_width=3.0, line_style="dotted"), label="KDE",
    )
    assert series.series_type == SeriesType.DENSITY

    editor = _editor_for(project, chart)

    lines = editor.chart_canvas.axes.lines
    assert len(lines) == 1
    assert lines[0].get_color() == "#ff0000"
    assert lines[0].get_linewidth() == 3.0
    assert lines[0].get_linestyle() == ":"
    assert lines[0].get_label() == "KDE"
    assert np.trapezoid(lines[0].get_ydata(), lines[0].get_xdata()) == pytest.approx(1.0, abs=0.05)
    assert "no plottable data" not in editor.status_label.text()


def test_a_constant_density_series_degrades_to_a_per_series_message():
    """gaussian_kde can't estimate a zero-variance column. That series is
    reported and skipped; the chart's other series still render."""
    project, dataset = _project_and_dataset()
    chart = Chart(name="Density", chart_type="density")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("const"), label="Flat")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"), label="Normal")

    editor = _editor_for(project, chart)

    assert "Flat: no plottable data" in editor.status_label.text()
    assert [line.get_label() for line in editor.chart_canvas.axes.lines] == ["Normal"]


def test_a_hist_series_on_a_density_chart_is_normalized_to_the_kdes_scale():
    project, dataset = _project_and_dataset()
    chart = Chart(name="Density", chart_type="density")
    chart.config["hist_bins"] = 10
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"),
                          series_type=SeriesType.HIST, style=HistSeriesStyle(), label="Hist")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"), label="KDE")

    editor = _editor_for(project, chart)

    axes = editor.chart_canvas.axes
    assert len(axes.patches) == 10
    assert sum(p.get_width() * p.get_height() for p in axes.patches) == pytest.approx(1.0)
    assert len(axes.lines) == 1


def test_a_hist_chart_keeps_raw_counts():
    project, dataset = _project_and_dataset()
    chart = Chart(name="Hist", chart_type="hist")
    chart.config["hist_bins"] = 10
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"))

    editor = _editor_for(project, chart)

    assert sum(p.get_height() for p in editor.chart_canvas.axes.patches) == pytest.approx(100)


def test_a_filled_density_series_gets_a_filled_legend_swatch():
    project, dataset = _project_and_dataset()
    chart = Chart(name="Density", chart_type="density")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"),
                          style=DensitySeriesStyle(fill_enabled=True, fill_alpha=0.4), label="Filled")

    editor = _editor_for(project, chart)

    fill_artist = editor._find_fill_artist_for_series(0)
    assert isinstance(fill_artist, PolyCollection)
    handles, _labels = editor.chart_canvas.axes.get_legend_handles_labels()
    assert editor._add_fill_legend_swatches(handles) == [(handles[0], fill_artist)]


def test_switching_a_hist_chart_to_density_keeps_its_hist_series():
    """HIST is allowed on DENSITY, so the switch is non-destructive."""
    chart = Chart(name="c", chart_type="hist")
    chart.add_data_series("ds", y_column_id="col")

    chart.set_chart_type("density")

    assert chart.data_series[0].series_type == SeriesType.HIST


def test_switching_a_density_chart_to_hist_retypes_its_density_series_keeping_color():
    chart = Chart(name="c", chart_type="density")
    chart.add_data_series("ds", y_column_id="col", style=DensitySeriesStyle(color="#abcdef"))

    chart.set_chart_type("hist")

    assert chart.data_series[0].series_type == SeriesType.HIST
    assert chart.data_series[0].style.color == "#abcdef"
