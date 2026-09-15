"""Style fields for a "line" series -- the only type that reads
line_style/line_width/fill_* in render_line_series()
(pandaplot/gui/components/tabs/chart/series_renderers/line.py)."""
from dataclasses import dataclass, field

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class LineSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    line_style: str = "solid"
    line_width: float = 2.0
    fill_enabled: bool = False
    fill_color: str = ""
    fill_alpha: float = 0.3
    fill_orientation: str = "vertical"
    fill_base: float = 0.0
    fill_to_index: int = -1
    marker: MarkerStyle = field(default_factory=MarkerStyle)
    error_bars: ErrorBarConfig = field(default_factory=ErrorBarConfig)
    # Annotate each rendered point with its numeric Y value (#125) -- see
    # SeriesTypeSpec.supports_value_labels and series_renderers/value_labels.py.
    show_value_labels: bool = False
    # Which value(s) the label shows: "x", "y", or "xy" (both, comma-separated).
    value_label_mode: str = "y"
    # Draw a leader line from the point to the (possibly offset) label.
    value_label_show_arrow: bool = False
    # Label offset from the point, in points (matches the historical hardcoded (0, 6)).
    value_label_offset_x: float = 0.0
    value_label_offset_y: float = 6.0
    # "" means inherit (no explicit text color override).
    value_label_text_color: str = ""
    # "" means no background box drawn; bg_alpha only applies when bg_color is set.
    value_label_bg_color: str = ""
    value_label_bg_alpha: float = 1.0
