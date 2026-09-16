"""Renders a "fit" series -- reproduces chart_editor.py's former separate
fit-rendering loop exactly (line via render_line_series + confidence band
via fill_between), now dispatched through SERIES_RENDERERS like every
other type (#304)."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import LineSeriesStyle


def render_fit_series(axes, series_data: SeriesData, style: FitStyle,
                       label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    line_style_adapter = LineSeriesStyle(
        color=style.color,
        line_style=style.line_style,
        line_width=style.line_width,
        marker=MarkerStyle(marker_style="none"),
        fill_enabled=False,
    )
    render_line_series(axes, series_data, line_style_adapter, label, alpha,
                        visible=visible, extra={})

    if (style.band_fill_enabled
            and style.confidence_lower is not None
            and style.confidence_upper is not None):
        band_color = style.band_color or style.color
        axes.fill_between(
            series_data.x_data,
            style.confidence_lower,
            style.confidence_upper,
            color=band_color,
            alpha=style.band_fill_alpha)
