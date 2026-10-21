"""Style fields for a "scatter" series -- marker fields plus the shared
area-fill fields (FillStyleFields); render_scatter_series()
(pandaplot/gui/components/tabs/chart/series_renderers/scatter.py) reads
them, no line."""
from dataclasses import dataclass, field

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase
from pandaplot.models.chart.series_style.fill import FillStyleFields
from pandaplot.models.chart.value_label_subset import ValueLabelSubset


@dataclass
class ScatterSeriesStyle(FillStyleFields, SeriesStyleBase):
    color: str = "#1f77b4"
    marker: MarkerStyle = field(default_factory=MarkerStyle)
    error_bars: ErrorBarConfig = field(default_factory=ErrorBarConfig)
    # Optional second value column for the same X, drawn on the Y axis
    # opposite this series' own y_axis (#402) -- see
    # SeriesTypeSpec.supports_twin_y_column. Blank means no twin trace.
    twin_y_column_id: str = ""
    twin_y_column: str = ""
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
    # Which points get a label (see series_renderers/value_labels.py).
    value_label_subset_mode: ValueLabelSubset = ValueLabelSubset.ALL

    def __post_init__(self) -> None:
        """Normalize an unknown `value_label_subset_mode` (e.g. from a hand-edited project) to ALL."""
        self.value_label_subset_mode = ValueLabelSubset.coerce(self.value_label_subset_mode)
