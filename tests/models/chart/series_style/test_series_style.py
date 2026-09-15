"""Tests for the 5 typed per-series-type style dataclasses.

Field lists and defaults are pinned against each style class's own
declared fields and against the corresponding per-type render function in
pandaplot/gui/components/tabs/chart/series_renderers/ -- each style class
holds exactly the fields that renderer reads, no more, no less. DataSeries
itself no longer carries any flat style fields (they were fully retired;
see test_flat_style_fields_no_longer_exist below). Marker fields are
composed via MarkerStyle and error-bar fields via ErrorBarConfig (both
pandaplot/models/chart/); vector's column-reference fields (u_column_id,
v_column_id, ...) live on VectorSeriesStyle itself.
"""
import dataclasses

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.error_direction import ErrorDirection
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import (
    BarSeriesStyle,
    HistSeriesStyle,
    LineSeriesStyle,
    ScatterSeriesStyle,
    SeriesStyleBase,
    VectorSeriesStyle,
)


def test_all_style_classes_subclass_series_style_base():
    for cls in (LineSeriesStyle, ScatterSeriesStyle, BarSeriesStyle, HistSeriesStyle, VectorSeriesStyle):
        assert issubclass(cls, SeriesStyleBase)


def test_marker_style_fields_and_defaults():
    marker = MarkerStyle()
    # Both color fields default to "" (the shared "match" sentinel every
    # marker renderer falls back on) so a fresh series' fill and edge
    # start out matching -- see marker_style.py's module docstring.
    assert marker.marker_color == ""
    assert marker.marker_edge_color == ""
    assert marker.marker_edge_width == 1.0
    assert marker.marker_style == "circle"
    assert marker.marker_size == 2.0


def test_error_bar_config_fields_and_defaults():
    error_bars = ErrorBarConfig()
    assert error_bars.x_error_column_id == ""
    assert error_bars.y_error_column_id == ""
    assert error_bars.x_error_minus_column_id == ""
    assert error_bars.y_error_minus_column_id == ""
    assert error_bars.x_error_column == ""
    assert error_bars.y_error_column == ""
    assert error_bars.x_error_minus_column == ""
    assert error_bars.y_error_minus_column == ""
    assert error_bars.error_symmetric is True
    assert error_bars.error_direction == ErrorDirection.BOTH
    assert error_bars.error_color == ""
    assert error_bars.error_cap_size == 3.0
    assert error_bars.has_error_data is False


def test_error_bar_config_has_error_data():
    assert ErrorBarConfig(x_error_column_id="col1").has_error_data is True
    assert ErrorBarConfig(y_error_column="legacy").has_error_data is True


def test_line_series_style_fields_and_defaults():
    style = LineSeriesStyle()
    assert style.color == "#1f77b4"
    assert style.line_style == "solid"
    assert style.line_width == 2.0
    assert style.fill_enabled is False
    assert style.fill_color == ""
    assert style.fill_alpha == 0.3
    assert style.fill_orientation == "vertical"
    assert style.fill_base == 0.0
    assert style.fill_to_index == -1
    assert style.show_value_labels is False
    assert style.value_label_mode == "y"
    assert style.value_label_show_arrow is False
    assert style.value_label_offset_x == 0.0
    assert style.value_label_offset_y == 6.0
    assert style.value_label_text_color == ""
    assert style.value_label_bg_color == ""
    assert style.value_label_bg_alpha == 1.0
    assert isinstance(style.marker, MarkerStyle)
    assert isinstance(style.error_bars, ErrorBarConfig)
    assert {f.name for f in dataclasses.fields(style)} == {
        "color", "line_style", "line_width", "fill_enabled", "fill_color",
        "fill_alpha", "fill_orientation", "fill_base", "fill_to_index",
        "marker", "error_bars", "show_value_labels",
        "value_label_mode", "value_label_show_arrow",
        "value_label_offset_x", "value_label_offset_y",
        "value_label_text_color", "value_label_bg_color", "value_label_bg_alpha",
    }


def test_line_series_style_marker_and_error_bars_are_independent_instances():
    a = LineSeriesStyle()
    b = LineSeriesStyle()
    assert a.marker is not b.marker
    assert a.error_bars is not b.error_bars
    a.marker.marker_color = "#ff0000"
    a.error_bars.error_color = "#00ff00"
    assert b.marker.marker_color == ""
    assert b.error_bars.error_color == ""


def test_scatter_series_style_fields_and_defaults():
    style = ScatterSeriesStyle()
    assert style.color == "#1f77b4"
    assert style.show_value_labels is False
    assert style.value_label_mode == "y"
    assert style.value_label_show_arrow is False
    assert style.value_label_offset_x == 0.0
    assert style.value_label_offset_y == 6.0
    assert style.value_label_text_color == ""
    assert style.value_label_bg_color == ""
    assert style.value_label_bg_alpha == 1.0
    assert isinstance(style.marker, MarkerStyle)
    assert isinstance(style.error_bars, ErrorBarConfig)
    assert {f.name for f in dataclasses.fields(style)} == {
        "color", "marker", "error_bars", "show_value_labels",
        "value_label_mode", "value_label_show_arrow",
        "value_label_offset_x", "value_label_offset_y",
        "value_label_text_color", "value_label_bg_color", "value_label_bg_alpha",
    }


def test_scatter_series_style_marker_and_error_bars_are_independent_instances():
    a = ScatterSeriesStyle()
    b = ScatterSeriesStyle()
    assert a.marker is not b.marker
    assert a.error_bars is not b.error_bars
    a.marker.marker_size = 10.0
    assert b.marker.marker_size == 2.0


def test_bar_series_style_fields_and_defaults():
    style = BarSeriesStyle()
    assert style.color == "#1f77b4"
    assert style.show_value_labels is False
    assert style.value_label_text_color == ""
    assert style.value_label_bg_color == ""
    assert style.value_label_bg_alpha == 1.0
    assert isinstance(style.error_bars, ErrorBarConfig)
    assert {f.name for f in dataclasses.fields(style)} == {
        "color", "error_bars", "show_value_labels",
        "value_label_text_color", "value_label_bg_color", "value_label_bg_alpha",
    }


def test_bar_series_style_error_bars_are_independent_instances():
    a = BarSeriesStyle()
    b = BarSeriesStyle()
    assert a.error_bars is not b.error_bars
    a.error_bars.error_cap_size = 9.0
    assert b.error_bars.error_cap_size == 3.0


def test_hist_series_style_fields_and_defaults():
    style = HistSeriesStyle()
    assert style.color == "#1f77b4"
    assert {f.name for f in dataclasses.fields(style)} == {"color"}


def test_vector_series_style_fields_and_defaults():
    style = VectorSeriesStyle()
    assert style.vector_color == "#1f77b4"
    assert style.vector_colormap == ""
    assert style.vector_scale == 0.0
    assert style.vector_width == 0.005
    assert style.vector_head_width == 3.0
    assert style.vector_head_length == 5.0
    assert style.vector_head_axis_length == 4.5
    assert style.u_column_id == ""
    assert style.v_column_id == ""
    assert style.u_column == ""
    assert style.v_column == ""
    assert style.magnitude_column_id == ""
    assert style.magnitude_column == ""
    assert {f.name for f in dataclasses.fields(style)} == {
        "vector_color", "vector_colormap", "vector_scale", "vector_width",
        "vector_head_width", "vector_head_length", "vector_head_axis_length",
        "u_column_id", "v_column_id", "u_column", "v_column",
        "magnitude_column_id", "magnitude_column",
    }
