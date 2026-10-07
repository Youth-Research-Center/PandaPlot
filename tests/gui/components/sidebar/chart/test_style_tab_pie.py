"""StyleTab's Pie card (#397): start angle, show percentages, donut hole."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import PieSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _tab():
    tab = StyleTab(app_context=None)
    tab.show()
    return tab


def _pie_series(**style_fields) -> DataSeries:
    return DataSeries(dataset_id="ds1", series_type=SeriesType.PIE, style=PieSeriesStyle(**style_fields))


def test_pie_card_is_the_only_series_card_shown_for_a_pie_series():
    tab = _tab()
    tab.set_chart_type(ChartType.PIE)

    tab.set_selected("series", _pie_series())

    assert tab.pie_card.isVisible() is True
    for card in (tab.line_card, tab.marker_card, tab.fill_card, tab.error_bars_card,
                 tab.value_labels_card, tab.vector_card, tab.vector3d_card, tab.heatmap_gridding_card):
        assert card.isVisible() is False


def test_pie_card_is_hidden_for_a_non_pie_series():
    tab = _tab()
    tab.set_chart_type(ChartType.LINE)

    tab.set_selected("series", DataSeries(dataset_id="ds1", series_type=SeriesType.LINE))

    assert tab.pie_card.isVisible() is False


def test_load_series_style_populates_the_pie_card():
    tab = _tab()
    tab.set_chart_type(ChartType.PIE)

    tab.load_series_style(_pie_series(start_angle=180.0, show_percentages=False, donut_width=0.5))

    assert tab.pie_start_angle_slider.value() == 180.0
    assert tab.pie_show_percentages_toggle.isChecked() is False
    assert tab.pie_donut_width_slider.value() == 0.5


def test_apply_series_style_to_writes_the_pie_fields():
    tab = _tab()
    series = _pie_series()
    tab.set_chart_type(ChartType.PIE)
    tab.set_selected("series", series)

    tab.pie_start_angle_slider.setValue(45.0)
    tab.pie_show_percentages_toggle.setChecked(checked=False)
    tab.pie_donut_width_slider.setValue(0.3)
    tab.apply_series_style_to(series)

    assert series.style.start_angle == 45.0
    assert series.style.show_percentages is False
    assert series.style.donut_width == pytest.approx(0.3)


def test_editing_a_pie_control_writes_through_live_and_leaves_opacity_alone():
    """The hidden Line card's opacity slider holds whatever the previous
    target left in it; a pie edit must not write that onto series.alpha."""
    tab = _tab()
    series = _pie_series()
    series.alpha = 1.0
    tab.set_chart_type(ChartType.PIE)
    tab.set_selected("series", series)
    tab.line_opacity_slider.setValue(0.2)
    emitted = []
    tab.configChanged.connect(lambda: emitted.append(True))

    # Through the spinbox, as a user edit would: SliderWithSpinbox.setValue
    # is the programmatic (non-emitting) path.
    tab.pie_donut_width_slider._spinbox.setValue(0.4)

    assert series.style.donut_width == pytest.approx(0.4)
    assert series.alpha == 1.0
    assert emitted
