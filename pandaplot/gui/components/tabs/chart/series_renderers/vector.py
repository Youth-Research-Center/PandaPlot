"""Renders a "vector" series (quiver plot) -- colored by a flat
vector_color unless both a magnitude column was resolved AND a colormap
is set, in which case magnitude drives per-arrow coloring instead."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import VectorSeriesStyle


def render_vector_series(axes, series_data: SeriesData, style: VectorSeriesStyle,
                          label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    quiver_kwargs = {
        "scale": style.vector_scale if style.vector_scale > 0 else None,
        "width": style.vector_width,
        "headwidth": style.vector_head_width,
        "headlength": style.vector_head_length,
        "headaxislength": style.vector_head_axis_length,
        "label": label,
        "alpha": alpha,
    }
    if series_data.magnitude_data is not None and style.vector_colormap:
        axes.quiver(series_data.x_data, series_data.y_data,
                    series_data.u_data, series_data.v_data,
                    series_data.magnitude_data,
                    cmap=style.vector_colormap,
                    **quiver_kwargs)
    else:
        axes.quiver(series_data.x_data, series_data.y_data,
                    series_data.u_data, series_data.v_data,
                    color=style.vector_color,
                    **quiver_kwargs)
