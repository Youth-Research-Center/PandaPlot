"""Renders a "colormap" series: a scatter whose fill color comes from
series_data.z_data through a colormap, while marker shape/size/edge still
come from style.marker. Returns the matplotlib PathCollection so
chart_editor.py can attach the shared colorbar to it.

The colormap name and color-scale limits come from `extra`, not `style`,
because they're shared across every Colormap/Heatmap series on the chart
(there's only one physical colorbar) and chart_editor.py computes them once.

An empty marker_edge_color resolves to matplotlib's "face" sentinel rather
than a fixed style.color fallback, since fill varies per point -- "face"
makes each point's edge match its own fill.

Z is coerced to numeric, returning None on invalid/empty data (matching
render_heatmap_series' contract), because passing non-numeric strings
straight to scatter(c=...) would either raise uncaught and blank the whole
chart, or silently misread color names as literal marker colors."""
import numpy as np

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import MARKER_MAP
from pandaplot.models.chart.series_style import ColormapSeriesStyle


def render_colormap_series(axes, series_data: SeriesData, style: ColormapSeriesStyle,
                            label: str, alpha: float, *, visible: bool, extra: dict):
    try:
        z_data = np.asarray(series_data.z_data, dtype=float)
    except (ValueError, TypeError):
        return None
    if z_data.size == 0:
        return None
    vmin, vmax = extra["color_limits"]
    return axes.scatter(
        series_data.x_data, series_data.y_data,
        c=z_data, cmap=extra["colormap"], vmin=vmin, vmax=vmax,
        marker=MARKER_MAP.get(style.marker.marker_style, "o"),
        s=style.marker.marker_size ** 2,
        edgecolors=style.marker.marker_edge_color or "face",
        linewidths=style.marker.marker_edge_width,
        label=label, alpha=alpha)
