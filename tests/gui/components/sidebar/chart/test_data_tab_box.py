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
from pandaplot.models.project.items.chart import Chart
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

    assert offered == {SeriesType.BOX, "__convert_to_fit__"}
    assert tab.series_type_combo.currentData() == SeriesType.BOX


def test_adding_a_series_to_a_box_chart_creates_another_box_series():
    tab, chart = _loaded_box_tab()

    tab._add_series()

    assert len(chart.data_series) == 2
    new_series = chart.data_series[1]
    assert new_series.series_type == SeriesType.BOX
    assert isinstance(new_series.style, BoxSeriesStyle)
    assert new_series.y_column_id
