"""Tests for the 3-D chart/series types (issue #98): their spec entries,
the is_3d / uses_color_scale distinction those specs introduce, and the
save/reload round trip of the six new typed style classes.
"""
import pytest

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import (
    CHART_TYPE_SPECS,
    compatible_chart_types_for_series,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import Chart, DataSeries

_3D_CHART_TYPES = [
    ChartType.SCATTER3D, ChartType.LINE3D, ChartType.SURFACE,
    ChartType.WIREFRAME, ChartType.BAR3D, ChartType.TRISURF,
]
_3D_SERIES_TYPES = [
    SeriesType.SCATTER3D, SeriesType.LINE3D, SeriesType.SURFACE,
    SeriesType.WIREFRAME, SeriesType.BAR3D, SeriesType.TRISURF,
]


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_every_3d_chart_type_requires_the_full_x_y_z_trio(chart_type):
    spec = CHART_TYPE_SPECS[chart_type]

    assert spec.is_3d is True
    assert spec.roles == ("x", "y", "z")
    assert spec.required_roles == ("x", "y", "z")


@pytest.mark.parametrize("series_type", _3D_SERIES_TYPES)
def test_every_3d_series_type_needs_a_z_column_and_draws_no_error_bars(series_type):
    """Z is the third spatial axis for these, so it's required; mplot3d has
    no errorbar() at all, so offering error-bar controls would be a
    silently-ignored UI."""
    spec = SERIES_TYPE_SPECS[series_type]

    assert spec.is_3d is True
    assert spec.needs_z_column is True
    assert spec.supports_error_bars is False


def test_only_the_color_mapped_types_use_the_shared_color_scale():
    """uses_color_scale is deliberately narrower than needs_z_column: a
    Scatter3D series picks a Z column but colors its points from
    style.color, so it must not put a Color Map card in front of the user
    or contribute to the chart's shared colorbar range."""
    using = {t for t, spec in SERIES_TYPE_SPECS.items() if spec.uses_color_scale}

    assert using == {
        SeriesType.COLORMAP, SeriesType.HEATMAP, SeriesType.SURFACE, SeriesType.TRISURF,
    }


def test_gridding_applies_to_the_types_that_actually_grid_their_data():
    """Surface/Wireframe reuse the heatmap's gridding; Trisurf deliberately
    doesn't (it triangulates the scattered points as-is, which is the whole
    difference between it and Surface)."""
    gridding = {t for t, spec in SERIES_TYPE_SPECS.items() if spec.supports_gridding}

    assert gridding == {SeriesType.HEATMAP, SeriesType.SURFACE, SeriesType.WIREFRAME}


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_no_3d_chart_type_accepts_a_2d_series_type(chart_type):
    """A Line2D can't be added to an Axes3D, so a chart mixing the two
    could never render. Enforced in the spec rather than defensively at
    render time."""
    allowed = CHART_TYPE_SPECS[chart_type].allowed_series_types

    assert all(SERIES_TYPE_SPECS[series_type].is_3d for series_type in allowed)


def test_no_2d_chart_type_accepts_a_3d_series_type():
    for chart_type, spec in CHART_TYPE_SPECS.items():
        if spec.is_3d:
            continue
        assert not any(SERIES_TYPE_SPECS[t].is_3d for t in spec.allowed_series_types), chart_type


def test_switching_between_2d_and_3d_is_never_offered_as_non_destructive():
    """Follows from the allow-lists above: such a switch would force-retype
    (and so silently reconfigure) every series on the chart, which is
    exactly what compatible_chart_types_for_series exists to prevent."""
    from_3d = compatible_chart_types_for_series(frozenset({SeriesType.SURFACE}))
    from_2d = compatible_chart_types_for_series(frozenset({SeriesType.LINE}))

    assert all(CHART_TYPE_SPECS[t].is_3d for t in from_3d)
    assert not any(CHART_TYPE_SPECS[t].is_3d for t in from_2d)


def test_a_point_cloud_or_trajectory_can_be_overlaid_on_any_3d_chart():
    """Scatter3D/Line3D are allowed on every 3-D chart type so measured
    points can be shown against a fitted surface."""
    for chart_type in _3D_CHART_TYPES:
        allowed = CHART_TYPE_SPECS[chart_type].allowed_series_types
        assert SeriesType.SCATTER3D in allowed
        assert SeriesType.LINE3D in allowed


@pytest.mark.parametrize("series_type", _3D_SERIES_TYPES)
def test_a_3d_series_survives_a_save_reload_round_trip(series_type):
    chart = Chart(name="3D", chart_type=ChartType(series_type.value))
    style = SERIES_TYPE_SPECS[series_type].style_cls(z_column_id="col-z")
    chart.data_series.append(DataSeries(
        dataset_id="ds-1", x_column_id="col-x", y_column_id="col-y",
        label="s1", series_type=series_type, style=style))

    reloaded = Chart.from_dict(chart.to_dict())

    assert reloaded.chart_type == ChartType(series_type.value)
    assert len(reloaded.data_series) == 1
    restored = reloaded.data_series[0]
    assert restored.series_type == series_type
    assert type(restored.style) is type(style)
    assert restored.style.z_column_id == "col-z"


def test_3d_style_fields_round_trip_with_their_edited_values():
    chart = Chart(name="Surface", chart_type=ChartType.SURFACE)
    chart.data_series.append(DataSeries(
        dataset_id="ds-1", series_type=SeriesType.SURFACE,
        style=SERIES_TYPE_SPECS[SeriesType.SURFACE].style_cls(
            z_column_id="col-z", heatmap_gridding="interpolated", heatmap_resolution=17,
            edge_color="#112233", edge_width=0.5, shade=False)))

    style = Chart.from_dict(chart.to_dict()).data_series[0].style

    assert style.heatmap_gridding == "interpolated"
    assert style.heatmap_resolution == 17
    assert style.edge_color == "#112233"
    assert style.edge_width == 0.5
    assert style.shade is False


def test_retyping_between_two_3d_types_keeps_the_picked_z_column():
    """Every 3-D type needs the same Z column, so switching Surface ->
    Wireframe must not make the user re-pick it (same carry-over
    Colormap <-> Heatmap already has)."""
    chart = Chart(name="Surface", chart_type=ChartType.SURFACE)
    chart.data_series.append(DataSeries(
        dataset_id="ds-1", series_type=SeriesType.SURFACE,
        style=SERIES_TYPE_SPECS[SeriesType.SURFACE].style_cls(z_column_id="col-z")))

    chart.retype_series(0, SeriesType.WIREFRAME)

    assert chart.data_series[0].style.z_column_id == "col-z"


def test_a_new_chart_carries_z_axis_and_camera_defaults():
    """Written for every chart, not just 3-D ones, so a chart that changes
    type doesn't start out with a half-populated Z axis."""
    config = Chart(name="c", chart_type=ChartType.LINE).config

    assert config["z_label"] == ""
    assert config["z_scale"] == "linear"
    assert config["z_auto_limits"] is True
    assert config["show_grid_z"] is True
    assert config["view_elev"] == 30.0
    assert config["view_azim"] == -60.0
