import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.color_swatch_row import ColorSwatchRow, is_valid_hex_color


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_is_valid_hex_color_accepts_six_digit_hex():
    assert is_valid_hex_color("#4A56C6") is True


def test_is_valid_hex_color_accepts_three_digit_hex():
    assert is_valid_hex_color("#FFF") is True


def test_is_valid_hex_color_rejects_missing_hash():
    assert is_valid_hex_color("4A56C6") is False


def test_is_valid_hex_color_rejects_non_hex_characters():
    assert is_valid_hex_color("#GGGGGG") is False


def test_default_selects_first_palette_color():
    row = ColorSwatchRow(["#A01818", "#4A56C6"])
    assert row.currentColor() == "#A01818"


def test_set_current_color_to_palette_entry_selects_it():
    row = ColorSwatchRow(["#A01818", "#4A56C6"])
    row.setCurrentColor("#4A56C6")
    assert row.currentColor() == "#4A56C6"


def test_set_current_color_to_custom_hex_is_stored_even_if_not_in_palette():
    row = ColorSwatchRow(["#A01818", "#4A56C6"])
    row.setCurrentColor("#123456")
    assert row.currentColor() == "#123456"


def test_clicking_a_swatch_emits_color_changed():
    row = ColorSwatchRow(["#A01818", "#4A56C6"])
    seen = []
    row.colorChanged.connect(seen.append)
    row._swatch_buttons[1].click()
    assert seen == ["#4A56C6"]


def test_icon_only_swatches_and_custom_button_have_accessible_names():
    row = ColorSwatchRow(["#A01818", "#4A56C6"])

    names = [button.accessibleName() for button in row._swatch_buttons]
    assert names == ["Color #A01818", "Color #4A56C6"]
    assert all(button.toolTip() for button in row._swatch_buttons)
    assert row._custom_button.accessibleName() == "Custom color"
    assert row._custom_button.toolTip()
