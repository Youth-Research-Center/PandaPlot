"""Tests for the Style and Data tabs' handling of the 3-D series types
(issue #98).

The interesting cases are the ones where a 3-D type is deliberately NOT
treated like the color-mapped 2-D types it superficially resembles: every
3-D type picks a Z column, but only Surface/Trisurf take their color from
the chart's shared color map.
"""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.project import Project

_3D_SERIES_TYPES = [
    SeriesType.SCATTER3D, SeriesType.LINE3D, SeriesType.SURFACE,
    SeriesType.WIREFRAME, SeriesType.BAR3D, SeriesType.TRISURF,
]


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab():
    # Qt only reports isVisible() truthfully once a top-level ancestor has
    # been shown -- same pattern as test_style_tab_colormap.py.
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def _series(series_type, label="s1"):
    return DataSeries(dataset_id="ds1", label=label, series_type=series_type,
                       style=build_series_style(series_type))


@pytest.mark.parametrize("series_type", _3D_SERIES_TYPES)
def test_selecting_any_3d_series_never_offers_error_bar_controls(series_type):
    """mplot3d has no errorbar() -- offering the card would be a control
    the renderer silently ignores."""
    tab = _tab()

    tab.set_chart_type(ChartType(series_type.value))
    tab.set_selected("series", _series(series_type))

    assert tab.error_bars_card.isVisible() is False
    assert tab.fill_card.isVisible() is False


@pytest.mark.parametrize("series_type,expects_gridding", [
    (SeriesType.SURFACE, True),
    (SeriesType.WIREFRAME, True),
    (SeriesType.TRISURF, False),
    (SeriesType.SCATTER3D, False),
])
def test_the_gridding_card_follows_whether_the_type_grids_its_data(series_type, expects_gridding):
    """Surface/Wireframe grid their (x, y, z) exactly as a heatmap does, so
    they reuse its Gridding card; Trisurf triangulates the scattered points
    instead and has nothing to configure there."""
    tab = _tab()

    tab.set_chart_type(ChartType(series_type.value))
    tab.set_selected("series", _series(series_type))

    assert tab.heatmap_gridding_card.isVisible() is expects_gridding


def test_a_scatter3d_series_keeps_its_own_marker_color_control():
    """Regression guard for the needs_z_column / uses_color_scale split: a
    Scatter3D series picks a Z column but colors its points from
    style.marker, so hiding the Color swatch (as is right for Colormap)
    would take away its only color control."""
    tab = _tab()

    tab.set_chart_type(ChartType.SCATTER3D)
    tab.set_selected("series", _series(SeriesType.SCATTER3D))

    assert tab.marker_card.isVisible() is True
    assert tab._is_z_driven_series_target() is False


def test_a_surface_series_is_treated_as_color_scale_driven():
    tab = _tab()

    tab.set_chart_type(ChartType.SURFACE)
    tab.set_selected("series", _series(SeriesType.SURFACE))

    assert tab._is_z_driven_series_target() is True
    assert tab.marker_card.isVisible() is False


@pytest.mark.parametrize("series_type", _3D_SERIES_TYPES)
def test_editing_style_controls_never_crashes_for_a_3d_series(series_type):
    """apply_series_style_to writes fields by concrete style class; a class
    it doesn't know about used to fall through to `style.color = ...` and
    raise for the types that declare no color field (Surface/Trisurf)."""
    tab = _tab()
    series = _series(series_type)
    tab.set_chart_type(ChartType(series_type.value))
    tab.set_selected("series", series)

    tab.apply_series_style_to(series)

    assert type(series.style) is type(_series(series_type).style)


def test_gridding_edits_reach_a_surface_series_style():
    tab = _tab()
    series = _series(SeriesType.SURFACE)
    tab.set_chart_type(ChartType.SURFACE)
    tab.set_selected("series", series)

    tab.heatmap_gridding_control.setCurrentValue("binned")
    tab.heatmap_resolution_spin.setValue(24)
    tab.apply_series_style_to(series)

    assert series.style.heatmap_gridding == "binned"
    assert series.style.heatmap_resolution == 24


def test_line_and_color_edits_reach_a_wireframe_series_style():
    """Wireframe is the one gridding type that also has a flat color and
    line width -- it must not stop at the gridding write the way Heatmap
    does."""
    tab = _tab()
    series = _series(SeriesType.WIREFRAME)
    tab.set_chart_type(ChartType.WIREFRAME)
    tab.set_selected("series", series)

    tab.line_color_row.setCurrentColor("#abcdef")
    tab.line_width_slider.setValue(3.5)
    tab.apply_series_style_to(series)

    assert series.style.color == "#abcdef"
    assert series.style.line_width == 3.5


# -- Data tab ---------------------------------------------------------------


def _app_context_with_project():
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [0, 1], "y": [0, 1], "z": [10.0, 20.0]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    return app_context, project, dataset


@pytest.mark.parametrize("series_type", _3D_SERIES_TYPES)
def test_the_data_tab_offers_a_z_column_for_every_3d_series(series_type):
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="3D Chart", chart_type=ChartType(series_type.value))
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=series_type,
        style=build_series_style(series_type, z_column_id=dataset.column_id("z")))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()

    assert tab.z_column_combo.isVisible() is True
    assert tab.z_column_combo.currentData() == dataset.column_id("z")


def test_adding_a_series_to_a_3d_chart_carries_the_picked_z_column():
    """The bootstrap path used to build a Colormap/Heatmap style with only
    a z_column_id via a hardcoded type check; a 3-D type not in that tuple
    would have silently lost its Z column."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="3D Chart", chart_type=ChartType.SCATTER3D)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._on_dataset_changed()
    tab.z_column_combo.setCurrentIndex(tab.z_column_combo.findData(dataset.column_id("z")))
    tab.apply_to(chart)

    assert len(chart.data_series) == 1
    series = chart.data_series[0]
    assert series.series_type == SeriesType.SCATTER3D
    assert series.style.z_column_id == dataset.column_id("z")
