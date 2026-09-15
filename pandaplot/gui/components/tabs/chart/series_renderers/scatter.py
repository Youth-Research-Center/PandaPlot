"""Renders a "scatter" series -- marker fields only, no line/fill."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.value_labels import annotate_point_labels
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
    if style.show_value_labels:
        annotate_point_labels(
            axes, series_data.x_data, series_data.y_data,
            mode=style.value_label_mode,
            show_arrow=style.value_label_show_arrow,
            offset_x=style.value_label_offset_x,
            offset_y=style.value_label_offset_y,
            text_color=style.value_label_text_color or mfc,
            bg_color=style.value_label_bg_color,
            bg_alpha=style.value_label_bg_alpha,
            alpha=alpha,
        )
