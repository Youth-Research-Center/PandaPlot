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


def test_every_series_type_is_registered():
    """Asserted against the SeriesType enum rather than a hardcoded list --
    a series type with no spec makes every consumer (the renderer dispatch,
    the Style tab's card visibility, DataSeries.__post_init__) KeyError,
    and that stays caught without editing this test per new type."""
    assert set(SERIES_TYPE_SPECS.keys()) == set(SeriesType)


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


def test_curve_analysis_is_supported_only_by_line_and_scatter():
    """Regression (#202): ChartAnalysisPanel's derivative/integral/arc-length/
    smoothing/interpolation operations assume a single ordered (x, y) curve.
    Asserted against the full SeriesType enum (not just the two True cases)
    so a newly added type defaults to being excluded rather than silently
    inheriting a meaningless analysis option."""
    curve_types = {SeriesType.LINE, SeriesType.SCATTER}
    for series_type in SeriesType:
        expected = series_type in curve_types
        assert SERIES_TYPE_SPECS[series_type].supports_curve_analysis is expected, series_type


def test_value_labels_are_supported_only_by_line_scatter_and_bar():
    """Regression (#125): each rendered point/bar can be annotated with its
    own numeric value only for the types with a single scalar value per
    plotted element (a Line/Scatter point's Y, a Bar's height). Asserted
    against the full SeriesType enum so a newly added type defaults to
    being excluded rather than silently inheriting an unsupported option."""
    value_label_types = {SeriesType.LINE, SeriesType.SCATTER, SeriesType.BAR}
    for series_type in SeriesType:
        expected = series_type in value_label_types
        assert SERIES_TYPE_SPECS[series_type].supports_value_labels is expected, series_type


def test_style_cls_matches_each_series_type():
    assert SERIES_TYPE_SPECS[SeriesType.LINE].style_cls is LineSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.SCATTER].style_cls is ScatterSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.BAR].style_cls is BarSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.HIST].style_cls is HistSeriesStyle
    assert SERIES_TYPE_SPECS[SeriesType.VECTOR].style_cls is VectorSeriesStyle
