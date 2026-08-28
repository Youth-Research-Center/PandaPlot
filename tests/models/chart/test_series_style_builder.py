"""Tests for build_series_style -- the single spec-driven replacement for
the four hand-written if/elif style-construction chains the series
creation paths used to each carry."""
import pytest

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS


@pytest.mark.parametrize("series_type", list(SeriesType))
def test_builds_the_style_class_the_spec_registers_for_every_series_type(series_type):
    """The whole point of driving this off SERIES_TYPE_SPECS: a newly
    registered series type is buildable by every creation path at once.
    A mismatch here is not cosmetic -- DataSeries.__post_init__ rejects a
    style whose class doesn't match its series_type."""
    style = build_series_style(series_type)

    assert type(style) is SERIES_TYPE_SPECS[series_type].style_cls


@pytest.mark.parametrize("series_type", list(SeriesType))
def test_passing_every_argument_is_safe_for_every_series_type(series_type):
    """Callers pass whatever their UI has to hand (a stale U column while a
    Line series is selected, say) without knowing which fields this type
    keeps -- an argument a type has no field for must be dropped, never
    raise."""
    style = build_series_style(
        series_type, color="#abcdef", error_bars=ErrorBarConfig(y_error_column_id="e"),
        u_column_id="u", v_column_id="v", magnitude_column_id="m", z_column_id="z",
    )

    assert type(style) is SERIES_TYPE_SPECS[series_type].style_cls


@pytest.mark.parametrize("series_type", list(SeriesType))
def test_the_column_ids_a_type_needs_always_land_on_its_style(series_type):
    spec = SERIES_TYPE_SPECS[series_type]
    style = build_series_style(
        series_type, u_column_id="u", v_column_id="v", magnitude_column_id="m", z_column_id="z")

    if spec.needs_z_column:
        assert style.z_column_id == "z"
    if spec.needs_secondary_columns:
        assert (style.u_column_id, style.v_column_id, style.magnitude_column_id) == ("u", "v", "m")


def test_color_lands_on_vector_color_for_a_vector_series():
    """VectorSeriesStyle has no flat `color` -- its equivalent field is
    named vector_color, and a caller shouldn't have to know that."""
    style = build_series_style(SeriesType.VECTOR, color="#ff0000")

    assert style.vector_color == "#ff0000"


@pytest.mark.parametrize("series_type", [
    SeriesType.COLORMAP, SeriesType.HEATMAP, SeriesType.SURFACE, SeriesType.TRISURF,
])
def test_color_is_dropped_for_the_types_the_chart_color_map_colors(series_type):
    """These take their color from the chart-level color map, so they
    declare no color field at all -- passing one must be a no-op rather
    than a TypeError (which is what the old per-call-site chains risked
    every time a type was added)."""
    style = build_series_style(series_type, color="#ff0000")

    assert not hasattr(style, "color")
    assert not hasattr(style, "vector_color")


def test_an_empty_color_leaves_the_style_class_default_intact():
    default = build_series_style(SeriesType.LINE).color

    assert build_series_style(SeriesType.LINE, color="").color == default


def test_error_bars_are_dropped_for_a_type_that_cannot_draw_them():
    """3-D types and Hist/Vector have no error_bars field: mplot3d has no
    errorbar() at all."""
    style = build_series_style(
        SeriesType.SCATTER3D, error_bars=ErrorBarConfig(y_error_column_id="e"))

    assert not hasattr(style, "error_bars")


def test_error_bars_are_kept_for_a_type_that_supports_them():
    style = build_series_style(
        SeriesType.SCATTER, error_bars=ErrorBarConfig(y_error_column_id="e"))

    assert style.error_bars.y_error_column_id == "e"
