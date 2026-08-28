"""Style fields for a "trisurf" series -- a surface built by Delaunay-
triangulating the (x, y) samples directly (``Axes3D.plot_trisurf``), with
no gridding step at all. That's the whole point of the type: it renders
genuinely scattered, non-lattice data that "surface" would first have to
bin or interpolate onto a grid, so it declares no gridding fields (see
SeriesTypeSpec.supports_gridding, False here and True for Surface).

Color comes from the chart-level shared color scale, like Surface."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class TrisurfSeriesStyle(SeriesStyleBase):
    z_column_id: str = ""
    z_column: str = ""
    edge_color: str = ""
    edge_width: float = 0.0
    shade: bool = True

    @property
    def swatch_color(self) -> str:
        return ""
