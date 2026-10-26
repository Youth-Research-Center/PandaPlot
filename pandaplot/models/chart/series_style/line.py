"""Style fields for a "line" series -- the only type that reads
line_style/line_width in render_line_series()
(pandaplot/gui/components/tabs/chart/series_renderers/line.py); the area-fill
fields come from FillStyleFields."""
from dataclasses import dataclass, field

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase
from pandaplot.models.chart.series_style.fill import FillStyleFields
from pandaplot.models.chart.value_label_subset import ValueLabelSubset


@dataclass
class LineSeriesStyle(FillStyleFields, SeriesStyleBase):
    color: str = "#1f77b4"
    line_style: str = "solid"
    line_width: float = 2.0
    marker: MarkerStyle = field(default_factory=MarkerStyle)
    error_bars: ErrorBarConfig = field(default_factory=ErrorBarConfig)
    # Optional second value column for the same X, drawn on the Y axis
    # opposite this series' own y_axis (#402) -- see
    # SeriesTypeSpec.supports_twin_y_column. Blank means no twin trace.
    twin_y_column_id: str = ""
    twin_y_column: str = ""
    # Color of the twin trace, so it can be told apart from the series' own
    # (#402). Overrides the line/marker color; a marker color left blank
    # ("inherit") follows it, an explicit one is replaced by it.
    twin_y_color: str = "#ff7f0e"
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
    # Which points get a label (see series_renderers/value_labels.py).
    value_label_subset_mode: ValueLabelSubset = ValueLabelSubset.ALL

    def __post_init__(self) -> None:
        """Normalize an unknown `value_label_subset_mode` (e.g. from a hand-edited project) to ALL."""
        self.value_label_subset_mode = ValueLabelSubset.coerce(self.value_label_subset_mode)
