"""Style fields for a "heatmap" series -- a gridded matrix drawn with
pcolormesh, or (see `render_mode`) a contour surface. No marker/line/fill
fields (marker_mode is "unsupported"); render_heatmap_series()
(series_renderers/heatmap.py) reads only these plus x/y/z data.
`heatmap_gridding`/`heatmap_resolution` control how scattered (x, y, z)
points become a regular grid -- see chart_heatmap.py. "triangulated" skips
gridding entirely and renders straight from the scattered points via
matplotlib's own Delaunay triangulation (tripcolor/tricontour/tricontourf),
usable with any `render_mode`.

The colormap name and color-scale limits are NOT here -- see
ColormapSeriesStyle's docstring for why (Chart.config instead)."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class HeatmapSeriesStyle(SeriesStyleBase):
    z_column_id: str = ""
    z_column: str = ""
    heatmap_gridding: str = "grid"  # "grid" | "binned" | "interpolated" | "triangulated"
    heatmap_resolution: int = 50
    # "mesh" (pcolormesh/tripcolor, the original behavior) | "contour_lines"
    # | "contour_filled" | "contour_filled_lines". See
    # series_renderers/heatmap.py for how each maps onto matplotlib calls.
    render_mode: str = "mesh"
    # Passed straight to contour/contourf/tricontour/tricontourf as
    # `levels` (an int -- matplotlib itself picks the level boundaries).
    contour_levels: int = 10
    # Inline value labels on contour lines (axes.clabel) -- only meaningful
    # when render_mode actually draws lines ("contour_lines"/
    # "contour_filled_lines").
    contour_line_labels: bool = False
    # Width of the contour lines themselves (matplotlib's `linewidths`).
    # 1.5 matches matplotlib's own rcParams default, so upgrading doesn't
    # change the look of an existing chart. Same "only meaningful while
    # lines are drawn" scope as contour_line_labels.
    contour_line_width: float = 1.5

    @property
    def swatch_color(self) -> str:
        return ""
