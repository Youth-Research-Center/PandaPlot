"""Renders a "line3d" series -- a polyline through (x, y, z), with
optional markers at each point. The Axes3D counterpart of line.py, minus
its area fill (no ``fill_between`` exists for mplot3d)."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import LINESTYLE_MAP, MARKER_MAP
from pandaplot.models.chart.series_style import Line3DSeriesStyle


def render_line3d_series(axes, series_data: SeriesData, style: Line3DSeriesStyle,
                          label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    mfc = style.marker.marker_color or style.color
    mec = style.marker.marker_edge_color or style.color
    axes.plot(series_data.x_data, series_data.y_data, series_data.z_data,
              color=style.color,
              linewidth=style.line_width,
              linestyle=LINESTYLE_MAP.get(style.line_style, "-"),
              marker=MARKER_MAP.get(style.marker.marker_style, "o"),
              markersize=style.marker.marker_size,
              markerfacecolor=mfc,
              markeredgecolor=mec,
              markeredgewidth=style.marker.marker_edge_width,
              label=label,
              alpha=alpha)
