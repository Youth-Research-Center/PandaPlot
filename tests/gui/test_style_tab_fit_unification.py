"""#304: StyleTab must treat a FIT-type DataSeries as kind="series" and
dispatch fit-specific behavior off series_type, not a separate "fit" kind."""
import sys

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def style_tab_fixture():
    _qapp()
    app_context = build_app_context()
    style_tab = StyleTab(app_context=app_context)
    style_tab.show()
    return style_tab


@pytest.fixture
def chart_with_fit():
    chart = Chart(name="c", chart_type="line")
    chart.add_data_series(dataset_id="ds1", y_column_id="y")
    chart.add_fit_series(
        source_dataset_id="ds1", x_data=np.array([1.0]), y_data=np.array([2.0]),
        label="My Fit", style=FitStyle(confidence_lower=np.array([0.5]), confidence_upper=np.array([1.5])),
    )
    return chart


def test_set_series_list_takes_one_combined_list(style_tab_fixture, chart_with_fit):
    style_tab = style_tab_fixture
    style_tab.set_series_list(chart_with_fit.data_series, selected_index=1)
    kind, obj = style_tab._current_target
    assert kind == "series"
    assert obj.series_type == SeriesType.FIT


def test_band_card_visible_for_fit_series_with_confidence_data(style_tab_fixture, chart_with_fit):
    style_tab = style_tab_fixture
    fit_series = chart_with_fit.fit_data[0]
    style_tab.set_selected("series", fit_series)
    assert style_tab.band_card.isVisible()
