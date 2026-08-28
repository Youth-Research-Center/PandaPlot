"""Renders a "trisurf" series -- a surface over the Delaunay
triangulation of the (x, y) samples themselves, with no gridding step
(that's the point of the type; see TrisurfSeriesStyle). Colored through
the chart's shared color scale, so this returns the mappable for the
colorbar.

Returns None instead when the points can't be triangulated at all --
fewer than three of them, or all collinear, which makes matplotlib's
Delaunay raise. That's the same "nothing to draw" contract
render_surface_series has for an ungriddable series, and it keeps one bad
series from blanking the whole chart."""
import numpy as np

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import TrisurfSeriesStyle


def render_trisurf_series(axes, series_data: SeriesData, style: TrisurfSeriesStyle,
                           label: str, alpha: float, *, visible: bool, extra: dict):
    vmin, vmax = extra["color_limits"]
    try:
        x = np.asarray(series_data.x_data, dtype=float)
        y = np.asarray(series_data.y_data, dtype=float)
        z = np.asarray(series_data.z_data, dtype=float)
    except (ValueError, TypeError):
        return None
    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[finite], y[finite], z[finite]
    if x.size < 3:
        return None
    try:
        return axes.plot_trisurf(
            x, y, z,
            cmap=extra["colormap"], vmin=vmin, vmax=vmax,
            edgecolor=style.edge_color or "none",
            linewidth=style.edge_width,
            shade=style.shade,
            alpha=alpha)
    except (RuntimeError, ValueError):
        # matplotlib.tri raises for a degenerate (e.g. fully collinear)
        # point set, which no amount of styling can fix.
        return None
