"""Style fields for a "bar" series -- color only, plus error bars
(BarSeriesStyle is the one non-marker-capable type that still supports
them -- see SeriesTypeSpec.supports_error_bars)."""
from dataclasses import dataclass, field

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class BarSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    error_bars: ErrorBarConfig = field(default_factory=ErrorBarConfig)
    # Annotate each bar with its numeric height (#125) -- see
    # SeriesTypeSpec.supports_value_labels and series_renderers/value_labels.py.
    show_value_labels: bool = False
    # No value_label_mode/show_arrow/offset here: bar_label() has a single
    # scalar height (no separate X value worth choosing), and matplotlib
    # already positions labels correctly above/below each bar with no
    # offset/arrow concept.
    value_label_text_color: str = ""
    value_label_bg_color: str = ""
    value_label_bg_alpha: float = 1.0
