"""Shared "series/fit" combo-box population for chart-series-scoped panels.

Used by ChartAnalysisPanel and (#268) ChartTransformPanel: both offer the
same set of eligible sources -- line/scatter data series and fitted curves,
excluding series types with no meaningful ordered (x, y) curve (bar/hist/
vector/colormap/heatmap/3-D) -- and want the same combo item shape.
"""

from typing import Optional

from PySide6.QtWidgets import QComboBox

from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import Chart


def populate_series_fit_sources(combo: QComboBox, chart: Optional[Chart]) -> tuple[bool, bool]:
    """(Re)fill `combo` with the chart's eligible series/fit entries.

    Each item's data is a ``(kind, index)`` tuple, ``kind`` one of
    ``"series"``/``"fit"``. Returns ``(has_sources, any_series_excluded)``
    so the caller can set its own hint text/enabled state.
    """
    combo.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
    combo.clear()
    any_series_excluded = False
    if chart is not None:
        for i, series in enumerate(chart.data_series):
            if not SERIES_TYPE_SPECS[series.series_type].supports_curve_analysis:
                any_series_excluded = True
                continue
            label = series.label or f"Series {i + 1}"
            combo.addItem(f"📈 {label}", ("series", i))
        for i, fit in enumerate(chart.fit_data):
            label = fit.label or f"Fit {i + 1}"
            combo.addItem(f"〰 {label}  (fit)", ("fit", i))
    combo.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
    return combo.count() > 0, any_series_excluded


def series_source_hint(*, has_sources: bool, any_series_excluded: bool) -> str:
    """Hint label text for the outcome of populate_series_fit_sources()."""
    if not has_sources:
        if any_series_excluded:
            # Operation-neutral wording: shared by ChartAnalysisPanel and
            # ChartTransformPanel, so it can't say "analysis" specifically.
            return (
                "This chart's series (bar/hist/vector/colormap/heatmap/3-D) "
                "aren't supported here -- add a line, scatter, or fit."
            )
        return "This chart has no data series or fits yet."
    if any_series_excluded:
        return "Line/scatter series and fitted curves of this chart -- other series types aren't shown."
    return "Data series and fitted curves of this chart."
