"""The marker shape combo lists plain names with bundled shape icons instead of glyph prefixes."""

import re
import sys

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.chart.chart_configuration import MarkerType

EXPECTED = [
    ("Circle", MarkerType.CIRCLE, "circle"),
    ("Square", MarkerType.SQUARE, "square"),
    ("Triangle", MarkerType.TRIANGLE, "triangle"),
    ("Diamond", MarkerType.DIAMOND, "diamond"),
    ("Star", MarkerType.STAR, "star"),
    ("Plus", MarkerType.PLUS, "plus"),
    ("Cross", MarkerType.CROSS, "x"),
]
DARK_TEXT = "#E2E2E2"
ICON_SIZE = 16


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _pixels(icon):
    return icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def test_marker_options_have_plain_names_enum_values_and_shape_icons():
    combo = StyleTab(app_context=None).marker_shape_control

    assert combo.count() == len(EXPECTED)
    for index, (label, value, icon_name) in enumerate(EXPECTED):
        assert combo.itemText(index) == label
        assert re.fullmatch(r"[A-Za-z ]+", label)
        assert combo.itemData(index) is value
        assert not combo.itemIcon(index).isNull()
        assert _pixels(combo.itemIcon(index)) == _pixels(build_icon(icon_name, "#1C1E26", size=ICON_SIZE))


def test_marker_icons_follow_the_theme():
    tab = StyleTab(app_context=None)

    tab.apply_theme({"text_primary": DARK_TEXT})

    combo = tab.marker_shape_control
    for index, (_label, _value, icon_name) in enumerate(EXPECTED):
        assert _pixels(combo.itemIcon(index)) == _pixels(build_icon(icon_name, DARK_TEXT, size=ICON_SIZE))


def test_selecting_a_marker_still_round_trips_the_enum_value():
    combo = StyleTab(app_context=None).marker_shape_control

    combo.setCurrentValue(MarkerType.STAR)

    assert combo.currentValue() is MarkerType.STAR
    assert combo.currentText() == "Star"
