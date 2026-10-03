"""Tests for StyleTab's Density (KDE) series support (#398).

A Density series reuses the shared Line card for color/line style/width/
opacity (DensitySeriesStyle declares those fields under the same names),
but NOT the generic Fill card -- that card writes the full FillStyleFields
set, which DensitySeriesStyle deliberately doesn't have -- so its fill
switch/opacity and bandwidth live on a dedicated Density card instead.
"""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_configuration import LineStyleType
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import DensitySeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab() -> StyleTab:
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def _density_series(**style_fields) -> DataSeries:
    return DataSeries(dataset_id="ds1", series_type=SeriesType.DENSITY, style=DensitySeriesStyle(**style_fields))


def test_density_series_shows_line_and_density_cards_only():
    tab = _tab()
    tab.set_chart_type(ChartType.DENSITY)
    tab.set_selected("series", _density_series())

    assert tab.density_card.isVisible() is True
    assert tab.line_card.isVisible() is True
    assert tab.fill_card.isVisible() is False
    assert tab.marker_card.isVisible() is False
    assert tab.error_bars_card.isVisible() is False
    assert tab.value_labels_card.isVisible() is False


def test_density_card_is_hidden_for_a_line_series_which_keeps_the_fill_card():
    tab = _tab()
    tab.set_chart_type(ChartType.LINE)
    tab.set_selected("series", DataSeries(dataset_id="ds1", series_type=SeriesType.LINE))

    assert tab.density_card.isVisible() is False
    assert tab.fill_card.isVisible() is True


def test_density_card_is_hidden_for_a_hist_series_on_a_density_chart():
    tab = _tab()
    tab.set_chart_type(ChartType.DENSITY)
    tab.set_selected("series", DataSeries(dataset_id="ds1", series_type=SeriesType.HIST))

    assert tab.density_card.isVisible() is False
    assert tab.line_card.isVisible() is True


def test_apply_series_style_to_writes_line_and_density_fields():
    tab = _tab()
    series = _density_series()
    tab.set_chart_type(ChartType.DENSITY)
    tab.set_selected("series", series)

    tab.line_color_row.setCurrentColor("#123456")
    tab.line_style_control.setCurrentValue(LineStyleType.DASHED)
    tab.line_width_slider.setValue(3.5)
    tab.line_opacity_slider.setValue(0.7)
    tab.density_bandwidth_spin.setValue(0.4)
    tab.density_fill_toggle.setChecked(checked=True)
    tab.density_fill_opacity_slider.setValue(0.6)

    tab.apply_series_style_to(series)

    assert series.style.color == "#123456"
    assert series.style.line_style == "dashed"
    assert series.style.line_width == 3.5
    assert series.alpha == 0.7
    assert series.style.bandwidth == 0.4
    assert series.style.fill_enabled is True
    assert series.style.fill_alpha == 0.6


def test_load_series_style_populates_density_card_from_series():
    tab = _tab()
    series = _density_series(color="#abcdef", line_style="dotted", line_width=4.0,
                             fill_enabled=True, fill_alpha=0.45, bandwidth=1.25)
    tab.set_chart_type(ChartType.DENSITY)

    tab.load_series_style(series)

    assert tab.line_color_row.currentColor() == "#abcdef"
    assert tab.line_style_control.currentValue() == LineStyleType.DOTTED
    assert tab.line_width_slider.value() == 4.0
    assert tab.density_bandwidth_spin.value() == 1.25
    assert tab.density_fill_toggle.isChecked() is True
    assert tab.density_fill_opacity_slider.value() == 0.45


def test_zero_bandwidth_displays_as_auto():
    tab = _tab()
    tab.set_chart_type(ChartType.DENSITY)
    tab.set_selected("series", _density_series(bandwidth=0.0))

    assert tab.density_bandwidth_spin.text() == "Auto"


def test_fill_opacity_is_shown_only_while_the_fill_is_on():
    tab = _tab()
    series = _density_series(fill_enabled=False)
    tab.set_chart_type(ChartType.DENSITY)
    tab.set_selected("series", series)
    assert tab.density_fill_opacity_slider.isVisible() is False

    tab.density_fill_toggle.setChecked(checked=True)

    assert tab.density_fill_opacity_slider.isVisible() is True
    # Toggling writes straight through to the selected series.
    assert series.style.fill_enabled is True
