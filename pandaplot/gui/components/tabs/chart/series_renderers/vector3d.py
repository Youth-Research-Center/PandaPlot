"""Renders a "vector3d" series -- a 3-D quiver plot. The Axes3D
counterpart of vector.py: same idea (an arrow per row, tail position plus
components), but ``Axes3D.quiver`` takes a different keyword set than 2-D
``Axes.quiver`` (``arrow_length_ratio``/``normalize`` instead
of ``scale``/``width``/``headwidth``/``headlength``/``headaxislength``) and
has no colormap support of its own. Like vector.py it draws in a flat
``vector_color`` unless a magnitude column was resolved AND a colormap is
set; then each arrow gets its own color, passed explicitly."""
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import Vector3DSeriesStyle


def _magnitude_mappable(magnitude, colormap: str, count: int) -> ScalarMappable | None:
    """A ScalarMappable spanning the magnitude column's range, or None when
    the magnitude can't be matched one-to-one to the arrows (or has no
    finite value to span). Serves both to color the arrows and as the
    colorbar's mappable."""
    values = np.asarray(magnitude, dtype=float)
    if values.shape != (count,) or not np.isfinite(values).any():
        return None
    mappable = ScalarMappable(norm=Normalize(vmin=np.nanmin(values), vmax=np.nanmax(values)), cmap=colormap)
    mappable.set_array(values)
    return mappable


def render_vector3d_series(axes, series_data: SeriesData, style: Vector3DSeriesStyle,
                            label: str, alpha: float, *, visible: bool, extra: dict) -> ScalarMappable | None:
    """Returns the magnitude ScalarMappable when arrows are colored by
    magnitude (the chart editor draws a colorbar from it), else None."""
    mappable = None
    if series_data.magnitude_data is not None and style.vector_colormap:
        mappable = _magnitude_mappable(series_data.magnitude_data, style.vector_colormap, len(series_data.x_data))
    if mappable is not None:
        # Axes3D.quiver draws each arrow as three segments -- all N shafts,
        # then N first head lines, then N second head lines -- so the
        # per-arrow colors are repeated three times to keep an arrow's
        # shaft and heads together.
        color_kwargs = {"colors": np.tile(mappable.to_rgba(mappable.get_array()), (3, 1))}
    else:
        color_kwargs = {"color": style.vector_color}
    axes.quiver(series_data.x_data, series_data.y_data, series_data.z_data,
                series_data.u_data, series_data.v_data, series_data.w_data,
                arrow_length_ratio=style.vector_arrow_ratio,
                normalize=style.vector_normalize,
                **color_kwargs,
                label=label,
                alpha=alpha)
    return mappable
