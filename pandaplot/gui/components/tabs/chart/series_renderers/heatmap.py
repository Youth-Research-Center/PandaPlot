"""Renders a "heatmap" series in one of two geometry pipelines, each able to
draw in one of four `style.render_mode`s:

- Gridded (`style.heatmap_gridding` in "grid"/"binned"/"interpolated"):
  (x, y, z) is pivoted/binned/interpolated onto a regular lattice via
  chart_heatmap.build_heatmap_grid, then drawn with pcolormesh/contour/
  contourf.
- Triangulated (`style.heatmap_gridding == "triangulated"`): the raw
  scattered points are used directly (after chart_heatmap.
  filter_finite_xyz), drawn with matplotlib's own Delaunay-triangulation
  equivalents -- tripcolor/tricontour/tricontourf -- which need no lattice
  at all and suit irregular/scattered data better than gridding does.

Returns None (not a mappable) when there's no data to render, so the caller
can skip the colorbar and surface a per-series error instead of drawing an
empty axes.

The colormap name and color-scale limits are shared across every
Colormap/Heatmap series on the chart -- see colormap.py's module
docstring for why they come from `extra`, not `style`."""
from pandaplot.gui.components.tabs.chart.chart_heatmap import build_heatmap_grid, filter_finite_xyz
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import HeatmapSeriesStyle

# Contour lines drawn together with a filled contour use a fixed neutral
# color instead of the shared colormap -- lines colored the same as the
# fill they sit on top of would be invisible.
_OVERLAID_LINE_COLOR = "black"


def _draw_contours(axes, x, y, z, style: HeatmapSeriesStyle, cmap: str,
                    vmin, vmax, alpha: float, filled_fn, lines_fn):
    """Shared "draw filled/lines/both per style.render_mode" logic for both
    the gridded (contour/contourf) and triangulated (tricontour/
    tricontourf) pipelines -- `filled_fn`/`lines_fn` are the two matplotlib
    calls to make, already bound to their (x, y, z) arguments.

    clabel (contour_line_labels) is best-effort: a contour set with no
    actual lines (e.g. a perfectly flat field) makes matplotlib raise
    inside clabel, which is swallowed here rather than blanking the whole
    chart over a cosmetic label placement failure.
    """
    levels = max(2, int(style.contour_levels))
    mappable = None
    if style.render_mode in ("contour_filled", "contour_filled_lines"):
        mappable = filled_fn(levels, cmap, vmin, vmax)
    if style.render_mode in ("contour_lines", "contour_filled_lines"):
        line_cmap = None if mappable is not None else cmap
        line_color = _OVERLAID_LINE_COLOR if mappable is not None else None
        contour_set = lines_fn(levels, line_cmap, line_color, vmin, vmax, style.contour_line_width)
        if style.contour_line_labels:
            try:
                axes.clabel(contour_set, inline=True, fontsize=8)
            except (ValueError, RuntimeError):
                pass
        if mappable is None:
            mappable = contour_set
    return mappable


def render_heatmap_series(axes, series_data: SeriesData, style: HeatmapSeriesStyle,
                           label: str, alpha: float, *, visible: bool, extra: dict):
    vmin, vmax = extra["color_limits"]
    cmap = extra["colormap"]
    try:
        if style.heatmap_gridding == "triangulated":
            return _render_triangulated(axes, series_data, style, cmap, vmin, vmax, alpha)
        return _render_gridded(axes, series_data, style, cmap, vmin, vmax, alpha)
    except ValueError:
        return None
    except RuntimeError:
        # Degenerate triangulation (e.g. all points collinear) -- matplotlib's
        # qhull-backed Triangulation raises RuntimeError, not ValueError, for
        # this. Only reachable from the triangulated pipeline.
        return None


def _render_gridded(axes, series_data: SeriesData, style: HeatmapSeriesStyle,
                     cmap: str, vmin, vmax, alpha: float):
    xs, ys, grid = build_heatmap_grid(
        series_data.x_data, series_data.y_data, series_data.z_data,
        style.heatmap_gridding, style.heatmap_resolution)

    if style.render_mode == "mesh":
        # Note: unlike every other renderer here, `label` is deliberately
        # NOT passed through to pcolormesh. matplotlib's Legend has no
        # handler for QuadMesh (the artist pcolormesh returns) -- passing a
        # label achieves nothing and only produces a "Legend does not
        # support handles for QuadMesh instances" UserWarning on every
        # render. chart_editor.py separately skips axes.legend() entirely
        # when there are no real legend handles, rather than trying to
        # manufacture one here.
        return axes.pcolormesh(
            xs, ys, grid, cmap=cmap, vmin=vmin, vmax=vmax,
            shading="nearest", alpha=alpha)

    return _draw_contours(
        axes, xs, ys, grid, style, cmap, vmin, vmax, alpha,
        filled_fn=lambda levels, c, lo, hi: axes.contourf(
            xs, ys, grid, levels=levels, cmap=c, vmin=lo, vmax=hi, alpha=alpha),
        lines_fn=lambda levels, c, color, lo, hi, lw: axes.contour(
            xs, ys, grid, levels=levels, cmap=c, colors=color, vmin=lo, vmax=hi, alpha=alpha,
            linewidths=lw),
    )


def _render_triangulated(axes, series_data: SeriesData, style: HeatmapSeriesStyle,
                          cmap: str, vmin, vmax, alpha: float):
    x, y, z = filter_finite_xyz(series_data.x_data, series_data.y_data, series_data.z_data)

    if style.render_mode == "mesh":
        # tripcolor's Gouraud shading interpolates color across each
        # triangle (vs. pcolormesh's flat-shaded cells), the natural
        # analogue for data with no grid to be flat-shaded per cell.
        return axes.tripcolor(
            x, y, z, cmap=cmap, vmin=vmin, vmax=vmax, alpha=alpha, shading="gouraud")

    return _draw_contours(
        axes, x, y, z, style, cmap, vmin, vmax, alpha,
        filled_fn=lambda levels, c, lo, hi: axes.tricontourf(
            x, y, z, levels=levels, cmap=c, vmin=lo, vmax=hi, alpha=alpha),
        lines_fn=lambda levels, c, color, lo, hi, lw: axes.tricontour(
            x, y, z, levels=levels, cmap=c, colors=color, vmin=lo, vmax=hi, alpha=alpha,
            linewidths=lw),
    )
