"""Renders a "bar3d" series -- one box per (x, y) sample, rising from
z=0 to that sample's z.

bar3d() takes the *near corner* of each box plus its extents, so the x/y
coordinates are shifted back by half a box to leave each bar centered on
its own data point (matching how a 2-D bar chart centers on its x value).
Box width/depth come from style.bar_width/bar_depth as fractions of the
data's own spacing -- see chart_3d.resolve_bar_footprint.

Returns the Poly3DCollection bar3d draws, or None when there's nothing to
draw (see SERIES_RENDERERS_REPORTING_NO_DATA) -- the artist is returned
only so a successful render is distinguishable from that failure, never
for a colorbar: the boxes are colored flat, not through the chart's color
scale. matplotlib has no legend handler for it, so no `label` is passed."""
import numpy as np

from pandaplot.gui.components.tabs.chart.chart_3d import resolve_bar_footprint
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import Bar3DSeriesStyle


def render_bar3d_series(axes, series_data: SeriesData, style: Bar3DSeriesStyle,
                         label: str, alpha: float, *, visible: bool, extra: dict):
    try:
        x = np.asarray(series_data.x_data, dtype=float)
        y = np.asarray(series_data.y_data, dtype=float)
        z = np.asarray(series_data.z_data, dtype=float)
    except (ValueError, TypeError):
        return None
    if x.size == 0 or y.size == 0 or z.size == 0:
        return None

    dx = resolve_bar_footprint(x, style.bar_width)
    dy = resolve_bar_footprint(y, style.bar_depth)
    return axes.bar3d(x - dx / 2, y - dy / 2, np.zeros_like(z), dx, dy, z,
                      color=style.color, shade=style.shade, alpha=alpha)
