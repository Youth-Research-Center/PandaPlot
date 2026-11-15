"""Renders a "fit" series: its curve via render_line_series, an optional
area fill via the shared render_area_fill (#431), and an optional confidence
band via fill_between, dispatched through SERIES_RENDERERS like every other
type (#304)."""
from matplotlib.axes import Axes

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.fill import render_area_fill
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import LineSeriesStyle

# Matplotlib gid of a fit's confidence-band artist, so the legend can tell it
# apart from the fit's area fill (both are PolyCollections tracked for the
# same series).
CONFIDENCE_BAND_GID = "pandaplot-fit-confidence-band"


def render_fit_series(axes: Axes, series_data: SeriesData, style: FitStyle,
                       label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    """Draw a fit's curve (as a marker-less line) plus its optional area fill and confidence band on `axes`.

    The area fill and the confidence band are independent, each with its own
    color and opacity. When both are on they stack in a fixed order: the area
    fill at the bottom, the band above it and the fit line on top (fills keep
    matplotlib's default zorder 1, below the line's 2, and the area fill is
    added first), so the curve stays readable.

    Draws nothing on a 3-D axes: a fit only has 2-D curve data, and mplot3d
    rejects the band's `fill_between`. A fit may stay on a chart that was
    switched to a 3-D type (see Chart.set_chart_type), so this must not raise.
    """
    if getattr(axes, "name", "") == "3d":
        return
    line_style_adapter = LineSeriesStyle(
        color=style.color,
        line_style=style.line_style,
        line_width=style.line_width,
        marker=MarkerStyle(marker_style="none"),
        fill_enabled=False,
    )
    render_line_series(axes, series_data, line_style_adapter, label, alpha,
                        visible=visible, extra={})

    if style.fill_enabled:
        render_area_fill(axes, series_data, style, color=style.fill_color or style.color, visible=visible, extra=extra)

    if (style.band_fill_enabled
            and style.confidence_lower is not None
            and style.confidence_upper is not None):
        band_color = style.band_color or style.color
        # Matches render_line_series's fill-visibility scaling (line.py):
        # a hidden fit's line already renders at alpha=0.3 (chart_editor.py
        # passes the pre-faded alpha in), but the band draws through this
        # separate fill_between call with its own alpha, so it needs the
        # same 0.3x scaling explicitly -- otherwise a hidden fit's band
        # stays fully opaque while its line fades.
        band_fill_alpha = style.band_fill_alpha if visible else 0.3 * style.band_fill_alpha
        if style.band_orientation == "horizontal":
            axes.fill_betweenx(
                series_data.y_data,
                style.confidence_lower,
                style.confidence_upper,
                color=band_color,
                alpha=band_fill_alpha,
                gid=CONFIDENCE_BAND_GID)
        else:
            axes.fill_between(
                series_data.x_data,
                style.confidence_lower,
                style.confidence_upper,
                color=band_color,
                alpha=band_fill_alpha,
                gid=CONFIDENCE_BAND_GID)
