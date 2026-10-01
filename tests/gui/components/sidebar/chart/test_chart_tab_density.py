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
