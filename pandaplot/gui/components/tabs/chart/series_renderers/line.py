"""Renders a "line" series -- reproduces chart_editor.py's former "line"
branch exactly (color/line_style/line_width/marker fields, plus the
optional area fill)."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.value_labels import annotate_point_labels
from pandaplot.gui.components.tabs.chart.style_maps import LINESTYLE_MAP, MARKER_MAP
from pandaplot.models.chart.series_style import LineSeriesStyle


def render_line_series(axes, series_data: SeriesData, style: LineSeriesStyle,
                        label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    mfc = style.marker.marker_color or style.color
    mec = style.marker.marker_edge_color or style.color
    axes.plot(series_data.x_data, series_data.y_data,
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
    if style.show_value_labels:
        annotate_point_labels(
            axes, series_data.x_data, series_data.y_data,
            mode=style.value_label_mode,
            show_arrow=style.value_label_show_arrow,
            offset_x=style.value_label_offset_x,
            offset_y=style.value_label_offset_y,
            text_color=style.value_label_text_color or style.color,
            bg_color=style.value_label_bg_color,
            bg_alpha=style.value_label_bg_alpha,
            alpha=alpha,
        )
    if style.fill_enabled:
        resolve_fill_baseline = extra["resolve_fill_baseline"]
        fill_color = style.fill_color or style.color
        fill_alpha = style.fill_alpha if visible else 0.3 * style.fill_alpha
        if style.fill_orientation == "horizontal":
            baseline = resolve_fill_baseline(series_data.y_data, horizontal=True)
            axes.fill_betweenx(series_data.y_data, series_data.x_data, baseline,
                                color=fill_color, alpha=fill_alpha)
        else:
            baseline = resolve_fill_baseline(series_data.x_data, horizontal=False)
            axes.fill_between(series_data.x_data, series_data.y_data, baseline,
                               color=fill_color, alpha=fill_alpha)
