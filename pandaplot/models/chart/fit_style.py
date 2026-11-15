"""Style fields for a curve fit's line, area fill and confidence band.

Deliberately does NOT subclass LineSeriesStyle: a fit has no marker
concept at all (see StyleTab.load_fit_style's own docstring), and
inheriting LineSeriesStyle would resurrect exactly the "carries fields it
never uses" problem the per-series-type style split (SeriesStyleBase
subclasses) exists to avoid.

It does take the shared area-fill fields (FillStyleFields, #431), so a fit
can be filled to a baseline or to another series like a Line. That fill is
independent of the confidence band, which is drawn AROUND the curve (from
style.confidence_lower/confidence_upper) with its own band_color/
band_fill_alpha. The area fill is drawn below the band, and the fit line
above both.

Carries fit-only metadata (fit_type/fit_params/fit_stats/confidence
arrays+ids/is_manual) moved here from the old standalone FitData
dataclass (#304) -- DataSeries.style is where every other type's
type-specific data already lives. No `alpha` field: a fit's own opacity
now comes from the generic DataSeries.alpha every other series type
already uses, not a fit-only duplicate.
"""
import copy
from dataclasses import dataclass, field, fields
from typing import Any

import numpy as np

from pandaplot.models.chart.series_style.base import SeriesStyleBase
from pandaplot.models.chart.series_style.fill import FillStyleFields


@dataclass
class _FitFillStyleFields(FillStyleFields):
    fill_enabled: bool = field(default=False, kw_only=True)
    fill_color: str = field(default="", kw_only=True)
    fill_alpha: float = field(default=0.3, kw_only=True)
    fill_orientation: str = field(default="vertical", kw_only=True)
    fill_base: float = field(default=0.0, kw_only=True)
    fill_to_index: int = field(default=-1, kw_only=True)
    fill_range_enabled: bool = field(default=False, kw_only=True)
    fill_sections: list[tuple[int, int]] = field(default_factory=list, kw_only=True)


@dataclass
class FitStyle(_FitFillStyleFields, SeriesStyleBase):
    color: str = "#ff7f0e"
    line_style: str = "dashed"
    line_width: float = 2.0
    band_fill_enabled: bool = True
    band_fill_alpha: float = 0.2
    band_color: str = ""  # "" => inherit the fit line's own color
    # "vertical": confidence_lower/upper are Y bounds at each curve X.
    # "horizontal": they are X bounds at each curve Y (after swapping X/Y).
    band_orientation: str = "vertical"
    fit_type: str = ""
    fit_params: dict[str, Any] | None = None
    fit_stats: dict[str, Any] | None = None
    confidence_lower: np.ndarray | None = field(default=None, compare=False)
    confidence_upper: np.ndarray | None = field(default=None, compare=False)
    confidence_lower_column_id: str = ""
    confidence_upper_column_id: str = ""
    is_manual: bool = False

    def __deepcopy__(self, memo: dict) -> "FitStyle":
        """Deep copy that shares the confidence arrays instead of copying them.

        They are snapshots that are only ever replaced wholesale, never
        mutated in place, and chart snapshots/undo deep-copy every series
        often -- copying large arrays each time is pure overhead."""
        clone = copy.copy(self)
        for f in fields(self):
            value = getattr(self, f.name)
            if not isinstance(value, np.ndarray):
                setattr(clone, f.name, copy.deepcopy(value, memo))
        return clone

    def __post_init__(self) -> None:
        if self.fit_params is None:
            self.fit_params = {}
        if self.fit_stats is None:
            self.fit_stats = {}
