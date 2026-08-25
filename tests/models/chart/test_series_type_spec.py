"""Pins SERIES_TYPE_SPECS' values against today's hardcoded behavior in
chart_editor.py/resolve_series_data/style_tab.py, before those call sites
are rewired to read from this registry.

Note on marker_mode: the UI doesn't yet distinguish line ("optional") from
scatter ("required") -- both show the Marker card with the same "markers
enabled" toggle. This field records the *intended* distinction (issue #178)
so a later phase reworking the Style tab's marker controls can consume it
directly instead of re-deciding the value. bar/hist/vector are
"unsupported" (no marker concept).
"""
from pandaplot.models.chart.series_style import (
    BarSeriesStyle,
    HistSeriesStyle,
    LineSeriesStyle,
    ScatterSeriesStyle,
    VectorSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS


def test_all_seven_series_types_are_registered():
    assert set(SERIES_TYPE_SPECS.keys()) == {
        SeriesType.LINE, SeriesType.SCATTER, SeriesType.BAR,
        SeriesType.HIST, SeriesType.VECTOR,
        SeriesType.COLORMAP, SeriesType.HEATMAP,
    }


def test_line_spec():
    spec = SERIES_TYPE_SPECS[SeriesType.LINE]
    assert spec.marker_mode == "optional"
    assert spec.supports_line_style is True
    assert spec.supports_color is True
    assert spec.supports_fill is True
    assert spec.supports_error_bars is True
    assert spec.needs_x_column is True
    assert spec.needs_secondary_columns is False


def test_scatter_spec():
    spec = SERIES_TYPE_SPECS[SeriesType.SCATTER]
    assert spec.marker_mode == "required"
    assert spec.supports_line_style is False
    assert spec.supports_color is False
    assert spec.supports_fill is False
    assert spec.supports_error_bars is True
    assert spec.needs_x_column is True
    assert spec.needs_secondary_columns is False


def test_bar_spec():
    spec = SERIES_TYPE_SPECS[SeriesType.BAR]
    assert spec.marker_mode == "unsupported"
    assert spec.supports_line_style is False
    assert spec.supports_color is True
    assert spec.supports_fill is False
    assert spec.supports_error_bars is True
    assert spec.needs_x_column is True
    assert spec.needs_secondary_columns is False


def test_hist_spec():
    spec = SERIES_TYPE_SPECS[SeriesType.HIST]
    assert spec.marker_mode == "unsupported"
    assert spec.supports_line_style is False
    assert spec.supports_color is True
    assert spec.supports_fill is False
    assert spec.supports_error_bars is False
    assert spec.needs_x_column is False
    assert spec.needs_secondary_columns is False


def test_vector_spec():
    spec = SERIES_TYPE_SPECS[SeriesType.VECTOR]
    assert spec.marker_mode == "unsupported"
    assert spec.supports_line_style is False
    assert spec.supports_color is False
    assert spec.supports_fill is False
    assert spec.supports_error_bars is False
    assert spec.needs_x_column is True
    assert spec.needs_secondary_columns is True


def test_style_cls_matches_each_series_type():
    assert SERIES_TYPE_SPECS[SeriesType.LINE].style_cls is LineSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.SCATTER].style_cls is ScatterSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.BAR].style_cls is BarSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.HIST].style_cls is HistSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.VECTOR].style_cls is VectorSeriesStyle
