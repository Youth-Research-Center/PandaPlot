"""Tests for AxesTab's 3-D additions (issue #98): the Z axis chip and
form, the camera-angle card, and the Y2/Z mutual exclusion.

Uses the same minimal app-context stand-in as test_axes_tab.py.
"""
import types

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.axes_tab import AxesTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context():
    return types.SimpleNamespace(app_state=types.SimpleNamespace(current_project=None))


def _chip_data(tab):
    """The axis values currently offered by the chip row."""
    return list(tab.axis_chips._values)


def _3d_chart():
    chart = Chart(name="Surface", chart_type=ChartType.SURFACE)
    chart.data_series.append(DataSeries(
        dataset_id="ds-1", series_type=SeriesType.SURFACE,
        style=build_series_style(SeriesType.SURFACE, z_column_id="col-z")))
    return chart


def test_a_2d_chart_offers_no_z_axis_chip_and_no_camera_card():
    tab = AxesTab(_make_app_context())

    tab.load(Chart(name="Line", chart_type=ChartType.LINE))

    assert "z" not in _chip_data(tab)
    assert tab.view_card.isVisible() is False


def test_a_3d_chart_offers_a_z_axis_chip_and_the_camera_card():
    tab = AxesTab(_make_app_context())

    tab.load(_3d_chart())

    assert "z" in _chip_data(tab)
    assert tab.view_card.isHidden() is False


def test_a_3d_chart_never_offers_the_secondary_y_chip():
    """A 3-D chart has no secondary Y axis at all (twinx() has no mplot3d
    equivalent), so a series still carrying y_axis=SECONDARY from a
    previous 2-D type must not resurrect the chip."""
    chart = _3d_chart()
    chart.data_series[0].y_axis = YAxis.SECONDARY
    tab = AxesTab(_make_app_context())

    tab.load(chart)

    assert "y2" not in _chip_data(tab)


def test_the_color_chip_appears_only_for_color_scaled_3d_series():
    """uses_color_scale, not needs_z_column, gates the Color chip: several
    3-D types (Scatter3D, Line3D, Bar3D, Wireframe) pick a Z column without
    taking their color from the chart's shared color scale -- they use
    their own marker/line color instead (see series_type_spec.py) -- so a
    needs_z_column check would offer a meaningless Color chip for them."""
    color_scaled = AxesTab(_make_app_context())
    color_scaled.load(_3d_chart())  # SURFACE: uses_color_scale=True

    flat = AxesTab(_make_app_context())
    flat_chart = Chart(name="Cloud", chart_type=ChartType.SCATTER3D)
    flat_chart.data_series.append(DataSeries(
        dataset_id="ds-1", series_type=SeriesType.SCATTER3D,
        style=build_series_style(SeriesType.SCATTER3D, z_column_id="col-z")))
    flat.load(flat_chart)

    assert "color" in _chip_data(color_scaled)
    assert "color" not in _chip_data(flat)


def test_the_z_form_writes_its_settings_into_the_chart_config():
    chart = _3d_chart()
    tab = AxesTab(_make_app_context())
    tab.load(chart)

    z_form = tab.axes_forms["z"]
    z_form["label_edit"].setText("Height (m)")
    z_form["mode_control"].setCurrentValue("count")
    z_form["count_spin"].setValue(7)
    z_form["grid_toggle"].setChecked(checked=False)

    assert chart.config["z_label"] == "Height (m)"
    assert chart.config["z_tick_mode"] == "count"
    assert chart.config["z_tick_count"] == 7
    assert chart.config["show_grid_z"] is False


def test_the_z_form_reloads_the_saved_config():
    chart = _3d_chart()
    chart.config.update({
        "z_label": "Depth", "z_auto_limits": False, "z_min": -3.0, "z_max": 9.0,
    })
    tab = AxesTab(_make_app_context())

    tab.load(chart)

    z_form = tab.axes_forms["z"]
    assert z_form["label_edit"].text() == "Depth"
    assert z_form["auto_toggle"].isChecked() is False
    assert z_form["min_spin"].value() == pytest.approx(-3.0)
    assert z_form["max_spin"].value() == pytest.approx(9.0)


def test_the_camera_card_round_trips_through_the_chart_config():
    chart = _3d_chart()
    tab = AxesTab(_make_app_context())
    tab.load(chart)

    tab.view_elev_spin.setValue(12.5)
    tab.view_azim_spin.setValue(-95.0)

    assert chart.config["view_elev"] == pytest.approx(12.5)
    assert chart.config["view_azim"] == pytest.approx(-95.0)

    reloaded = AxesTab(_make_app_context())
    reloaded.load(chart)
    assert reloaded.view_elev_spin.value() == pytest.approx(12.5)
    assert reloaded.view_azim_spin.value() == pytest.approx(-95.0)


def test_switching_a_chart_back_to_2d_reselects_a_reachable_axis():
    """The Z chip disappears with the 3-D type; leaving the (now
    unreachable) Z form on screen with no chip highlighted would strand the
    user in a form they can't navigate away from."""
    chart = _3d_chart()
    tab = AxesTab(_make_app_context())
    tab.load(chart)
    tab.axis_chips.setCurrentValue("z")
    tab._show_axis_form("z")

    chart.set_chart_type(ChartType.LINE)
    tab.refresh_axis_chips(chart)

    assert tab.axis_chips.currentValue() == "x"
    assert tab.axes_forms["z"]["widget"].isVisible() is False
