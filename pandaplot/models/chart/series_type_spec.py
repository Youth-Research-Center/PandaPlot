"""Per-series-type styling capabilities: the single source of truth this
design introduces to replace the independently-drifting if/elif checks in
chart_editor.py's update_chart()/resolve_series_data() and style_tab.py's
_update_target_cards_visibility(). See test_series_type_spec.py for the
current hardcoded behavior each field's value is derived from.

Deliberately holds no matplotlib-dependent render callable -- pandaplot/models/
has zero matplotlib imports today, and this keeps it that way. The actual
per-type render functions live in the GUI layer, in
pandaplot/gui/components/tabs/chart/series_renderers/, keyed by the same
SeriesType via SERIES_RENDERERS.
"""
from dataclasses import dataclass, field
from typing import Literal

from pandaplot.models.chart.series_style import (
    Bar3DSeriesStyle,
    BarSeriesStyle,
    BoxSeriesStyle,
    ColormapSeriesStyle,
    DensitySeriesStyle,
    HeatmapSeriesStyle,
    HistSeriesStyle,
    Line3DSeriesStyle,
    LineSeriesStyle,
    PieSeriesStyle,
    Scatter3DSeriesStyle,
    ScatterSeriesStyle,
    SeriesStyleBase,
    SurfaceSeriesStyle,
    TrisurfSeriesStyle,
    Vector3DSeriesStyle,
    VectorSeriesStyle,
    WireframeSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType


@dataclass(frozen=True)
class SeriesTypeSpec:
    marker_mode: Literal["required", "optional", "unsupported"]
    supports_line_style: bool
    # Whether the series' color/opacity controls (line_color_row,
    # line_opacity_slider -- writing style.color/style.alpha) apply to
    # this type. True for line/bar/hist (all read style.color/alpha in
    # their series_renderers module); False for scatter/vector, which
    # rely on style.marker.marker_color/marker_edge_color instead. Distinct
    # from supports_line_style, which is specifically about
    # line_style/line_width (only true for "line") -- a bar/hist series has
    # no line style but still needs its color/opacity card shown.
    supports_color: bool
    supports_fill: bool
    supports_error_bars: bool
    needs_x_column: bool
    needs_secondary_columns: bool
    # Whether this type needs a Z column, picked on the Data tab via a
    # dedicated combo (mirrors needs_secondary_columns for Vector's
    # U/V/magnitude). What Z *means* differs by type -- a color channel
    # for COLORMAP/HEATMAP, a third spatial axis for every 3-D type -- so
    # this says only "the Data tab must offer a Z picker"; see
    # uses_color_scale for the color question.
    needs_z_column: bool
    # Whether the Style tab's gridding mode + resolution controls apply,
    # i.e. whether this type's renderer feeds its (x, y, z) through
    # chart_heatmap.build_heatmap_grid. True for HEATMAP/SURFACE/WIREFRAME.
    # False for COLORMAP and TRISURF, which consume the scattered points
    # directly (a scatter needs no grid; plot_trisurf triangulates its own).
    supports_gridding: bool
    # Whether this type's color comes from the CHART-level shared color
    # scale (Chart.config's colormap/color_vmin/color_vmax, and the single
    # colorbar chart_editor.py draws). Distinct from needs_z_column, which
    # only says a Z column is picked on the Data tab: a Scatter3D series
    # needs Z as a genuine third *spatial* axis while still drawing in a
    # flat style.color, so it must NOT contribute to the shared color scale
    # or put a Color Map card in front of the user (a silently-ignored
    # control). True only for COLORMAP/HEATMAP/SURFACE/TRISURF.
    uses_color_scale: bool
    # Whether this type renders on a matplotlib mplot3d axes. Mirrors
    # ChartTypeSpec.is_3d; kept per-series-type too because the renderer
    # dispatches on the SERIES' type, and a chart may legitimately mix
    # types (a Scatter3D overlay on a Surface chart).
    is_3d: bool
    # Whether this type represents a single ordered (x, y) curve, which is
    # what ChartAnalysisPanel's derivative/integral/arc-length/smoothing/
    # interpolation operations assume (see AnalyzeChartSeriesCommand). True
    # only for LINE/SCATTER: BAR/HIST have no meaningful curve to
    # differentiate/integrate, VECTOR's (x, y) is an arrow's tail position
    # rather than a curve, COLORMAP/HEATMAP's points are an unordered 2-D
    # scatter (not a sequence), and every 3-D type would silently drop its Z
    # dimension if analyzed as a flat (x, y) pair.
    supports_curve_analysis: bool
    # Whether this type's renderer can annotate each rendered point/bar with
    # its own numeric value (#125) -- a Line/Scatter point's Y value, or a
    # Bar's height (a Stacked Bar segment's own height, not the running
    # stack total). True only for LINE/SCATTER/BAR/STACKED_BAR: HIST's bars represent a
    # computed count matplotlib itself picks bin edges for (no single
    # "value" column to label from series data the way a Bar chart's height
    # already is one), VECTOR/COLORMAP/HEATMAP/every 3-D type have no single
    # scalar value per plotted element that a flat text label reads naturally.
    supports_value_labels: bool
    style_cls: type[SeriesStyleBase]
    # Whether this type needs a THIRD secondary column (a vector's W
    # component) on top of the U/V pair needs_secondary_columns already
    # covers -- only True for VECTOR3D, whose arrows have a Z-axis
    # component 2-D Vector's U/V pair has no equivalent of. Meaningless
    # (and always False) unless needs_secondary_columns is also True.
    needs_w_column: bool = False
    # Whether each of this type's values is drawn ON TOP of the values every
    # earlier series of the same type already placed at the same X (and on
    # the same Y axis), rather than from zero -- only True for STACKED_BAR.
    # It's the one cross-series rendering behavior: everything else that
    # positions a value against the Y axis (error bars, the Axes tab's
    # data-derived range) must offset by the same running stack the renderer
    # does, so it reads this flag rather than testing the series type.
    is_stacked: bool = field(default=False, kw_only=True)
    # Whether this type takes an optional per-point text-label column (a
    # pie's wedge/category names), picked on the Data tab via its own
    # combo. Optional by definition: a blank label column never fails the
    # series, it just renders unlabeled. Only True for PIE.
    needs_label_column: bool = False


SERIES_TYPE_SPECS: dict[SeriesType, SeriesTypeSpec] = {
    SeriesType.LINE: SeriesTypeSpec(
        marker_mode="optional", supports_line_style=True, supports_color=True, supports_fill=True,
        supports_error_bars=True, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=True,
        supports_value_labels=True,
        style_cls=LineSeriesStyle,
    ),
    SeriesType.SCATTER: SeriesTypeSpec(
        marker_mode="required", supports_line_style=False, supports_color=False, supports_fill=True,
        supports_error_bars=True, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=True,
        supports_value_labels=True,
        style_cls=ScatterSeriesStyle,
    ),
    SeriesType.BAR: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=True, supports_fill=False,
        supports_error_bars=True, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=True,
        style_cls=BarSeriesStyle,
    ),
    # Stacked Bar: the same styling surface as Bar (it reuses BarSeriesStyle
    # unchanged), differing only in where each bar starts -- see is_stacked.
    SeriesType.STACKED_BAR: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=True, supports_fill=False,
        supports_error_bars=True, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=True,
        style_cls=BarSeriesStyle,
        is_stacked=True,
    ),
    SeriesType.HIST: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=True, supports_fill=False,
        supports_error_bars=False, needs_x_column=False, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=HistSeriesStyle,
    ),
    # Density: a KDE curve computed from one values column -- Hist's exact
    # column shape (no X), drawn as a smooth line instead of binned bars.
    # supports_curve_analysis is False for the same reason as Hist: the
    # plotted (x, y) is a derived estimate, not the series' own data, so
    # differentiating/integrating "it" would silently analyze something
    # other than what the user picked. supports_fill means "can shade the
    # area under the curve" -- Density's fill is its own two-field variant
    # (DensitySeriesStyle), not FillStyleFields, so the Style tab shows its
    # Density card rather than the generic Fill card for it.
    SeriesType.DENSITY: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=True, supports_color=True, supports_fill=True,
        supports_error_bars=False, needs_x_column=False, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=DensitySeriesStyle,
    ),
    SeriesType.VECTOR: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=True,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=VectorSeriesStyle,
    ),
    SeriesType.COLORMAP: SeriesTypeSpec(
        marker_mode="required", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=True, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=ColormapSeriesStyle,
    ),
    SeriesType.HEATMAP: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=True,
        uses_color_scale=True, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=HeatmapSeriesStyle,
    ),
    # Pie: one wedge per row of the "values" column (y_column_id, the same
    # role Hist uses), so no X. No flat color (wedges take the default
    # color cycle -- see PieSeriesStyle), no curve to analyze, and its own
    # show_percentages stands in for the generic value-labels system.
    SeriesType.PIE: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=False, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=PieSeriesStyle,
        needs_label_column=True,
    ),
    # -- 3-D types (is_3d=True) ------------------------------------------
    # None of these support error bars: mplot3d has no errorbar() at all.
    # All need a Z column -- their third *spatial* axis.
    SeriesType.SCATTER3D: SeriesTypeSpec(
        marker_mode="required", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=False, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=Scatter3DSeriesStyle,
    ),
    SeriesType.LINE3D: SeriesTypeSpec(
        marker_mode="optional", supports_line_style=True, supports_color=True, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=False, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=Line3DSeriesStyle,
    ),
    SeriesType.SURFACE: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=True,
        uses_color_scale=True, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=SurfaceSeriesStyle,
    ),
    SeriesType.WIREFRAME: SeriesTypeSpec(
        # supports_color (not uses_color_scale): plot_wireframe draws
        # lines, which matplotlib doesn't color-map per vertex, so this
        # type takes a single flat style.color like a Line series does.
        marker_mode="unsupported", supports_line_style=True, supports_color=True, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=True,
        uses_color_scale=False, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=WireframeSeriesStyle,
    ),
    SeriesType.BAR3D: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=True, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=False, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=Bar3DSeriesStyle,
    ),
    SeriesType.TRISURF: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=False,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=True, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=TrisurfSeriesStyle,
    ),
    # Vector3D: a 3-D quiver plot. Z is the arrow's spatial tail position
    # (needs_z_column, like every other 3-D type), and needs_secondary_
    # columns + needs_w_column together require the U/V/W components that
    # make up the arrow itself -- the 3-D analogue of Vector's U/V pair.
    SeriesType.VECTOR3D: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=False, supports_fill=False,
        supports_error_bars=False, needs_x_column=True, needs_secondary_columns=True,
        needs_z_column=True, supports_gridding=False,
        uses_color_scale=False, is_3d=True,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=Vector3DSeriesStyle,
        needs_w_column=True,
    ),
    # Box: like HIST, a single "values" column (resolved into y_data) with
    # no X -- each series is one box, positioned among its sibling box
    # series by the renderer rather than by any column. No error bars:
    # boxplot's whiskers/outliers ARE its spread display, and the generic
    # errorbar() pass would draw a second, unrelated spread on top.
    SeriesType.BOX: SeriesTypeSpec(
        marker_mode="unsupported", supports_line_style=False, supports_color=True, supports_fill=False,
        supports_error_bars=False, needs_x_column=False, needs_secondary_columns=False,
        needs_z_column=False, supports_gridding=False,
        uses_color_scale=False, is_3d=False,
        supports_curve_analysis=False,
        supports_value_labels=False,
        style_cls=BoxSeriesStyle,
    ),
}
