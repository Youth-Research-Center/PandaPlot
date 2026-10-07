"""Area-fill style fields shared by every series type that can be filled
(Line and Scatter) -- read by
pandaplot/gui/components/tabs/chart/series_renderers/fill.py."""
from dataclasses import dataclass


@dataclass
class FillStyleFields:
    fill_enabled: bool = False
    fill_color: str = ""
    fill_alpha: float = 0.3
    fill_orientation: str = "vertical"
    fill_base: float = 0.0
    fill_to_index: int = -1
    # Restrict the fill to a run of data points -- e.g. to shade/integrate
    # over just one segment of a curve (#280). The bounds are 0-based row
    # positions into the series' data (both inclusive); the UI shows them
    # 1-based to match the dataset table's row numbers. fill_range_end == -1
    # means "through the last point", so the default range is the whole
    # series. Only read when fill_range_enabled.
    fill_range_enabled: bool = False
    fill_range_start: int = 0
    fill_range_end: int = -1
