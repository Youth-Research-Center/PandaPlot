"""Tests for the Value Labels card's arrow styling controls (#504)."""
import sys

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.line_style_icons import build_line_style_icon
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.chart.chart_configuration import LineStyleType
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.value_label_arrow import ValueLabelArrowLineStyle, ValueLabelArrowStyle
from pandaplot.models.project.items.chart import DataSeries
from tests.gui.theme_testing import design_tokens

STYLED = {
    "value_label_arrow_style": ValueLabelArrowStyle.FILLED_ARROW,
    "value_label_arrow_color": "#2ca02c",
    "value_label_arrow_width": 2.5,
    "value_label_arrow_line_style": ValueLabelArrowLineStyle.DASHED,
}


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


def _arrow_controls(tab):
    return (
        tab.value_labels_arrow_style_label, tab.value_labels_arrow_style_control,
        tab.value_labels_arrow_match_color_label, tab.value_labels_arrow_match_color_toggle,
        tab.value_labels_arrow_width_label, tab.value_labels_arrow_width_slider,
        tab.value_labels_arrow_line_style_label, tab.value_labels_arrow_line_style_control,
    )


def _pick_color(tab, color):
    """What clicking a swatch does: set the color, then announce it."""
    tab.value_labels_arrow_color_row.setCurrentColor(color)
    tab.value_labels_arrow_color_row.colorChanged.emit(color)


def test_controls_show_the_historical_look_by_default():
    tab = _tab()

    tab.load_series_style(_line_series(show_value_labels=True, value_label_show_arrow=True))

    assert tab.value_labels_arrow_style_control.currentValue() == "line"
    assert tab.value_labels_arrow_match_color_toggle.isChecked() is False
    assert tab.value_labels_arrow_color_row.currentColor() == "#000000"
    assert tab.value_labels_arrow_width_slider.value() == 1.0
    assert tab.value_labels_arrow_line_style_control.currentValue() == "solid"


@pytest.mark.parametrize(
    ("make_series", "arrow_color"),
    [(_line_series, "#2ca02c"), (_scatter_series, "#2ca02c"), (_line_series, ""), (_scatter_series, "")],
)
def test_load_then_apply_round_trips_the_arrow_styling(make_series, arrow_color):
    tab = _tab()
    fields = {**STYLED, "value_label_arrow_color": arrow_color}
    series = make_series(show_value_labels=True, value_label_show_arrow=True, **fields)

    tab.load_series_style(series)
    tab.apply_series_style_to(series)

    style = series.style
    assert style.value_label_arrow_style is ValueLabelArrowStyle.FILLED_ARROW
    assert style.value_label_arrow_line_style is ValueLabelArrowLineStyle.DASHED
    assert style.value_label_arrow_color == arrow_color
    assert style.value_label_arrow_width == 2.5
    assert style.value_label_arrow_line_style == "dashed"


def test_loading_shows_the_stored_arrow_styling_in_the_controls():
    tab = _tab()

    tab.load_series_style(_line_series(show_value_labels=True, value_label_show_arrow=True, **STYLED))

    assert tab.value_labels_arrow_style_control.currentValue() == "filled_arrow"
    assert tab.value_labels_arrow_match_color_toggle.isChecked() is False
    assert tab.value_labels_arrow_color_row.currentColor() == "#2ca02c"
    assert tab.value_labels_arrow_width_slider.value() == 2.5
    assert tab.value_labels_arrow_line_style_control.currentValue() == "dashed"


def test_an_arrow_matching_the_label_shows_the_label_color_in_the_swatch():
    tab = _tab()
    series = _line_series(
        color="#9467bd", show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="",
    )

    tab.load_series_style(series)

    assert tab.value_labels_arrow_match_color_toggle.isChecked() is True
    assert tab.value_labels_arrow_color_row.currentColor() == "#9467bd"

    series.style.value_label_text_color = "#d62728"
    tab.load_series_style(series)

    assert tab.value_labels_arrow_color_row.currentColor() == "#d62728"


def test_choosing_each_arrow_setting_updates_the_series_style_and_notifies():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_show_arrow=True)
    tab.set_selected("series", series)
    changes = []
    tab.configChanged.connect(lambda: changes.append(True))

    def changed(action):
        before = len(changes)
        action()
        return len(changes) > before

    style_control = tab.value_labels_arrow_style_control
    assert changed(lambda: style_control.setCurrentIndex(style_control.findData("arrow")))
    assert series.style.value_label_arrow_style == "arrow"

    assert changed(lambda: _pick_color(tab, "#1f77b4"))
    assert series.style.value_label_arrow_color == "#1f77b4"

    assert changed(lambda: tab.value_labels_arrow_width_slider._spinbox.setValue(3.0))
    assert series.style.value_label_arrow_width == 3.0

    line_style_control = tab.value_labels_arrow_line_style_control
    assert changed(lambda: line_style_control.setCurrentIndex(line_style_control.findData("dotted")))
    assert series.style.value_label_arrow_line_style == "dotted"


def test_turning_on_match_text_color_stores_an_empty_color_and_turning_it_off_restores_the_swatch_color():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="#2ca02c")
    tab.set_selected("series", series)
    changes = []
    tab.configChanged.connect(lambda: changes.append(True))

    tab.value_labels_arrow_match_color_toggle.setChecked(checked=True)

    assert series.style.value_label_arrow_color == ""
    assert changes

    tab.value_labels_arrow_match_color_toggle.setChecked(checked=False)

    assert series.style.value_label_arrow_color == tab.value_labels_arrow_color_row.currentColor()


def test_arrow_controls_are_hidden_until_the_arrow_is_turned_on():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_show_arrow=False)
    tab.set_selected("series", series)

    assert not any(control.isVisible() for control in _arrow_controls(tab))
    assert tab.value_labels_arrow_color_row.isVisible() is False
    assert tab.value_labels_arrow_color_label.isVisible() is False

    tab.value_labels_arrow_toggle.setChecked(checked=True)

    assert all(control.isVisible() for control in _arrow_controls(tab))
    assert tab.value_labels_arrow_color_row.isVisible() is True
    assert tab.value_labels_arrow_color_label.isVisible() is True
    assert series.style.value_label_show_arrow is True

    tab.value_labels_arrow_toggle.setChecked(checked=False)

    assert not any(control.isVisible() for control in _arrow_controls(tab))


def test_arrow_controls_are_hidden_while_value_labels_are_off():
    tab = _tab()
    series = _line_series(show_value_labels=False, value_label_show_arrow=True)

    tab.set_selected("series", series)

    assert not any(control.isVisible() for control in _arrow_controls(tab))


def test_arrow_color_swatch_is_hidden_while_the_arrow_matches_the_label():
    tab = _tab()
    series = _line_series(show_value_labels=True, value_label_show_arrow=True)
    tab.set_selected("series", series)
    assert tab.value_labels_arrow_color_row.isVisible() is True

    tab.value_labels_arrow_match_color_toggle.setChecked(checked=True)

    assert tab.value_labels_arrow_color_row.isVisible() is False
    assert tab.value_labels_arrow_color_label.isVisible() is False
    assert tab.value_labels_arrow_match_color_toggle.isVisible() is True


@pytest.mark.parametrize("make_series", [_line_series, _scatter_series])
def test_arrow_controls_are_shown_for_line_and_scatter_series(make_series):
    tab = _tab()

    tab.set_selected("series", make_series(show_value_labels=True, value_label_show_arrow=True))

    assert all(control.isVisible() for control in _arrow_controls(tab))


def test_arrow_controls_are_hidden_for_bar_series():
    tab = _tab()
    bar_series = DataSeries(dataset_id="ds1", x_column="x", y_column="y", series_type=SeriesType.BAR)
    bar_series.style.show_value_labels = True

    tab.set_selected("series", bar_series)

    assert tab.value_labels_enabled_toggle.isChecked() is True
    assert not any(control.isVisible() for control in _arrow_controls(tab))


def test_unusable_stored_arrow_values_show_the_defaults_not_the_previous_series_values():
    tab = _tab()
    first = _line_series(show_value_labels=True, value_label_show_arrow=True, **STYLED)
    second = _line_series(show_value_labels=True, value_label_show_arrow=True)
    # Assigned after construction, so they bypass the style's own normalization.
    second.style.value_label_arrow_style = "not-a-style"
    second.style.value_label_arrow_line_style = "not-a-line-style"

    tab.load_series_style(first)
    tab.load_series_style(second)

    assert tab.value_labels_arrow_style_control.currentValue() == "line"
    assert tab.value_labels_arrow_line_style_control.currentValue() == "solid"


def test_switching_series_does_not_carry_arrow_settings_over():
    tab = _tab()
    styled = _line_series(show_value_labels=True, value_label_show_arrow=True, **STYLED)
    plain = _scatter_series(show_value_labels=True, value_label_show_arrow=True)

    tab.load_series_style(styled)
    tab.load_series_style(plain)
    tab.apply_series_style_to(plain)

    assert plain.style.value_label_arrow_style == "line"
    assert plain.style.value_label_arrow_color == "#000000"
    assert plain.style.value_label_arrow_width == 1.0
    assert plain.style.value_label_arrow_line_style == "solid"


def test_loading_does_not_report_a_change():
    tab = _tab()
    changes = []
    tab.configChanged.connect(lambda: changes.append(True))

    tab.load_series_style(_line_series(show_value_labels=True, value_label_show_arrow=True, **STYLED))

    assert not changes


def test_arrow_line_style_icons_follow_the_theme():
    tab = _tab()
    # A sentinel icon colour no theme uses, so the icons can only match if they were built from these tokens.
    tokens = design_tokens(text_primary="#ff00ff")
    size = QSize(32, 16)

    tab.apply_theme(tokens)

    control = tab.value_labels_arrow_line_style_control
    assert control.count() == len(ValueLabelArrowLineStyle)
    for index in range(control.count()):
        expected = build_line_style_icon(LineStyleType(control.itemData(index)), tokens)
        assert control.itemIcon(index).pixmap(size).toImage() == expected.pixmap(size).toImage()


@pytest.mark.parametrize(
    ("make_series", "expected"),
    [(_line_series, "#1f77b4"), (_scatter_series, "#8c564b")],
)
def test_an_arrow_matching_the_label_shows_the_color_the_label_is_drawn_in(make_series, expected):
    """Scatter labels inherit the marker color (render_scatter_series), Line labels the line color,
    so that is what the swatch must show once Match text color is turned off."""
    tab = _tab()
    series = make_series(show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="")
    series.style.color = "#1f77b4"
    series.style.marker.marker_color = "#8c564b"

    tab.load_series_style(series)

    assert tab.value_labels_arrow_color_row.currentColor() == expected
