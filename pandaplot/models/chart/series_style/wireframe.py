"""Style fields for a "wireframe" series -- the same gridded lattice a
"surface" series builds (see surface.py for why the gridding fields carry
the heatmap names), drawn as an unfilled mesh with
``Axes3D.plot_wireframe``.

Unlike Surface/Trisurf this type has a single flat ``color`` and takes no
part in the chart's shared color scale: plot_wireframe draws lines, which
matplotlib does not color-map per vertex."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class WireframeSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    line_style: str = "solid"
    line_width: float = 1.0
    z_column_id: str = ""
    z_column: str = ""
    heatmap_gridding: str = "grid"  # "grid" | "binned" | "interpolated"
    heatmap_resolution: int = 50
    # Draw every Nth grid row/column. mplot3d's own default is 1 for
    # plot_wireframe, which turns a finely-gridded dataset into an
    # unreadable solid block -- these are exposed so a dense grid can be
    # thinned without re-gridding the data.
    row_stride: int = 1
    column_stride: int = 1
