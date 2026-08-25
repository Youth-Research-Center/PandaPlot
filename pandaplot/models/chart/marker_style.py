"""Marker styling shared by every marker-capable series type (LINE, SCATTER,
COLORMAP). Extracted from LineSeriesStyle/ScatterSeriesStyle so a future
marker-capable series type reuses these fields via composition instead of
duplicating them.

`marker_edge_color` defaults to "" (empty), the same "inherit" sentinel
`marker_color` uses: renderers treat an empty edge color as "match the
fill" rather than a literal color, so a fresh series starts with a
matching fill/edge, still independently editable via the Style tab.
"""
from dataclasses import dataclass


@dataclass
class MarkerStyle:
    marker_color: str = ""
    marker_edge_color: str = ""
    marker_edge_width: float = 1.0
    marker_style: str = "circle"
    marker_size: float = 2.0
