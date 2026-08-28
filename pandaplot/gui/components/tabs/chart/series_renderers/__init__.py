"""SeriesType -> render function dispatch table, replacing chart_editor.py's
former 5 if/elif branches. Every render function shares the signature
(axes, series_data, style, label, alpha, *, visible, extra) -> None --
`visible`/`extra` are keyword-only (ruff FBT001/002/003: boolean-trap
avoidance) since they're only ever called from our own Python code. `extra`
carries the few pieces of per-type context that don't fit the uniform
shape (bins for hist, resolve_fill_baseline for line), ignored by the
renderers that don't need them, so callers can dispatch through one call
site instead of branching to decide which arguments to gather.
"""
from typing import Callable

from pandaplot.gui.components.tabs.chart.series_renderers.bar import render_bar_series
from pandaplot.gui.components.tabs.chart.series_renderers.bar3d import render_bar3d_series
from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series
from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series
from pandaplot.gui.components.tabs.chart.series_renderers.hist import render_hist_series
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.gui.components.tabs.chart.series_renderers.line3d import render_line3d_series
from pandaplot.gui.components.tabs.chart.series_renderers.scatter import render_scatter_series
from pandaplot.gui.components.tabs.chart.series_renderers.scatter3d import render_scatter3d_series
from pandaplot.gui.components.tabs.chart.series_renderers.surface import render_surface_series
from pandaplot.gui.components.tabs.chart.series_renderers.trisurf import render_trisurf_series
from pandaplot.gui.components.tabs.chart.series_renderers.vector import render_vector_series
from pandaplot.gui.components.tabs.chart.series_renderers.wireframe import render_wireframe_series
from pandaplot.models.chart.series_type import SeriesType

SERIES_RENDERERS: dict[SeriesType, Callable] = {
    SeriesType.LINE: render_line_series,
    SeriesType.SCATTER: render_scatter_series,
    SeriesType.BAR: render_bar_series,
    SeriesType.HIST: render_hist_series,
    SeriesType.VECTOR: render_vector_series,
    SeriesType.COLORMAP: render_colormap_series,
    SeriesType.HEATMAP: render_heatmap_series,
    SeriesType.SCATTER3D: render_scatter3d_series,
    SeriesType.LINE3D: render_line3d_series,
    SeriesType.SURFACE: render_surface_series,
    SeriesType.WIREFRAME: render_wireframe_series,
    SeriesType.BAR3D: render_bar3d_series,
    SeriesType.TRISURF: render_trisurf_series,
}

# The render functions whose contract is to return None when they have
# nothing to draw -- they transform their inputs first (grid them,
# triangulate them, coerce them to float) and that step can fail on data
# the user is free to configure. chart_editor.py turns a None from one of
# these into a per-series "no data" message instead of silently rendering
# an empty axes. Every other renderer returns None unconditionally (it
# draws directly and has no failure mode to report), so a None from one
# of those means nothing at all -- which is exactly why this set has to
# exist rather than the caller testing `mappable is None` for everything.
SERIES_RENDERERS_REPORTING_NO_DATA: frozenset[SeriesType] = frozenset({
    SeriesType.COLORMAP,
    SeriesType.HEATMAP,
    SeriesType.SURFACE,
    SeriesType.WIREFRAME,
    SeriesType.BAR3D,
    SeriesType.TRISURF,
})

__all__ = [
    "SERIES_RENDERERS",
    "SERIES_RENDERERS_REPORTING_NO_DATA",
    "render_line_series",
    "render_scatter_series",
    "render_bar_series",
    "render_hist_series",
    "render_vector_series",
    "render_colormap_series",
    "render_heatmap_series",
    "render_scatter3d_series",
    "render_line3d_series",
    "render_surface_series",
    "render_wireframe_series",
    "render_bar3d_series",
    "render_trisurf_series",
]
