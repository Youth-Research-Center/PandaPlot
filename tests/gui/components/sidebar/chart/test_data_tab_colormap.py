"""Tests for DataTab's Colormap/Heatmap chart-type support (Z column)."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.series_style.colormap import ColormapSeriesStyle
from pandaplot.models.chart.series_style.heatmap import HeatmapSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _app_context_with_project():
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [0, 1], "y": [0, 1], "z": [10.0, 20.0]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    return app_context, project, dataset


def test_z_column_hidden_for_a_line_chart():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.z_column_combo.isVisible() is False


def test_z_column_shown_and_populated_for_a_heatmap_series():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Heatmap Chart", chart_type="heatmap")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(z_column_id=dataset.column_id("z")),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()

    assert tab.z_column_combo.isVisible() is True
    assert tab.z_column_combo.currentData() == dataset.column_id("z")


def test_editing_z_column_updates_the_series():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Heatmap Chart", chart_type="heatmap")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=SeriesType.HEATMAP,
        style=HeatmapSeriesStyle(z_column_id=dataset.column_id("z")),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    z_index = tab.z_column_combo.findData(dataset.column_id("x"))
    tab.z_column_combo.setCurrentIndex(z_index)

    assert chart.data_series[0].style.z_column_id == dataset.column_id("x")


def test_apply_to_does_not_create_a_colormap_series_on_an_empty_chart():
    """apply_to only re-asserts existing series fields; a series comes from + Add series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Colormap Chart", chart_type="colormap")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._on_dataset_changed()
    tab.z_column_combo.setCurrentIndex(tab.z_column_combo.findData(dataset.column_id("z")))

    tab.apply_to(chart)

    assert chart.data_series == []


def test_z_column_hidden_for_a_non_z_series_on_a_vector_typed_chart():
    """A LINE series left on a chart that switched to "vector" (Vector's
    spec allows {VECTOR, LINE}, so set_chart_type leaves it untouched --
    unlike Colormap/Heatmap, whose spec allows only their own series type)
    must NOT show the Z field when selected -- driven by the series' own
    type, not the chart's (mirrors the equivalent Vector regression test)."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Mixed Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.set_chart_type("vector")
    assert chart.data_series[0].series_type == SeriesType.LINE  # sanity: still LINE

    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()

    assert tab.z_column_combo.isVisible() is False


def test_retyping_an_existing_series_to_colormap_shows_and_populates_z_column_combo():
    """Regression test for the shared reload path in _on_series_type_changed:
    retyping an existing (non-Colormap) series via the Series Type combo
    must reveal and populate the Z column combo, mirroring how retyping to
    VECTOR reveals U/V (test_retyping_an_existing_series_to_vector_does_not_
    default_uv_to_the_same_real_column in test_data_tab_vector.py)."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Bar Chart", chart_type="bar")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.set_chart_type("colormap")
    assert chart.data_series[0].series_type == SeriesType.COLORMAP  # bar isn't in colormap's allowed set

    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()

    assert tab.z_column_combo.isVisible() is True
    assert tab.z_column_combo.count() > 1
    assert tab.z_column_combo.currentData() == ""


def test_apply_to_writes_z_column_id_for_colormap_style_object():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Colormap Chart", chart_type="colormap")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=SeriesType.COLORMAP,
        style=ColormapSeriesStyle(),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    z_index = tab.z_column_combo.findData(dataset.column_id("z"))
    tab.z_column_combo.setCurrentIndex(z_index)
    tab.apply_to(chart)

    assert chart.data_series[0].style.z_column_id == dataset.column_id("z")
