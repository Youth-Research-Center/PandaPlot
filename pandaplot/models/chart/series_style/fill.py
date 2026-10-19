"""Area-fill style fields shared by every series type that can be filled
(Line and Scatter) -- read by
pandaplot/gui/components/tabs/chart/series_renderers/fill.py."""
from dataclasses import dataclass, field


@dataclass
class FillStyleFields:
    fill_enabled: bool = False
    fill_color: str = ""
    fill_alpha: float = 0.3
    fill_orientation: str = "vertical"
    fill_base: float = 0.0
    fill_to_index: int = -1
    # Optional 0-based, inclusive data-point ranges, displayed as 1-based
    # rows in the Style tab. An empty list means the whole series. Only read
    # when fill_range_enabled; all sections share the series fill style.
    fill_range_enabled: bool = False
    fill_sections: list[tuple[int, int]] = field(default_factory=list)
