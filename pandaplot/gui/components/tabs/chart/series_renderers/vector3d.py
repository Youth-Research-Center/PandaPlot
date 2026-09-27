"""Renders a "vector3d" series -- a 3-D quiver plot. The Axes3D
counterpart of vector.py: same idea (an arrow per row, tail position plus
components), but ``Axes3D.quiver`` takes a different keyword set than 2-D
``Axes.quiver`` (``length``/``arrow_length_ratio``/``normalize`` instead
of ``scale``/``width``/``headwidth``/``headlength``/``headaxislength``)
and has no per-arrow colormap support -- so this always draws in a flat
``vector_color``, the same reasoning render_scatter3d_series documents for
why a 3-D type takes no part in the shared color scale."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import Vector3DSeriesStyle


def render_vector3d_series(axes, series_data: SeriesData, style: Vector3DSeriesStyle,
                            label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    axes.quiver(series_data.x_data, series_data.y_data, series_data.z_data,
                series_data.u_data, series_data.v_data, series_data.w_data,
                length=style.vector_length,
                arrow_length_ratio=style.vector_arrow_ratio,
                normalize=style.vector_normalize,
                color=style.vector_color,
                label=label,
                alpha=alpha)
