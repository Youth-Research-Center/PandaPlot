"""Tests for DataTab with Density charts (#398). Density reuses Hist's
single-values-column shape, so no Density-specific Data tab wiring exists;
these pin that the generic, spec-driven paths handle it."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.series_style import DensitySeriesStyle, HistSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab_with_density_chart() -> tuple[DataTab, Chart]:
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"v": [1.0, 2.0, 2.5, 4.0]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    chart = Chart(name="Density Chart", chart_type="density")
    chart.add_data_series(dataset.id, y_column_id=dataset.column_id("v"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    return tab, chart


def test_series_type_combo_offers_density_and_hist_defaulting_to_density():
    tab, _chart = _tab_with_density_chart()

    offered = {tab.series_type_combo.itemData(i) for i in range(tab.series_type_combo.count())}
    assert offered == {SeriesType.DENSITY, SeriesType.HIST}
    assert tab.series_type_combo.currentData() == SeriesType.DENSITY


def test_retyping_a_density_series_to_hist_and_back():
    tab, chart = _tab_with_density_chart()
    chart.data_series[0].style.color = "#abcdef"

    tab.series_type_combo.setCurrentIndex(tab.series_type_combo.findData(SeriesType.HIST))
    assert chart.data_series[0].series_type == SeriesType.HIST
    assert isinstance(chart.data_series[0].style, HistSeriesStyle)

    tab.series_type_combo.setCurrentIndex(tab.series_type_combo.findData(SeriesType.DENSITY))
    assert isinstance(chart.data_series[0].style, DensitySeriesStyle)
    assert chart.data_series[0].style.color == "#abcdef"
