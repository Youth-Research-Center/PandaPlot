"""Style fields for a "scatter" series -- marker fields only, no line/
fill; render_scatter_series()
(pandaplot/gui/components/tabs/chart/series_renderers/scatter.py) reads
only marker fields."""
from dataclasses import dataclass, field

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class ScatterSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    marker: MarkerStyle = field(default_factory=MarkerStyle)
    error_bars: ErrorBarConfig = field(default_factory=ErrorBarConfig)
    # Annotate each rendered point with its numeric Y value (#125) -- see
    # SeriesTypeSpec.supports_value_labels and series_renderers/value_labels.py.
    show_value_labels: bool = False
    value_label_mode: str = "y"
    value_label_show_arrow: bool = False
    value_label_offset_x: float = 0.0
    value_label_offset_y: float = 6.0
    value_label_text_color: str = ""
    value_label_bg_color: str = ""
    value_label_bg_alpha: float = 1.0
