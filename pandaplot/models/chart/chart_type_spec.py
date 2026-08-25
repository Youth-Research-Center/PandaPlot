"""Per-chart-type column-role requirements and series-type allow-list.

Merges chart_role_spec.py's ChartRoleSpec/CHART_ROLE_SPECS into one
registry instead of two competing ones, adding allowed_series_types/
allows_fit/default_series_type. allowed_series_types is enforced by
Chart.set_chart_type and the add-series flow -- mixed series types on
one chart are a real, working capability.

supports_error_bars is a property, not a stored field: SeriesTypeSpec
now owns the single definition of which series types render error bars,
so duplicating it here would let the two silently drift again.
"""
from dataclasses import dataclass

from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS


@dataclass(frozen=True)
class ChartTypeSpec:
    display_name: str
    roles: tuple[str, ...]
    required_roles: tuple[str, ...]
    # frozenset, not set: `frozen=True` on the dataclass only stops
    # `spec.allowed_series_types = ...` from reassigning the field -- a
    # plain `set` value is still mutable in place (`spec.allowed_series_
    # types.add(...)`), which would silently corrupt every chart using
    # this shared, module-level registry entry. frozenset closes that gap.
    allowed_series_types: frozenset[SeriesType]
    allows_fit: bool
    default_series_type: SeriesType

    @property
    def supports_error_bars(self) -> bool:
        return SERIES_TYPE_SPECS[self.default_series_type].supports_error_bars


CHART_TYPE_SPECS: dict[ChartType, ChartTypeSpec] = {
    ChartType.LINE: ChartTypeSpec(
        display_name="Line", roles=("x", "y"), required_roles=("y",),
        allowed_series_types=frozenset({SeriesType.LINE, SeriesType.SCATTER, SeriesType.VECTOR}),
        allows_fit=True, default_series_type=SeriesType.LINE,
    ),
    ChartType.SCATTER: ChartTypeSpec(
        display_name="Scatter", roles=("x", "y"), required_roles=("y",),
        allowed_series_types=frozenset({SeriesType.LINE, SeriesType.SCATTER, SeriesType.VECTOR}),
        allows_fit=True, default_series_type=SeriesType.SCATTER,
    ),
    ChartType.BAR: ChartTypeSpec(
        display_name="Bar", roles=("x", "y"), required_roles=("y",),
        allowed_series_types=frozenset({SeriesType.BAR, SeriesType.SCATTER}),
        allows_fit=True, default_series_type=SeriesType.BAR,
    ),
    ChartType.HIST: ChartTypeSpec(
        display_name="Histogram", roles=("values",), required_roles=("values",),
        allowed_series_types=frozenset({SeriesType.HIST}),
        allows_fit=True, default_series_type=SeriesType.HIST,
    ),
    ChartType.VECTOR: ChartTypeSpec(
        display_name="Vector", roles=("x", "y", "u", "v", "magnitude"),
        required_roles=("x", "y", "u", "v"),
        allowed_series_types=frozenset({SeriesType.LINE, SeriesType.SCATTER, SeriesType.VECTOR}),
        allows_fit=True, default_series_type=SeriesType.VECTOR,
    ),
    ChartType.COLORMAP: ChartTypeSpec(
        display_name="Color Map", roles=("x", "y", "z"), required_roles=("x", "y", "z"),
        # Also allows plain Scatter/Line series alongside the color-mapped
        # points (e.g. an overlay of uncolored reference points or a trend
        # line -- the same "mixed series types on one chart" pattern
        # LINE/SCATTER/VECTOR chart types already use), and Heatmap series
        # (a gridded matrix on the same axes as color-mapped points).
        allowed_series_types=frozenset({
            SeriesType.COLORMAP, SeriesType.SCATTER, SeriesType.LINE, SeriesType.HEATMAP,
        }),
        allows_fit=False, default_series_type=SeriesType.COLORMAP,
    ),
    ChartType.HEATMAP: ChartTypeSpec(
        display_name="Heatmap", roles=("x", "y", "z"), required_roles=("x", "y", "z"),
        # Also allows plain Scatter/Line series alongside the gridded
        # matrix (e.g. marking specific points or overlaying a trend
        # line), and Colormap series (a color-mapped scatter overlay on
        # the same grid).
        allowed_series_types=frozenset({
            SeriesType.HEATMAP, SeriesType.SCATTER, SeriesType.LINE, SeriesType.COLORMAP,
        }),
        allows_fit=False, default_series_type=SeriesType.HEATMAP,
    ),
}


def compatible_chart_types(chart_type: "str | ChartType") -> frozenset[ChartType]:
    """Chart types it's non-destructive to switch `chart_type` into.

    `target` is compatible with `chart_type` iff `chart_type`'s own
    default_series_type is allowed on `target` -- i.e. the chart's
    "typical" series (what a freshly-created chart of that type actually
    has) survives the switch without a forced retype. This is a static
    per-type-pair rule, not dependent on any specific chart's actual
    series mix, so the chart-type selector UI can precompute it once per
    chart type rather than recomputing per chart. Always includes
    `chart_type` itself (switching a chart to its own current type is
    trivially non-destructive).
    """
    source_spec = CHART_TYPE_SPECS[ChartType(chart_type)]
    return frozenset(
        target for target, target_spec in CHART_TYPE_SPECS.items()
        if source_spec.default_series_type in target_spec.allowed_series_types
    )


def compatible_chart_types_for_series(series_types: "frozenset[SeriesType]") -> frozenset[ChartType]:
    """Chart types it's non-destructive to switch into, given the ACTUAL
    series types on a chart -- not just the nominal type's static
    default_series_type (see `compatible_chart_types`).

    Compatible iff EVERY series type is in the target's allowed_series_types,
    i.e. the switch force-retypes none of the chart's existing series. An
    empty `series_types` (a new chart) has nothing to protect, so every type
    qualifies.

    Fixes a gap in `compatible_chart_types`: a mixed chart (e.g. Scatter
    holding both SCATTER and VECTOR) would otherwise report Bar as safe,
    silently discarding the VECTOR series' config on switch.
    """
    types = frozenset(series_types)
    if not types:
        return frozenset(CHART_TYPE_SPECS.keys())
    return frozenset(
        target for target, spec in CHART_TYPE_SPECS.items()
        if types <= spec.allowed_series_types
    )


def get_chart_type_spec(chart_type: "str | ChartType") -> ChartTypeSpec:
    """Return the spec for `chart_type`.

    Raises:
        ValueError: if `chart_type` is not one of the 5 supported types.
    """
    return CHART_TYPE_SPECS[ChartType(chart_type)]
