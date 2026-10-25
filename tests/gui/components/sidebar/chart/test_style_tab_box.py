"""Tests for StyleTab's Box chart-type support (#399): a Box card for the
box-specific fields, with color/opacity left to the shared Line card (Box's
spec sets supports_color, like Bar/Hist)."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import BoxSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab():
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def _box_series(**style_fields) -> DataSeries:
    return DataSeries(dataset_id="ds1", series_type=SeriesType.BOX, style=BoxSeriesStyle(**style_fields))


def test_box_card_and_color_card_are_shown_for_a_box_series_target():
    tab = _tab()
    tab.set_chart_type(ChartType.BOX)
    tab.set_selected("series", _box_series())

    assert tab.box_card.isVisible() is True
    assert tab.line_card.isVisible() is True
    assert tab.marker_card.isVisible() is False
    assert tab.fill_card.isVisible() is False
    assert tab.error_bars_card.isVisible() is False
    assert tab.value_labels_card.isVisible() is False
    assert tab.vector_card.isVisible() is False


def test_box_card_is_hidden_for_other_series_types():
    tab = _tab()
    tab.set_chart_type(ChartType.HIST)
    tab.set_selected("series", DataSeries(dataset_id="ds1", series_type=SeriesType.HIST))

    assert tab.box_card.isVisible() is False


def test_apply_series_style_to_writes_box_fields_and_color():
    tab = _tab()
    series = _box_series()
    tab.set_chart_type(ChartType.BOX)
    tab.set_selected("series", series)

    tab.box_show_outliers_toggle.setChecked(checked=False)
    tab.box_notch_toggle.setChecked(checked=True)
    tab.box_width_slider.setValue(0.3)
    tab.line_color_row.setCurrentColor("#123456")
    tab.line_opacity_slider.setValue(0.4)

    tab.apply_series_style_to(series)

    assert series.style == BoxSeriesStyle(color="#123456", show_outliers=False, notch=True, box_width=0.3)
    assert series.alpha == 0.4


def test_load_series_style_populates_box_card_from_series():
    tab = _tab()
    series = _box_series(color="#abcdef", show_outliers=False, notch=True, box_width=0.8)
    tab.set_chart_type(ChartType.BOX)

    tab.load_series_style(series)

    assert tab.box_show_outliers_toggle.isChecked() is False
    assert tab.box_notch_toggle.isChecked() is True
    assert tab.box_width_slider.value() == 0.8
    assert tab.line_color_row.currentColor() == "#abcdef"


def test_editing_a_box_control_writes_through_to_the_selected_series():
    """The controls are wired to _on_field_changed, not just readable."""
    tab = _tab()
    series = _box_series()
    tab.set_chart_type(ChartType.BOX)
    tab.set_selected("series", series)
    tab.load_series_style(series)

    tab.box_notch_toggle.setChecked(checked=True)

    assert series.style.notch is True
