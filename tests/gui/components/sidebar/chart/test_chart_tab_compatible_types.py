"""Tests for ChartTab's chart-type selector."""
import sys

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.chart_tab import ChartTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _is_option_enabled(tab: ChartTab, chart_type: ChartType) -> bool:
    combo = tab.chart_type_control
    index = combo.findData(chart_type)
    item = combo.model().item(index)
    return item.isEnabled()


def test_vector_chart_disables_bar_as_a_switch_target():
    """Reported live: "I don't think we should support going from vector
    to barchart" -- the option must be disabled, not just silently
    force-retype on selection."""
    tab = ChartTab()
    chart = Chart(name="Vector Chart", chart_type="vector")
    tab.load(chart)

    assert _is_option_enabled(tab, ChartType.BAR) is False
    assert _is_option_enabled(tab, ChartType.LINE) is True
    assert _is_option_enabled(tab, ChartType.SCATTER) is True
    assert _is_option_enabled(tab, ChartType.VECTOR) is True


def test_scatter_chart_still_allows_switching_to_bar():
    """Existing, preserved case."""
    tab = ChartTab()
    chart = Chart(name="Scatter Chart", chart_type="scatter")
    tab.load(chart)

    assert _is_option_enabled(tab, ChartType.BAR) is True


def test_disabled_option_has_an_explanatory_tooltip():
    tab = ChartTab()
    chart = Chart(name="Vector Chart", chart_type="vector")
    tab.load(chart)

    combo = tab.chart_type_control
    index = combo.findData(ChartType.BAR)
    tooltip = combo.model().item(index).toolTip()
    assert tooltip != ""


def test_compatibility_is_recomputed_after_switching_type():
    """After Vector -> Line, Bar must still reflect Line's own
    compatibility (disabled, since LINE isn't in BAR.allowed_series_types),
    proving the disabled-state check reruns on every type change rather
    than being computed once at load()."""
    tab = ChartTab()
    chart = Chart(name="Vector Chart", chart_type="vector")
    tab.load(chart)

    line_index = tab.chart_type_control.findData(ChartType.LINE)
    tab.chart_type_control.setCurrentIndex(line_index)

    assert _is_option_enabled(tab, ChartType.BAR) is False
    assert _is_option_enabled(tab, ChartType.HIST) is False


def test_clear_resets_chart_type_compatibility_state():
    """clear() resets the type combo to SCATTER but must also recompute
    compatibility -- otherwise a tab cleared after showing a Vector chart
    (which disables Bar) keeps stale disabled state even though SCATTER's
    compatible_chart_types includes BAR."""
    tab = ChartTab()
    chart = Chart(name="Vector Chart", chart_type="vector")
    tab.load(chart)
    assert _is_option_enabled(tab, ChartType.BAR) is False

    tab.clear()

    assert _is_option_enabled(tab, ChartType.BAR) is True


def test_mixed_scatter_and_vector_series_disables_bar():
    """The exact reviewer scenario from PR #180 review, reproduced through
    the real UI method: a Scatter chart holding both a SCATTER series and
    a VECTOR series must show Bar as DISABLED, even though a plain
    Scatter chart alone (no VECTOR series) allows Bar -- see
    `test_scatter_chart_still_allows_switching_to_bar` above. Before the
    fix, `_update_chart_type_compatibility` consulted only the chart's
    nominal type (`compatible_chart_types(ChartType.SCATTER)`, which
    includes Bar) and ignored the actual VECTOR series present, so this
    test would have failed by asserting Bar was enabled when it should
    not be."""
    tab = ChartTab()
    chart = Chart(name="Mixed Chart", chart_type="scatter")
    chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                           series_type=SeriesType.SCATTER)
    chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                           series_type=SeriesType.VECTOR)
    tab.load(chart)

    assert _is_option_enabled(tab, ChartType.BAR) is False


def test_a_chart_holding_a_fit_still_allows_switching_to_colormap_and_heatmap():
    """Re-review finding #2: a FIT series lives inline in data_series since
    #304, but it must stay immune to chart-type-switch gating in the UI --
    same as it already is in `Chart.set_chart_type` (which never
    force-retypes a FIT series away). Before the fix, a chart holding ANY
    fit had SeriesType.FIT included in the set passed to
    `compatible_chart_types_for_series`, and since FIT isn't in Colormap's
    or Heatmap's `allowed_series_types`, both options were wrongly
    disabled -- a regression versus pre-#304, where fits lived in a
    separate `fit_data` list that never entered this computation."""
    tab = ChartTab()
    chart = Chart(name="Chart With Fit", chart_type="line")
    chart.add_data_series(dataset_id="ds1", x_column_id="x", y_column_id="y",
                           series_type=SeriesType.LINE)
    chart.add_fit_series(
        source_dataset_id="ds1",
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 2.0, 3.0]),
        label="Fit",
        style=FitStyle(fit_type="linear"),
    )
    tab.load(chart)

    assert _is_option_enabled(tab, ChartType.COLORMAP) is True
    assert _is_option_enabled(tab, ChartType.HEATMAP) is True
