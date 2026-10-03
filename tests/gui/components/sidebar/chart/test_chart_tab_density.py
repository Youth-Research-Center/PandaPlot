"""Tests for ChartTab's Density chart-type support (#398)."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.chart_tab import ChartTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.project.items.chart import Chart


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


@pytest.mark.parametrize(("chart_type", "shows_bins"), [
    ("hist", True),
    # A Density chart may hold Hist series (a KDE over a histogram), whose
    # bin count is this same chart-level setting.
    ("density", True),
    ("line", False),
    ("scatter", False),
])
def test_bins_control_is_shown_for_chart_types_that_allow_hist_series(chart_type: str, *, shows_bins: bool):
    tab = ChartTab()
    tab.show()

    tab.load(Chart(name="c", chart_type=chart_type))

    assert tab.hist_bins_spin.isVisible() is shows_bins
    assert tab.hist_bins_label.isVisible() is shows_bins


def test_loading_a_density_chart_selects_the_density_combo_entry():
    tab = ChartTab()

    tab.load(Chart(name="d", chart_type="density"))

    assert tab.chart_type_control.currentValue() == ChartType.DENSITY


def _type_item_enabled(tab: ChartTab, chart_type: ChartType) -> bool:
    index = tab.chart_type_control.findData(chart_type)
    return tab.chart_type_control.model().item(index).isEnabled()


def test_fits_on_a_hist_chart_disable_density_but_never_the_charts_own_type():
    from unittest.mock import MagicMock

    from pandaplot.models.chart.series_type import SeriesType

    chart = Chart(name="h", chart_type="hist")
    chart.add_data_series("ds", y_column_id="c1", series_type=SeriesType.HIST)
    tab = ChartTab()
    tab.load(chart)
    assert _type_item_enabled(tab, ChartType.DENSITY) is True

    chart.fit_data.append(MagicMock())
    tab._update_chart_type_compatibility()

    assert _type_item_enabled(tab, ChartType.DENSITY) is False
    assert _type_item_enabled(tab, ChartType.HIST) is True


def test_a_density_chart_that_holds_fits_keeps_its_own_type_enabled():
    from unittest.mock import MagicMock

    chart = Chart(name="d", chart_type="density")
    chart.fit_data.append(MagicMock())
    tab = ChartTab()

    tab.load(chart)

    assert _type_item_enabled(tab, ChartType.DENSITY) is True
