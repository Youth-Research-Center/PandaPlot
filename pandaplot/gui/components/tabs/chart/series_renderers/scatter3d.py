"""Renders a "scatter3d" series -- a 3-D point cloud. The Axes3D
counterpart of scatter.py: same marker fields, one more coordinate.

Unlike a Colormap series (whose Z is a color channel), Z here is the
third spatial axis, so points draw in a flat style.color and this returns
None -- there is no mappable for a colorbar to attach to."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import MARKER_MAP
from pandaplot.models.chart.series_style import Scatter3DSeriesStyle


def render_scatter3d_series(axes, series_data: SeriesData, style: Scatter3DSeriesStyle,
                             label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    mfc = style.marker.marker_color or style.color
    mec = style.marker.marker_edge_color or style.color
    axes.scatter(series_data.x_data, series_data.y_data, series_data.z_data,
                 c=mfc,
                 edgecolors=mec,
                 linewidths=style.marker.marker_edge_width,
                 marker=MARKER_MAP.get(style.marker.marker_style, "o"),
                 s=style.marker.marker_size ** 2,
                 label=label,
                 alpha=alpha)
