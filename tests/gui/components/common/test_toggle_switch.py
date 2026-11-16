"""ToggleSwitch geometry and keyboard operability: it must take focus and toggle from the
keyboard, since it is a custom-painted widget with no native behavior."""
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.toggle_switch import ToggleSwitch, knob_x_for_state
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.contrast import contrast_ratio
from tests.gui.icon_testing import assert_tinted
from tests.gui.theme_testing import DEFAULT_ACCENT, design_tokens, surface_palette


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


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#0E7C86", DEFAULT_ACCENT])
def test_checked_focus_ring_stands_out_from_the_accent_track(qtbot, theme: Theme, accent: str) -> None:
    """#581: when checked, the focus ring is drawn over the accent track, so it needs 3:1 against `accent`."""
    toggle = ToggleSwitch(checked=True)
    qtbot.addWidget(toggle)
    tokens = design_tokens(theme, accent=accent)
    toggle.set_tokens(tokens)

    assert contrast_ratio(toggle._focus_ring_color(), QColor(tokens["accent"])) >= 3.0


def test_unchecked_focus_ring_uses_the_accent(qtbot) -> None:
    toggle = ToggleSwitch(checked=False)
    qtbot.addWidget(toggle)
    tokens = design_tokens()
    toggle.set_tokens(tokens)

    assert toggle._focus_ring_color().name().upper() == tokens["accent"]


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_unchecked_track_uses_the_toggle_off_token(qtbot, theme: Theme) -> None:
    """The off track is `toggle_off`, which keeps 3:1 against the surface it sits on; `border_panel` did not."""
    toggle = ToggleSwitch(checked=False)
    qtbot.addWidget(toggle)
    tokens = design_tokens(theme)
    toggle.set_tokens(tokens)

    image = toggle.grab().toImage()
    # Mid-track, right of the knob (the unchecked knob sits at the left).
    track_pixel = image.pixelColor(21, 7)

    assert_tinted(track_pixel, tokens["toggle_off"])
    assert contrast_ratio(QColor(tokens["toggle_off"]), QColor(surface_palette(theme)["card_bg"])) >= 3.0
