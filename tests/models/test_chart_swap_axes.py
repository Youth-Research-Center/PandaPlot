"""Tests for Chart.swap_axes / Chart.swap_axes_blocker (#266)."""
import numpy as np
import pytest

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries, YAxis, snapshot_chart_state


def _chart_with_series(**series_kwargs) -> Chart:
    chart = Chart(name="Swap", chart_type="line")
    kwargs = {"x_column_id": "cx", "y_column_id": "cy", "x_column": "time", "y_column": "voltage", **series_kwargs}
    chart.data_series.append(DataSeries(dataset_id="ds1", **kwargs))
    return chart


def test_swap_exchanges_series_columns_and_axis_settings():
    style = LineSeriesStyle(
        error_bars=ErrorBarConfig(x_error_column_id="ex", y_error_column_id="ey", y_error_minus_column_id="eym"),
        fill_orientation="vertical", value_label_mode="y", value_label_offset_x=1.0, value_label_offset_y=6.0,
    )
    chart = _chart_with_series(style=style)
    chart.config.x.label = "Time"
    chart.config.y.label = "Voltage"
    chart.config.y.scale = "log"
    chart.config.y.auto_limits = False
    chart.config.y.min = 1.0
    chart.config.y.max = 100.0
    chart.config.x.label_color = "#ff0000"

    chart.swap_axes()

    series = chart.data_series[0]
    assert (series.x_column_id, series.y_column_id) == ("cy", "cx")
    assert (series.x_column, series.y_column) == ("voltage", "time")
    assert series.style.error_bars.x_error_column_id == "ey"
    assert series.style.error_bars.y_error_column_id == "ex"
    assert series.style.error_bars.x_error_minus_column_id == "eym"
    assert series.style.error_bars.y_error_minus_column_id == ""
    assert series.style.fill_orientation == "horizontal"
    assert series.style.value_label_mode == "x"
    assert (series.style.value_label_offset_x, series.style.value_label_offset_y) == (6.0, 1.0)
    assert (chart.config.x.label, chart.config.y.label) == ("Voltage", "Time")
    assert (chart.config.x.scale, chart.config.y.scale) == ("log", "linear")
    assert chart.config.x.auto_limits is False
    assert (chart.config.x.min, chart.config.x.max) == (1.0, 100.0)
    assert chart.config.y.auto_limits is True
    # Positional styling stays with the axis, not the data.
    assert chart.config.x.label_color == "#ff0000"
    assert chart.config.y.side == "left"
    assert chart.config.y.label_rotation == 90.0


def test_swapping_twice_restores_the_original_chart():
    chart = _chart_with_series(style=LineSeriesStyle(error_bars=ErrorBarConfig(x_error_column_id="ex")))
    chart.config.x.label = "Time"
    chart.config.y.scale = "log"
    before = snapshot_chart_state(chart)

    chart.swap_axes()
    chart.swap_axes()

    after = snapshot_chart_state(chart)
    assert after["config"] == before["config"]
    assert after["data_series"] == before["data_series"]


def test_swap_survives_save_and_reload():
    chart = _chart_with_series()
    chart.config.y.label = "Voltage"
    chart.swap_axes()

    reloaded = Chart.from_dict(chart.to_dict())

    assert reloaded.data_series[0].x_column_id == "cy"
    assert reloaded.config.x.label == "Voltage"


@pytest.mark.parametrize(("make_chart", "reason_fragment"), [
    (lambda: Chart(name="Empty", chart_type="line"), "Add a data series"),
    (lambda: Chart(name="Bars", chart_type="bar"), "Bar"),
    (lambda: _chart_with_series(y_axis=YAxis.SECONDARY), "secondary Y axis"),
    (lambda: _chart_with_series(style=LineSeriesStyle(twin_y_column_id="ct")), "secondary Y axis"),
    (lambda: _chart_with_series(x_column_id="", x_column=""), "row index"),
    (lambda: Chart(name="Pie", chart_type="pie"), "Pie"),
    (lambda: _chart_with_series(series_type=SeriesType.HIST), "Line, Scatter, Vector or Fit"),
])
def test_swap_is_refused_with_a_reason_and_leaves_the_chart_unchanged(make_chart, reason_fragment):
    chart = make_chart()
    before = snapshot_chart_state(chart)

    blocker = chart.swap_axes_blocker()
    assert blocker is not None
    assert reason_fragment in blocker
    with pytest.raises(ValueError, match=reason_fragment):
        chart.swap_axes()

    after = snapshot_chart_state(chart)
    assert after["config"] == before["config"]
    assert after["data_series"] == before["data_series"]


def test_scatter_chart_can_be_swapped():
    chart = Chart(name="Scatter", chart_type="scatter")
    chart.data_series.append(DataSeries(dataset_id="ds1", x_column_id="cx", y_column_id="cy", series_type=SeriesType.SCATTER))

    assert chart.swap_axes_blocker() is None
    chart.swap_axes()
    assert chart.data_series[0].x_column_id == "cy"


def test_supports_swap_axes_only_for_line_scatter_and_vector_charts():
    assert Chart(name="L", chart_type="line").supports_swap_axes
    assert Chart(name="S", chart_type="scatter").supports_swap_axes
    assert Chart(name="V", chart_type="vector").supports_swap_axes
    assert not Chart(name="P", chart_type="pie").supports_swap_axes
    assert not Chart(name="B", chart_type="bar").supports_swap_axes


def test_swap_exchanges_a_vector_series_positions_and_components():
    style = VectorSeriesStyle(u_column_id="cu", v_column_id="cv", u_column="U", v_column="V", magnitude_column_id="cm")
    chart = Chart(name="Vec", chart_type="vector")
    chart.data_series.append(
        DataSeries(dataset_id="ds1", x_column_id="cx", y_column_id="cy", series_type=SeriesType.VECTOR, style=style),
    )

    chart.swap_axes()

    series = chart.data_series[0]
    assert (series.x_column_id, series.y_column_id) == ("cy", "cx")
    assert (series.style.u_column_id, series.style.v_column_id) == ("cv", "cu")
    assert (series.style.u_column, series.style.v_column) == ("V", "U")
    assert series.style.magnitude_column_id == "cm"


def _chart_with_fit() -> Chart:
    chart = _chart_with_series()
    chart.data_series.append(DataSeries(
        dataset_id="ds1", x_column_id="cx", y_column_id="cy", series_type=SeriesType.FIT,
        style=FitStyle(
            fit_type="linear", fit_params={"slope": 2.0},
            confidence_lower=np.array([0.5, 1.5]), confidence_upper=np.array([1.5, 2.5]),
        ),
        precomputed_x_data=np.array([0.0, 1.0]), precomputed_y_data=np.array([1.0, 2.0]),
    ))
    return chart


def test_swap_mirrors_a_fit_curve_and_turns_its_band_horizontal():
    chart = _chart_with_fit()

    assert chart.swap_axes_blocker() is None
    chart.swap_axes()

    fit = chart.data_series[1]
    np.testing.assert_array_equal(fit.precomputed_x_data, [1.0, 2.0])
    np.testing.assert_array_equal(fit.precomputed_y_data, [0.0, 1.0])
    assert (fit.x_column_id, fit.y_column_id) == ("cy", "cx")
    assert fit.style.band_orientation == "horizontal"
    assert fit.style.fit_params == {"slope": 2.0}
    np.testing.assert_array_equal(fit.style.confidence_lower, [0.5, 1.5])


def test_swapping_a_fit_twice_restores_it_and_its_band_orientation_round_trips():
    chart = _chart_with_fit()
    chart.swap_axes()

    reloaded = Chart.from_dict(chart.to_dict())
    assert reloaded.data_series[1].style.band_orientation == "horizontal"
    np.testing.assert_array_equal(reloaded.data_series[1].precomputed_x_data, [1.0, 2.0])

    chart.swap_axes()
    fit = chart.data_series[1]
    np.testing.assert_array_equal(fit.precomputed_x_data, [0.0, 1.0])
    np.testing.assert_array_equal(fit.precomputed_y_data, [1.0, 2.0])
    assert fit.style.band_orientation == "vertical"


def test_swap_leaves_partial_fill_ranges_untouched():
    style = LineSeriesStyle(fill_enabled=True, fill_range_enabled=True, fill_sections=[(0, 4), (7, 9)])
    chart = _chart_with_series(style=style)

    chart.swap_axes()

    assert chart.data_series[0].style.fill_sections == [(0, 4), (7, 9)]
    assert chart.data_series[0].style.fill_orientation == "horizontal"
