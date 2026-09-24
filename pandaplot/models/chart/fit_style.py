"""Style fields for a curve fit's line and confidence band.

Deliberately does NOT subclass LineSeriesStyle: a fit has no marker
concept at all (see StyleTab.load_fit_style's own docstring), and its
"fill" is a confidence band drawn AROUND the curve (from
style.confidence_lower/confidence_upper), not an area-fill-to-baseline
UNDER it like DataSeries's fill_* fields -- different semantics, needing
different fields (band_fill_alpha/band_color vs fill_color/fill_alpha/
fill_orientation/fill_base/fill_to_index). Inheriting LineSeriesStyle
would resurrect exactly the "carries fields it never uses" problem the
per-series-type style split (SeriesStyleBase subclasses) exists to avoid.

Carries fit-only metadata (fit_type/fit_params/fit_stats/confidence
arrays+ids/is_manual) moved here from the old standalone FitData
dataclass (#304) -- DataSeries.style is where every other type's
type-specific data already lives. No `alpha` field: a fit's own opacity
now comes from the generic DataSeries.alpha every other series type
already uses, not a fit-only duplicate.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class FitStyle(SeriesStyleBase):
    color: str = "#ff7f0e"
    line_style: str = "dashed"
    line_width: float = 2.0
    band_fill_enabled: bool = True
    band_fill_alpha: float = 0.2
    band_color: str = ""  # "" => inherit the fit line's own color
    fit_type: str = ""
    fit_params: Optional[dict[str, Any]] = None
    fit_stats: Optional[dict[str, Any]] = None
    confidence_lower: Optional[np.ndarray] = field(default=None, compare=False)
    confidence_upper: Optional[np.ndarray] = field(default=None, compare=False)
    confidence_lower_column_id: str = ""
    confidence_upper_column_id: str = ""
    is_manual: bool = False

    def __post_init__(self) -> None:
        if self.fit_params is None:
            self.fit_params = {}
        if self.fit_stats is None:
            self.fit_stats = {}
