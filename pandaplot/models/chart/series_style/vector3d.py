"""Style fields for a "vector3d" series -- a 3-D quiver plot drawn with
``Axes3D.quiver(x, y, z, u, v, w)``. Column references (the arrow's tail
position and its U/V/W components) live here, same reasoning as every
other type-specific style class (see vector.py/scatter3d.py).

Deliberately NOT a superset of VectorSeriesStyle's fields: ``Axes3D.quiver``
takes a completely different keyword set than 2-D ``Axes.quiver`` (``length``/
``arrow_length_ratio``/``normalize`` instead of ``scale``/``width``/
``headwidth``/``headlength``/``headaxislength``), and has no per-arrow
colormap support the way 2-D quiver's magnitude-driven coloring does -- so
this class has no ``vector_colormap``/``magnitude_column`` fields at all,
rather than declaring ones that would silently do nothing. See
render_vector3d_series() (series_renderers/vector3d.py)."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class Vector3DSeriesStyle(SeriesStyleBase):
    vector_color: str = "#1f77b4"
    # matplotlib's quiver3d `length`: a uniform scale factor applied to
    # every arrow (not a per-arrow pixel width like 2-D quiver's `scale`).
    vector_length: float = 1.0
    # matplotlib's `arrow_length_ratio`: how much of the arrow's length its
    # head takes up, as a fraction (0-1).
    vector_arrow_ratio: float = 0.3
    # matplotlib's `normalize`: when True every arrow is drawn the same
    # length (direction only), ignoring the U/V/W magnitudes.
    vector_normalize: bool = False
    z_column_id: str = ""
    z_column: str = ""
    u_column_id: str = ""
    v_column_id: str = ""
    w_column_id: str = ""
    u_column: str = ""
    v_column: str = ""
    w_column: str = ""

    @property
    def swatch_color(self) -> str:
        return self.vector_color
