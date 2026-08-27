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
from pandaplot.gui.components.tabs.chart.series_renderers.colormap import render_colormap_series
from pandaplot.gui.components.tabs.chart.series_renderers.heatmap import render_heatmap_series
from pandaplot.gui.components.tabs.chart.series_renderers.hist import render_hist_series
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.gui.components.tabs.chart.series_renderers.scatter import render_scatter_series
from pandaplot.gui.components.tabs.chart.series_renderers.vector import render_vector_series
from pandaplot.models.chart.series_type import SeriesType

SERIES_RENDERERS: dict[SeriesType, Callable] = {
    SeriesType.LINE: render_line_series,
    SeriesType.SCATTER: render_scatter_series,
    SeriesType.BAR: render_bar_series,
    SeriesType.HIST: render_hist_series,
    SeriesType.VECTOR: render_vector_series,
    SeriesType.COLORMAP: render_colormap_series,
    SeriesType.HEATMAP: render_heatmap_series,
}

__all__ = [
    "SERIES_RENDERERS",
    "render_line_series",
    "render_scatter_series",
    "render_bar_series",
    "render_hist_series",
    "render_vector_series",
    "render_colormap_series",
    "render_heatmap_series",
]
