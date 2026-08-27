"""Renders a "scatter" series -- marker fields only, no line/fill."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import MARKER_MAP
from pandaplot.models.chart.series_style import ScatterSeriesStyle


def render_scatter_series(axes, series_data: SeriesData, style: ScatterSeriesStyle,
                           label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    mfc = style.marker.marker_color or style.color
    mec = style.marker.marker_edge_color or style.color
    axes.scatter(series_data.x_data, series_data.y_data,
                 c=mfc,
                 edgecolors=mec,
                 linewidths=style.marker.marker_edge_width,
                 marker=MARKER_MAP.get(style.marker.marker_style, "o"),
                 s=style.marker.marker_size ** 2,
                 label=label,
                 alpha=alpha)
