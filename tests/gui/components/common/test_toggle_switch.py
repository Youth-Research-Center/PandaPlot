"""ToggleSwitch keyboard operability: it must take focus and toggle from the
keyboard, since it is a custom-painted widget with no native behavior."""
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.toggle_switch import ToggleSwitch


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def test_toggle_switch_is_focusable():
    assert ToggleSwitch().focusPolicy() == Qt.FocusPolicy.StrongFocus


@pytest.mark.parametrize("key", [Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_toggle_switch_toggles_from_the_keyboard(qtbot, key):
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)

    qtbot.keyClick(toggle, key)
    assert toggle.isChecked() is True
    qtbot.keyClick(toggle, key)
    assert toggle.isChecked() is False
