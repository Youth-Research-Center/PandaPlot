"""Style fields for a "surface" series -- (x, y, z) gridded into a regular
lattice and drawn as a shaded surface with ``Axes3D.plot_surface``.

Gridding reuses the heatmap machinery verbatim (chart_heatmap.
build_heatmap_grid), so the field names are the heatmap ones
(``heatmap_gridding``/``heatmap_resolution``): SeriesTypeSpec.
supports_gridding is what the Style tab's Gridding card keys off, and
sharing the field names means that card reads/writes this class with no
per-type branching.

The colormap name and color-scale limits are NOT here -- they're
chart-level config shared with every other color-scaled series (see
ColormapSeriesStyle's docstring)."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class SurfaceSeriesStyle(SeriesStyleBase):
    z_column_id: str = ""
    z_column: str = ""
    heatmap_gridding: str = "grid"  # "grid" | "binned" | "interpolated"
    heatmap_resolution: int = 50
    edge_color: str = ""
    edge_width: float = 0.0
    shade: bool = True

    @property
    def swatch_color(self) -> str:
        return ""
