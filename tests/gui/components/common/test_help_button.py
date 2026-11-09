"""Tests for the shared help-button helper."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.help_button import build_help_button, help_button_stylesheet


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_build_help_button_sets_text_and_accessibility():
    button = build_help_button(accessible_name="Help: X", accessible_description="Opens X", tooltip="Tip")

    assert button.text() == "?"
    assert button.toolTip() == "Tip"
    assert button.accessibleName() == "Help: X"
    assert button.accessibleDescription() == "Opens X"
    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_build_help_button_uses_parent():
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    button = build_help_button(accessible_name="a", accessible_description="b", tooltip="c", parent=parent)

    assert button.parent() is parent


def test_stylesheet_uses_foreground_colour():
    sheet = help_button_stylesheet("#abcdef")

    assert sheet.count("#abcdef") == 3
    assert "QToolButton:hover" in sheet
    assert "QToolButton:focus" in sheet
