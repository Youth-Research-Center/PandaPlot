"""Tests for the Data and Style tabs' handling of Stacked Bar series (#396).

Stacked Bar has no tab wiring of its own: both tabs are driven by
SeriesTypeSpec/ChartTypeSpec and BarSeriesStyle's fields, all shared with
Bar. These pin that a Stacked Bar series gets exactly Bar's controls.
"""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.chart_tab import ChartTab
from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style import BarSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.project import Project

_SERIES_CARDS = (
    "line_card", "fill_card", "marker_card", "error_bars_card", "value_labels_card",
    "vector_card", "vector3d_card", "heatmap_gridding_card",
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _style_tab_showing(series_type: SeriesType, chart_type: ChartType) -> StyleTab:
    # Qt only reports isVisible() truthfully once a top-level ancestor has
    # been shown -- same pattern as test_style_data_tabs_3d.py.
    tab = StyleTab(app_context=None)
    tab.show()
    tab.set_chart_type(chart_type)
    # An error column configured, so the Error Bars card has something to style.
    style = BarSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id="col-err"), show_value_labels=True)
    tab.set_selected("series", DataSeries(dataset_id="ds1", label="s1", series_type=series_type, style=style))
    return tab


def test_style_tab_shows_a_stacked_bar_series_exactly_the_cards_a_bar_series_gets():
    bar_tab = _style_tab_showing(SeriesType.BAR, ChartType.BAR)
    stacked_tab = _style_tab_showing(SeriesType.STACKED_BAR, ChartType.STACKED_BAR)

    visibility = {card: getattr(stacked_tab, card).isVisible() for card in _SERIES_CARDS}
    assert visibility == {card: getattr(bar_tab, card).isVisible() for card in _SERIES_CARDS}
    assert visibility["line_card"] is True
    assert visibility["error_bars_card"] is True
    assert visibility["value_labels_card"] is True
    assert visibility["marker_card"] is False
    # Bar-style value labels: no mode/arrow/offset (BarSeriesStyle has none).
    assert stacked_tab.value_labels_mode_control.isVisible() is False


def test_style_tab_round_trips_a_stacked_bar_series_style():
    tab = StyleTab(app_context=None)
    tab.set_chart_type(ChartType.STACKED_BAR)
    series = DataSeries(
        dataset_id="ds1", series_type=SeriesType.STACKED_BAR,
        style=BarSeriesStyle(color="#112233", show_value_labels=True, value_label_bg_color="#445566"),
    )

    tab.load_series_style(series)
    tab.line_color_row.setCurrentColor("#abcdef")
    tab.apply_series_style_to(series)

    assert series.style.color == "#abcdef"
    assert series.style.show_value_labels is True
    assert series.style.value_label_bg_color == "#445566"


@pytest.mark.parametrize("source,target", [(ChartType.BAR, ChartType.STACKED_BAR), (ChartType.STACKED_BAR, ChartType.BAR)])
def test_chart_tab_offers_switching_between_bar_and_stacked_bar(source, target):
    tab = ChartTab()
    chart = Chart(name="Bars", chart_type=source)
    chart.add_data_series("ds1", y_column_id="col-y")
    tab.load(chart)

    combo = tab.chart_type_control
    assert combo.model().item(combo.findData(target)).isEnabled() is True


def _data_tab_with_stacked_chart() -> tuple[DataTab, Chart]:
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"x": [0, 1], "y": [2, 3], "err": [0.1, 0.1]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    chart = Chart(name="Stacked", chart_type=ChartType.STACKED_BAR)
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab.show()
    return tab, chart


def test_data_tab_offers_the_stacked_bar_charts_allowed_series_types_with_a_readable_name():
    tab, chart = _data_tab_with_stacked_chart()

    assert chart.data_series[0].series_type == SeriesType.STACKED_BAR
    offered = {tab.series_type_combo.itemData(i): tab.series_type_combo.itemText(i)
               for i in range(tab.series_type_combo.count())}
    assert offered == {SeriesType.STACKED_BAR: "Stacked Bar", SeriesType.SCATTER: "Scatter", "__convert_to_fit__": "Fit"}
    assert tab.series_type_combo.currentData() == SeriesType.STACKED_BAR


def test_data_tab_offers_x_y_and_error_columns_but_no_type_specific_ones():
    tab, _chart = _data_tab_with_stacked_chart()

    assert tab.x_column_combo.isVisible() is True
    assert tab.y_column_combo.isVisible() is True
    assert tab.y_error_column_combo.isEnabled() is True
    assert tab.z_column_combo.isVisible() is False
    assert tab.u_column_combo.isVisible() is False
