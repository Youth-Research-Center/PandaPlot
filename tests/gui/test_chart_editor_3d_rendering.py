"""Widget-level tests for ChartEditorWidget's 3-D rendering path (issue
#98): projection switching, the shared colorbar's narrower 3-D rules, and
the 2-D-only axis machinery that must not run on an mplot3d axes.

Follows the same helper-function pattern (not a pytest fixture) as
test_chart_editor_colormap_rendering.py.
"""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis
from pandaplot.models.project.project import Project

_3D_CHART_TYPES = [
    ChartType.SCATTER3D, ChartType.LINE3D, ChartType.SURFACE,
    ChartType.WIREFRAME, ChartType.BAR3D, ChartType.TRISURF,
]


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset():
    """A 5x5 lattice: griddable exactly (no binning needed for
    surface/wireframe) and triangulatable for trisurf."""
    project = Project(name="3D Render Project")
    side = 5
    x = [float(i) for i in range(side) for _ in range(side)]
    y = [float(j) for _ in range(side) for j in range(side)]
    df = pd.DataFrame(
        {"x": x, "y": y, "z": [a * 0.5 + b * 0.25 for a, b in zip(x, y, strict=True)]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _editor_for(project, chart):
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    return ChartEditorWidget(app_context=app_context, chart=chart, parent=None)


def _chart_with_series(dataset, chart_type, **series_kwargs):
    chart = Chart(name=f"{chart_type} chart", chart_type=chart_type)
    series_type = SeriesType(chart_type.value)
    chart.data_series.append(DataSeries(
        dataset_id=dataset.id,
        x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        label="s1", series_type=series_type,
        style=build_series_style(series_type, color="#1f77b4",
                                  z_column_id=dataset.column_id("z")),
        **series_kwargs,
    ))
    return chart


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_every_3d_chart_type_renders_without_error(chart_type):
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _chart_with_series(dataset, chart_type))

    editor.update_chart()

    assert editor.chart_canvas.is_3d is True
    assert editor.status_label.text() == "Ready"


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_re_rendering_a_3d_chart_repeatedly_stays_healthy(chart_type):
    """The colorbar/gridspec accumulation bug class colormap charts hit
    (PR #156) applies just as much here -- Surface/Trisurf draw a colorbar
    too, and every render rebuilds the axes."""
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _chart_with_series(dataset, chart_type))

    for _ in range(3):
        editor.update_chart()

    assert editor.status_label.text() == "Ready"
    assert len(editor.chart_canvas.fig.axes) <= 2  # the plot, plus at most a colorbar


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_a_colorbar_is_drawn_only_for_the_color_scaled_3d_types(chart_type):
    """Surface/Trisurf color their faces through the chart's shared color
    scale; Scatter3D/Line3D/Wireframe/Bar3D draw in a flat style color and
    must not get a colorbar for a scale they don't use."""
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _chart_with_series(dataset, chart_type))

    editor.update_chart()

    expects_colorbar = chart_type in (ChartType.SURFACE, ChartType.TRISURF)
    assert (editor._colorbar is not None) is expects_colorbar


def test_switching_a_chart_from_2d_to_3d_rebuilds_the_axes_projection():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.LINE)
    editor = _editor_for(project, chart)
    editor.update_chart()
    assert editor.chart_canvas.is_3d is False

    chart.set_chart_type(ChartType.SCATTER3D)
    chart.data_series[0].style.z_column_id = dataset.column_id("z")
    editor.update_chart()

    assert editor.chart_canvas.is_3d is True
    assert editor.status_label.text() == "Ready"


def test_switching_a_chart_back_from_3d_to_2d_restores_a_flat_axes():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.SCATTER3D)
    editor = _editor_for(project, chart)
    editor.update_chart()
    assert editor.chart_canvas.is_3d is True

    chart.set_chart_type(ChartType.LINE)
    editor.update_chart()

    assert editor.chart_canvas.is_3d is False
    assert editor.status_label.text() == "Ready"


def test_a_3d_chart_never_builds_a_secondary_y_axis():
    """twinx() has no mplot3d equivalent, so a series still carrying
    y_axis=SECONDARY from a previous 2-D type must not make one."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.SURFACE, y_axis=YAxis.SECONDARY)
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert editor.chart_canvas.axes2 is None
    assert editor.status_label.text() == "Ready"


def test_switching_to_3d_tears_down_an_existing_secondary_y_axis():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.LINE, y_axis=YAxis.SECONDARY)
    editor = _editor_for(project, chart)
    editor.update_chart()
    assert editor.chart_canvas.axes2 is not None

    chart.set_chart_type(ChartType.SCATTER3D)
    chart.data_series[0].style.z_column_id = dataset.column_id("z")
    editor.update_chart()

    assert editor.chart_canvas.axes2 is None


def test_the_z_axis_label_scale_and_manual_limits_are_applied():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.SCATTER3D)
    chart.config.update({
        "z_label": "Depth (m)", "z_auto_limits": False, "z_min": -2.0, "z_max": 7.0,
    })
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert editor.chart_canvas.axes.get_zlabel() == "Depth (m)"
    assert editor.chart_canvas.axes.get_zlim() == (-2.0, 7.0)


def test_the_configured_camera_angle_is_applied():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.SCATTER3D)
    chart.config.update({"view_elev": 12.0, "view_azim": 45.0})
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert editor.chart_canvas.axes.elev == pytest.approx(12.0)
    assert editor.chart_canvas.axes.azim == pytest.approx(45.0)


def test_reset_zoom_restores_the_z_limits_too():
    _qapp()
    project, dataset = _project_and_dataset()
    editor = _editor_for(project, _chart_with_series(dataset, ChartType.SCATTER3D))
    editor.update_chart()
    original = editor.chart_canvas.axes.get_zlim()

    editor.chart_canvas.axes.set_zlim(-100.0, 100.0)
    editor.chart_canvas.reset_zoom()

    assert editor.chart_canvas.axes.get_zlim() == pytest.approx(original)


def test_a_3d_series_with_no_z_column_reports_an_error_instead_of_rendering():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _chart_with_series(dataset, ChartType.SURFACE)
    chart.data_series[0].style.z_column_id = ""
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert "no Z column configured" in editor.status_label.text()


def test_an_ungriddable_surface_series_degrades_to_a_per_series_message():
    """All-NaN coordinates leave build_surface_mesh nothing to grid. That
    must surface as a skipped series, not a blank chart."""
    _qapp()
    project = Project(name="p")
    df = pd.DataFrame({
        "x": [float("nan")] * 4, "y": [float("nan")] * 4, "z": [1.0, 2.0, 3.0, 4.0],
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    chart = _chart_with_series(dataset, ChartType.SURFACE)
    editor = _editor_for(project, chart)

    editor.update_chart()

    assert "no plottable data" in editor.status_label.text()
    assert editor._colorbar is None


def test_a_3d_chart_type_is_marked_3d_in_the_spec_the_editor_reads():
    """The editor branches on ChartTypeSpec.is_3d rather than testing chart
    type membership itself; this pins the two together."""
    for chart_type in _3D_CHART_TYPES:
        assert CHART_TYPE_SPECS[chart_type].is_3d is True
