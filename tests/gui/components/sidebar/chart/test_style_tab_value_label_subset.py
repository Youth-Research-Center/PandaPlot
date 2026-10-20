"""Tests for the Value Labels card's "Label points" dropdown (#337)."""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import DataSeries


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _tab():
    _qapp()
    tab = StyleTab(app_context=None)
    tab.show()  # Qt only reports isVisible() truthfully once shown
    tab.set_chart_type(ChartType.LINE)
    return tab


def _line_series(**style_fields):
    return DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.LINE,
        style=LineSeriesStyle(**style_fields),
    )


def _scatter_series(**style_fields):
    return DataSeries(
        dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.SCATTER,
        style=ScatterSeriesStyle(**style_fields),
    )


def test_subset_dropdown_shows_all_points_by_default():
    tab = _tab()
    series = _line_series(show_value_labels=True)

    tab.load_series_style(series)

    assert tab.value_labels_subset_control.currentValue() == "all"


def test_load_then_apply_round_trips_subset_mode_for_line_series():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_subset_mode="max")

    tab.load_series_style(series)

    assert tab.value_labels_subset_control.currentValue() == "max"

    tab.apply_series_style_to(series)

    assert series.style.value_label_subset_mode == "max"


def test_load_then_apply_round_trips_subset_mode_for_scatter_series():
    tab = _tab()
    series = _scatter_series(show_value_labels=True, value_label_subset_mode="extremes")

    tab.load_series_style(series)

    assert tab.value_labels_subset_control.currentValue() == "extremes"

    tab.apply_series_style_to(series)

    assert series.style.value_label_subset_mode == "extremes"


def test_choosing_a_subset_in_the_dropdown_updates_the_series_style():
    tab = _tab()
    series = _line_series(show_value_labels=True)
    tab.set_selected("series", series)

    changes = []
    tab.configChanged.connect(lambda: changes.append(True))
    control = tab.value_labels_subset_control
    control.setCurrentIndex(control.findData("min"))

    assert series.style.value_label_subset_mode == "min"
    assert changes


def test_subset_dropdown_visible_for_line_only_while_value_labels_are_on():
    tab = _tab()
    series = _line_series(show_value_labels=False)
    tab.set_selected("series", series)
    assert tab.value_labels_subset_control.isVisible() is False

    tab.value_labels_enabled_toggle.setChecked(checked=True)

    assert tab.value_labels_subset_control.isVisible() is True
    assert tab.value_labels_subset_label.isVisible() is True


def test_subset_dropdown_hidden_for_bar_series():
    tab = _tab()
    bar_series = DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.BAR)
    bar_series.style.show_value_labels = True

    tab.set_selected("series", bar_series)

    assert tab.value_labels_enabled_toggle.isChecked() is True
    assert tab.value_labels_subset_control.isVisible() is False


def test_unknown_subset_mode_shows_all_points_not_the_previous_series_value():
    tab = _tab()
    first = _line_series(show_value_labels=True, value_label_subset_mode="min")
    second = _line_series(show_value_labels=True, value_label_subset_mode="not-a-mode")

    tab.load_series_style(first)
    tab.load_series_style(second)

    assert tab.value_labels_subset_control.currentValue() == "all"


def test_load_then_apply_round_trips_local_extremes_subset_mode():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_subset_mode="local_extremes")

    tab.load_series_style(series)

    assert tab.value_labels_subset_control.currentValue() == "local_extremes"

    tab.apply_series_style_to(series)

    assert series.style.value_label_subset_mode == "local_extremes"