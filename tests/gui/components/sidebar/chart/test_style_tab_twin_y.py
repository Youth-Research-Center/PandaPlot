"""StyleTab's Twin Y Column card (#402): recolors the twin trace so it can be
told apart from the series' own."""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import BarSeriesStyle, LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


def _tab(chart_type=ChartType.LINE):
    QApplication.instance() or QApplication(sys.argv)
    tab = StyleTab(app_context=None)
    tab.show()  # Qt only reports isVisible() truthfully once shown
    tab.set_chart_type(chart_type)
    return tab


def _series(series_type, style):
    return DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type=series_type, style=style)


def _select(tab, series):
    tab.set_selected("series", series)


def test_card_is_shown_for_a_line_series_with_a_twin_column():
    tab = _tab()

    _select(tab, _series(SeriesType.LINE, LineSeriesStyle(twin_y_column_id="twin")))

    assert tab.twin_y_card.isVisible() is True


def test_card_is_shown_for_a_scatter_series_with_a_twin_column():
    tab = _tab(ChartType.SCATTER)

    _select(tab, _series(SeriesType.SCATTER, ScatterSeriesStyle(twin_y_column="pressure")))

    assert tab.twin_y_card.isVisible() is True


def test_card_is_hidden_without_a_twin_column():
    tab = _tab()

    _select(tab, _series(SeriesType.LINE, LineSeriesStyle()))

    assert tab.twin_y_card.isVisible() is False


def test_card_is_hidden_for_a_series_type_without_twin_support():
    tab = _tab(ChartType.BAR)

    _select(tab, _series(SeriesType.BAR, BarSeriesStyle()))

    assert tab.twin_y_card.isVisible() is False


def test_load_shows_the_twin_color_and_apply_writes_it_back():
    tab = _tab()
    series = _series(SeriesType.LINE, LineSeriesStyle(twin_y_column_id="twin", twin_y_color="#00aa00"))
    _select(tab, series)
    assert tab.twin_y_color_row.currentColor().lower() == "#00aa00"

    tab.twin_y_color_row.setCurrentColor("#aa00aa")
    tab.apply_series_style_to(series)

    assert series.style.twin_y_color.lower() == "#aa00aa"
    assert series.style.color == LineSeriesStyle().color


def test_picking_a_twin_color_emits_a_config_change():
    tab = _tab()
    series = _series(SeriesType.LINE, LineSeriesStyle(twin_y_column_id="twin"))
    _select(tab, series)
    emitted = []
    tab.configChanged.connect(lambda: emitted.append(True))

    tab.twin_y_color_row.colorChanged.emit("#123456")

    assert emitted
