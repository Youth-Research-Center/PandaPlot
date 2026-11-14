import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.line_style_icons import (
    build_line_style_icon,
    line_style_pen_style,
)
from pandaplot.models.chart.chart_configuration import LineStyleType
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_line_style_pen_style_maps_solid():
    assert line_style_pen_style(LineStyleType.SOLID) == Qt.PenStyle.SolidLine


def test_line_style_pen_style_maps_dashed():
    assert line_style_pen_style(LineStyleType.DASHED) == Qt.PenStyle.DashLine


def test_line_style_pen_style_maps_dotted():
    assert line_style_pen_style(LineStyleType.DOTTED) == Qt.PenStyle.DotLine


def test_line_style_pen_style_maps_dashdot():
    assert line_style_pen_style(LineStyleType.DASHDOT) == Qt.PenStyle.DashDotLine


def test_line_style_pen_style_maps_none_to_no_pen():
    assert line_style_pen_style(LineStyleType.NONE) == Qt.PenStyle.NoPen


def test_build_line_style_icon_returns_non_null_icon_for_every_style():
    tokens = design_tokens()
    for style in LineStyleType:
        icon = build_line_style_icon(style, tokens)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()
