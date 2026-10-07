"""DataTab coverage for Box charts (#399). Box reuses Histogram's single
"values" column (y_column_id), so it needs no Box-specific Data tab wiring --
these pin that the generic, spec-driven paths already handle it."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.series_style import BoxSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, YAxis
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _loaded_box_tab():
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    chart = Chart(name="Box Chart", chart_type="box")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("a"), label="A")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    return tab, chart


def test_series_type_combo_offers_only_box_for_a_box_chart():
    tab, _chart = _loaded_box_tab()

    offered = {tab.series_type_combo.itemData(i) for i in range(tab.series_type_combo.count())}

    # No "Fit": a box series has no X column, so a fit conversion could only fail.
    assert offered == {SeriesType.BOX}
    assert tab.series_type_combo.currentData() == SeriesType.BOX


def test_adding_a_series_to_a_box_chart_creates_another_box_series():
    tab, chart = _loaded_box_tab()

    tab._add_series()

    assert len(chart.data_series) == 2
    new_series = chart.data_series[1]
    assert new_series.series_type == SeriesType.BOX
    assert isinstance(new_series.style, BoxSeriesStyle)
    assert new_series.y_column_id


def test_y_axis_control_is_hidden_and_forced_primary_for_box_series():
    """Sibling boxes share one set of numbered slots/ticks on the primary
    axes, so a Box series can't be put on Y2."""
    tab, chart = _loaded_box_tab()
    tab.show()

    assert not tab.series_y_axis_control.isVisible()
    assert not tab.series_y_axis_label.isVisible()

    tab.series_y_axis_control.setCurrentValue(YAxis.SECONDARY)
    tab._add_series()

    assert all(series.y_axis == YAxis.PRIMARY for series in chart.data_series)


def test_y_axis_badge_is_not_shown_as_a_window_before_it_is_parented():
    """The badge is built parentless and added to a layout afterwards;
    calling setVisible(True) on it in between flashed it as a top-level
    window every time the series cards were rebuilt."""
    tab, _chart = _loaded_box_tab()

    badge = tab._build_y_axis_badge(YAxis.PRIMARY, {})

    assert not badge.isVisible()
