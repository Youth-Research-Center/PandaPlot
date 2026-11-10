"""ToggleSwitch geometry and keyboard operability: it must take focus and toggle from the
keyboard, since it is a custom-painted widget with no native behavior."""
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.toggle_switch import ToggleSwitch, knob_x_for_state


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def test_knob_x_for_off_state_is_at_left_margin():
    assert knob_x_for_state(checked=False, track_width=26, knob_diameter=11, margin=2) == 2


def test_knob_x_for_on_state_is_at_right_margin():
    # track_width - knob_diameter - margin
    assert knob_x_for_state(checked=True, track_width=26, knob_diameter=11, margin=2) == 13


def test_knob_x_scales_with_custom_track_width():
    assert knob_x_for_state(checked=True, track_width=40, knob_diameter=15, margin=3) == 22


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


def test_toggle_switch_is_a_checkable_button_so_assistive_tech_sees_its_state(qtbot):
    from PySide6.QtWidgets import QAbstractButton

    toggle = ToggleSwitch(checked=True)
    qtbot.addWidget(toggle)

    assert isinstance(toggle, QAbstractButton)
    assert toggle.isCheckable() is True
    assert toggle.isChecked() is True


def test_toggle_switch_set_checked_emits_toggled_once_per_change(qtbot):
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)
    emitted = []
    toggle.toggled.connect(emitted.append)

    toggle.setChecked(checked=True)
    toggle.setChecked(checked=True)

    assert emitted == [True]
