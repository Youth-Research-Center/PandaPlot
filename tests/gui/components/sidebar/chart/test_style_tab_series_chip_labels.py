"""StyleTab's series chips show plain series and fit labels (#586)."""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.project.items.chart import Chart


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_fit_series_chip_label_is_the_plain_fit_label():
    chart = Chart(name="C", chart_type="line")
    chart.add_data_series("ds1", "x", "y", label="Data")
    chart.add_fit_series("ds1", x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]), label="A Fit", style=FitStyle(fit_type="linear"))
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.LINE)

    tab.set_series_list(chart.data_series, selected_index=0)

    labels = [tab.style_series_chips.itemText(row) for row in range(tab.style_series_chips.count())]
    assert labels == ["Chart", "Axes", "Data", "A Fit"]
