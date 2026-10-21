"""DecimalInput / IntegerInput: the spin-box replacement.

Covers the spin-box-compatible API call sites rely on, and the behaviour that
motivated replacing QSpinBox/QDoubleSpinBox: commit-on-finish instead of a value
per keystroke, a wheel that only edits while focused, bigger step buttons and
keyboard stepping.
"""
import ast
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QLocale, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pandaplot.gui.components.common.number_input import DecimalInput, IntegerInput, NumberInput
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def shown():
    """Show widgets in a window so focus works; closes them afterwards."""
    windows: list[QWidget] = []

    def show(widget: NumberInput) -> NumberInput:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.addWidget(widget)
        host.resize(260, 80)
        host.show()
        host.activateWindow()
        QTest.qWaitForWindowActive(host)
        windows.append(host)
        return widget

    try:
        yield show
    finally:
        for window in windows:
            window.close()


def _recorder(widget):
    seen: list = []
    widget.valueChanged.connect(seen.append)
    return seen


def _type(widget: NumberInput, text: str) -> None:
    """Replace the field's text as typing would, without committing it."""
    widget._edit.selectAll()
    QTest.keyClicks(widget._edit, text)


def _wheel(widget: QWidget, delta: int) -> QWheelEvent:
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,  # noqa: FBT003 -- Qt constructor argument
    )
    QApplication.sendEvent(widget, event)
    return event


def _key(widget: QWidget, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers)
    QApplication.sendEvent(widget, event)
    return event


# -- spin-box compatible API ------------------------------------------------------


def test_decimal_defaults_match_qdoublespinbox():
    widget = DecimalInput()

    assert (widget.minimum(), widget.maximum()) == (0.0, 99.99)
    assert widget.decimals() == 2
    assert widget.singleStep() == 1.0
    assert widget.value() == 0.0


def test_integer_defaults_match_qspinbox():
    widget = IntegerInput()

    assert (widget.minimum(), widget.maximum()) == (0, 99)
    assert widget.singleStep() == 1
    assert widget.value() == 0
    assert isinstance(widget.value(), int)


def test_set_value_clamps_into_range_and_rounds_to_decimals():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    widget.setDecimals(2)

    widget.setValue(3.14159)
    assert widget.value() == 3.14
    widget.setValue(50.0)
    assert widget.value() == 10.0
    widget.setValue(-5.0)
    assert widget.value() == 0.0


def test_set_value_emits_once_when_it_changes_and_not_when_it_does_not():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    seen = _recorder(widget)

    widget.setValue(2.5)
    widget.setValue(2.5)
    widget.setValue(2.501)  # rounds to 2.50, i.e. unchanged

    assert seen == [2.5]


def test_set_range_clamps_the_value_and_announces_it():
    widget = DecimalInput()
    widget.setRange(0.0, 100.0)
    widget.setValue(80.0)
    seen = _recorder(widget)

    widget.setRange(0.0, 50.0)

    assert widget.value() == 50.0
    assert seen == [50.0]


def test_set_minimum_and_maximum_adjust_one_end_of_the_range():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)

    widget.setMinimum(2.0)
    widget.setMaximum(8.0)

    assert (widget.minimum(), widget.maximum()) == (2.0, 8.0)
    assert widget.value() == 2.0


def test_set_decimals_rounds_the_value_and_the_display():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    widget.setDecimals(3)
    widget.setValue(1.2345)
    assert widget.value() == 1.234 or widget.value() == 1.235

    widget.setDecimals(1)

    assert widget.value() == 1.2
    assert widget._edit.text().endswith("2")
    assert len(widget._edit.text().replace(",", ".").split(".")[1]) == 1


def test_block_signals_silences_programmatic_changes():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    seen = _recorder(widget)

    widget.blockSignals(True)  # noqa: FBT003 -- Qt bound method, positional-only
    widget.setValue(4.0)
    widget.blockSignals(False)  # noqa: FBT003 -- Qt bound method, positional-only

    assert seen == []
    assert widget.value() == 4.0


def test_non_finite_values_are_ignored():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    widget.setValue(3.0)
    seen = _recorder(widget)

    widget.setValue(float("nan"))
    widget.setValue(float("inf"))

    assert widget.value() == 3.0
    assert seen == []


def test_integer_input_emits_ints_and_clamps_to_32_bits():
    widget = IntegerInput()
    seen = _recorder(widget)

    widget.setRange(-(10**12), 10**12)
    widget.setValue(10**11)

    assert widget.maximum() == 2_147_483_647
    assert widget.minimum() == -2_147_483_648
    assert seen == [2_147_483_647]
    assert all(isinstance(value, int) for value in seen)


def test_integer_single_step_is_at_least_one():
    widget = IntegerInput()
    widget.setSingleStep(0)

    assert widget.singleStep() == 1


def test_integer_input_rejects_a_typed_decimal_point(shown):
    widget = shown(IntegerInput())
    widget.setRange(0, 1000)

    _type(widget, "1.5")

    assert widget._edit.text() == "15"


# -- typing and committing --------------------------------------------------------


def test_value_follows_typing_without_leaving_the_field(shown):
    """On macOS clicking a push button does not move focus out of the field
    (and fires no editingFinished), so an "Apply" button reads value() while
    the field still has focus: it must already be the typed number."""
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setValue(3.0)

    _type(widget, "12,5")

    assert widget._edit.hasFocus()
    assert widget.value() == 12.5


def test_typing_emits_for_each_complete_in_range_number(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    seen = _recorder(widget)

    _type(widget, "12")

    assert seen == [1.0, 12.0]


def test_half_typed_and_out_of_range_text_does_not_change_the_value(shown):
    widget = shown(DecimalInput())
    widget.setRange(1.0, 10.0)
    widget.setValue(4.0)
    seen = _recorder(widget)

    _type(widget, "-")
    assert widget.value() == 4.0
    _type(widget, "0")  # below the minimum
    assert widget.value() == 4.0
    _type(widget, "55")  # "5" is in range, "55" is not

    assert seen == [5.0]
    assert widget.value() == 5.0


def test_leaving_the_field_clamps_and_reformats_what_was_typed(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 10.0)
    widget.setDecimals(2)
    other = DecimalInput(widget.parentWidget())
    other.show()
    seen = _recorder(widget)

    _type(widget, "55")
    assert widget._edit.text() == "55"
    other._edit.setFocus()
    QApplication.processEvents()

    assert widget.value() == 10.0
    assert widget._parse(widget._edit.text()) == 10.0
    assert seen == [5.0, 10.0]


def test_enter_reformats_the_typed_value(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setDecimals(2)

    _type(widget, "7")
    assert widget._edit.text() == "7"
    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget._edit.text() in ("7,00", "7.00")


def test_no_more_decimals_can_be_typed_than_the_input_shows(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setDecimals(2)

    _type(widget, "1.2345")
    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget._edit.text() in ("1.23", "1,23")


def test_a_decimal_input_with_no_decimals_takes_no_separator(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setDecimals(0)

    _type(widget, "1.5")

    assert widget._edit.text() == "15"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("12,5", 12.5),
        ("12.5", 12.5),
        ("1,234.5", 1234.5),
        ("1.234,5", 1234.5),
        ("1e-3", 0.001),
        ("−3", -3.0),
        ("+4", 4.0),
        (" 6 ", 6.0),
    ],
)
def test_committing_accepts_common_number_spellings(typed, expected):
    widget = DecimalInput()
    widget.setRange(-10_000.0, 10_000.0)
    widget.setDecimals(4)

    widget._edit.setText(typed)
    widget._commit_text()

    assert widget.value() == pytest.approx(expected)


@pytest.mark.parametrize("typed", ["", "-", "abc", "1e", "nan", "inf", "."])
def test_committing_unreadable_text_restores_the_previous_value(typed):
    widget = DecimalInput()
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    seen = _recorder(widget)

    widget._edit.setText(typed)
    widget._commit_text()

    assert widget.value() == 5.0
    assert seen == []
    assert widget._parse(widget._edit.text()) == 5.0


def test_committing_an_out_of_range_value_clamps_it():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    seen = _recorder(widget)

    widget._edit.setText("500")
    widget._commit_text()

    assert widget.value() == 10.0
    assert seen == [10.0]


def test_out_of_range_text_is_flagged_invalid_while_typing(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 10.0)

    _type(widget, "55")
    assert widget.property("invalid") is True

    _type(widget, "5")
    assert widget.property("invalid") is False


def test_committing_clears_the_invalid_flag(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 10.0)
    _type(widget, "55")

    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget.property("invalid") is False
    assert widget.value() == 10.0


def test_escape_discards_text_that_is_not_a_usable_number(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    _type(widget, "88")
    QTest.keyClicks(widget._edit, "0")  # "880" is out of range, so value stays 88
    assert widget.value() == 88.0

    event = _key(widget._edit, Qt.Key.Key_Escape)

    assert event.isAccepted()
    assert widget._parse(widget._edit.text()) == 88.0


def test_escape_with_a_usable_number_is_left_for_the_dialog(shown):
    """Otherwise Escape would stop closing a dialog while a field has focus."""
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    _type(widget, "20")

    event = _key(widget._edit, Qt.Key.Key_Escape)

    assert not event.isAccepted()
    assert widget.value() == 20.0


# -- stepping ---------------------------------------------------------------------


def test_arrow_keys_step_by_the_single_step(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setSingleStep(0.5)
    widget.setValue(10.0)

    _key(widget._edit, Qt.Key.Key_Up)
    assert widget.value() == 10.5
    _key(widget._edit, Qt.Key.Key_Down)
    _key(widget._edit, Qt.Key.Key_Down)

    assert widget.value() == 9.5


def test_shift_and_page_keys_step_ten_times_as_far(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setValue(100.0)

    _key(widget._edit, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert widget.value() == 110.0
    _key(widget._edit, Qt.Key.Key_PageDown)
    assert widget.value() == 100.0
    _key(widget._edit, Qt.Key.Key_PageUp)

    assert widget.value() == 110.0


def test_stepping_stops_at_the_limits(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 3.0)
    widget.setValue(2.5)

    _key(widget._edit, Qt.Key.Key_Up)
    _key(widget._edit, Qt.Key.Key_Up)
    assert widget.value() == 3.0
    _key(widget._edit, Qt.Key.Key_PageDown)
    _key(widget._edit, Qt.Key.Key_Down)

    assert widget.value() == 0.0


def test_stepping_starts_from_text_that_has_not_been_committed_yet(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    _type(widget, "20")

    _key(widget._edit, Qt.Key.Key_Up)

    assert widget.value() == 21.0


def test_stepping_has_no_floating_point_drift(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 10.0)
    widget.setDecimals(1)
    widget.setSingleStep(0.1)

    for _ in range(3):
        _key(widget._edit, Qt.Key.Key_Up)

    assert widget.value() == 0.3


def test_step_buttons_step_and_disable_at_the_limits():
    widget = DecimalInput()
    widget.setRange(0.0, 2.0)
    widget.setValue(1.0)

    widget._increase.click()
    assert widget.value() == 2.0
    assert not widget._increase.isEnabled()
    assert widget._decrease.isEnabled()

    widget._decrease.click()
    widget._decrease.click()

    assert widget.value() == 0.0
    assert not widget._decrease.isEnabled()
    assert widget._increase.isEnabled()


def test_shift_click_steps_ten_times_as_far(monkeypatch):
    monkeypatch.setattr(QApplication, "keyboardModifiers", staticmethod(lambda: Qt.KeyboardModifier.ShiftModifier))
    widget = DecimalInput()
    widget.setRange(0.0, 100.0)

    widget._increase.click()

    assert widget.value() == 10.0


def test_holding_a_step_button_repeats():
    widget = DecimalInput()

    assert widget._increase.autoRepeat()
    assert widget._decrease.autoRepeat()


def test_step_buttons_are_big_enough_to_hit():
    widget = DecimalInput()

    assert widget._increase.width() >= 24
    assert widget._decrease.width() >= 24
    assert widget.height() >= 28


def test_steppers_can_be_left_out():
    widget = DecimalInput(steppers=False)
    widget.show()
    try:
        assert not widget._increase.isVisible()
        assert not widget._decrease.isVisible()
        assert widget.minimumSizeHint().width() < DecimalInput().minimumSizeHint().width()
    finally:
        widget.close()


# -- wheel ------------------------------------------------------------------------


def test_wheel_does_not_edit_a_field_that_is_not_focused(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.clearFocus()

    event = _wheel(widget._edit, 120)

    assert widget.value() == 5.0
    assert not event.isAccepted()


def test_wheel_steps_a_focused_field(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.setFocus()
    QApplication.processEvents()

    up = _wheel(widget._edit, 120)
    assert widget.value() == 6.0
    assert up.isAccepted()
    _wheel(widget._edit, -120)
    _wheel(widget._edit, -120)

    assert widget.value() == 4.0


@pytest.mark.parametrize("part", ["frame", "edit", "increase", "decrease"])
def test_every_part_leaves_the_wheel_to_the_panel_when_unfocused(shown, part):
    """Ignored events propagate to the enclosing scroll area, so scrolling a
    sidebar never edits a number the pointer happens to pass over. (Qt only
    propagates events that come from the window system, so the contract is
    checked as "not accepted" on each part.)"""
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.clearFocus()
    target = {"frame": widget, "edit": widget._edit, "increase": widget._increase, "decrease": widget._decrease}[part]

    event = _wheel(target, -120)

    assert not event.isAccepted()
    assert widget.value() == 5.0


# -- display ----------------------------------------------------------------------


def test_special_value_text_is_shown_at_the_minimum_and_typing_it_selects_the_minimum():
    widget = DecimalInput()
    widget.setRange(0.0, 10.0)
    widget.setSpecialValueText("Auto")
    widget.setSuffix(" px")
    widget.setValue(2.0)
    assert widget._edit.text() != "Auto"
    assert not widget._suffix_label.isHidden()

    widget.setValue(0.0)
    assert widget._edit.text() == "Auto"
    assert widget._suffix_label.isHidden()

    widget.setValue(2.0)
    widget._edit.setText("auto")
    widget._commit_text()

    assert widget.value() == 0.0


def test_suffix_is_a_separate_label_that_is_not_part_of_the_editable_text():
    widget = IntegerInput()
    widget.setRange(0, 100)
    widget.setSuffix(" pt")
    widget.setValue(12)

    assert widget.suffix() == " pt"
    assert widget._suffix_label.text() == "pt"
    assert widget._edit.text() == "12"
    assert not widget._suffix_label.isHidden()

    widget.setSuffix("")
    assert widget._suffix_label.isHidden()


def test_text_includes_the_unit_and_clean_text_does_not():
    widget = IntegerInput()
    widget.setRange(0, 100)
    widget.setSuffix(" pt")
    widget.setValue(12)

    assert widget.text() == "12 pt"
    assert widget.cleanText() == "12"

    widget.setSpecialValueText("Auto")
    widget.setValue(0)
    assert widget.text() == "Auto"


def test_decimal_display_uses_the_configured_number_of_decimals():
    widget = DecimalInput()
    widget.setRange(0.0, 100.0)
    widget.setDecimals(3)
    widget.setValue(2.0)

    assert widget._parse(widget._edit.text()) == 2.0
    separator = "," if "," in widget._edit.text() else "."
    assert len(widget._edit.text().split(separator)[1]) == 3


def test_selects_the_whole_value_when_focused(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(42.0)
    widget._edit.deselect()

    widget._edit.clearFocus()
    widget._edit.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.qWait(20)

    assert widget._edit.selectedText() == widget._edit.text()


# -- focus and accessibility ------------------------------------------------------


def test_focus_goes_to_the_text_field_and_the_frame_tracks_it(shown):
    widget = shown(DecimalInput())
    other = DecimalInput(widget.parentWidget())
    other.show()

    widget.setFocus()
    QApplication.processEvents()
    assert widget.focusProxy() is widget._edit
    assert widget._edit.hasFocus()
    assert widget.property("focused") is True

    other.setFocus()
    QApplication.processEvents()
    assert widget.property("focused") is False


def test_only_the_text_field_takes_tab_focus():
    widget = DecimalInput()

    assert widget._edit.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert widget._increase.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert widget._decrease.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_step_buttons_are_named_for_assistive_technology():
    widget = DecimalInput()

    assert widget._increase.accessibleName() == "Increase value"
    assert widget._decrease.accessibleName() == "Decrease value"
    assert "Up and Down" in widget._increase.accessibleDescription()


def test_accessible_name_and_description_reach_the_text_field():
    widget = DecimalInput()

    widget.setAccessibleName("Line width")
    widget.setAccessibleDescription("Width in points")

    assert widget._edit.accessibleName() == "Line width"
    assert widget._edit.accessibleDescription() == "Width in points"
    assert widget.accessibleName() == "Line width"


def test_disabled_input_disables_its_parts():
    widget = DecimalInput()

    widget.setEnabled(False)

    assert not widget._edit.isEnabled()
    assert not widget._increase.isEnabled()


# -- appearance -------------------------------------------------------------------


@pytest.fixture
def themed_app(qapp):
    original_sheet = qapp.styleSheet()
    original_palette = qapp.palette()

    def apply(theme: Theme) -> dict:
        manager = ThemeManager.__new__(ThemeManager)
        manager._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
        qapp.setStyleSheet(manager.build_stylesheet(manager._current))
        return manager.get_design_tokens()

    try:
        yield apply
    finally:
        qapp.setStyleSheet(original_sheet)
        qapp.setPalette(original_palette)


def _border_colour(widget: NumberInput) -> str:
    host = widget.window()
    image = host.grab().toImage()
    point = widget.mapTo(host, QPoint(0, widget.height() // 2))
    return QColor(image.pixel(point.x(), point.y())).name()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_field_border_follows_the_theme_and_state(themed_app, shown, theme):
    tokens = themed_app(theme)
    widget = shown(DecimalInput())
    widget.setRange(0.0, 10.0)
    other = DecimalInput(widget.parentWidget())
    other.show()
    other.setFocus()
    QApplication.processEvents()

    assert _border_colour(widget) == QColor(tokens["border_control"]).name()

    widget.setFocus()
    QApplication.processEvents()
    assert _border_colour(widget) == QColor(tokens["accent"]).name()

    _type(widget, "55")
    assert _border_colour(widget) == QColor(tokens["status_danger"]).name()


def test_disabled_field_is_inset(themed_app, shown):
    tokens = themed_app(Theme.LIGHT)
    widget = shown(DecimalInput())
    widget.setEnabled(False)
    QApplication.processEvents()

    assert _border_colour(widget) == QColor(tokens["border_subtle"]).name()


# -- the rest of the app uses them ------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "pandaplot"


def _production_trees():
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path, ast.parse(path.read_text(encoding="utf-8"))


def test_production_code_never_instantiates_a_spin_box():
    """A spin box brings back the tiny arrows and the wheel that edits values
    while scrolling. Use DecimalInput / IntegerInput."""
    offenders = [
        f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno}"
        for path, tree in _production_trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("QSpinBox", "QDoubleSpinBox")
    ]

    assert offenders == [], f"use DecimalInput / IntegerInput instead: {offenders}"


def test_no_stylesheet_targets_a_spin_box():
    """Spin-box rules would silently style nothing now; number inputs are
    styled in ThemeManager."""
    offenders = [
        f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno}"
        for path, tree in _production_trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "SpinBox" in node.value and "{" in node.value
    ]

    assert offenders == [], f"QSpinBox QSS no longer matches anything: {offenders}"


# -- review follow-ups (#487) -------------------------------------------------------


def test_setting_the_value_it_already_has_leaves_the_typed_text_alone(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setDecimals(1)
    widget._edit.setFocus()
    _type(widget, "5")
    cursor_text = widget._edit.text()

    widget.setValue(widget.value())

    assert widget._edit.text() == cursor_text == "5"


def test_setting_the_same_value_still_restores_text_that_is_not_a_number(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    _type(widget, "500")

    widget.setValue(5.0)

    assert widget.value() == 5.0
    assert widget._edit.text() in ("5,00", "5.00")


def test_a_tiny_negative_value_is_stored_as_plain_zero():
    widget = DecimalInput()
    widget.setRange(-10.0, 10.0)

    widget.setValue(-0.001)

    assert str(widget.value()) == "0.0"


@pytest.mark.parametrize("point_size", [10, 24, 36])
def test_the_field_grows_with_the_font_instead_of_clipping_the_text(shown, point_size):
    widget = DecimalInput()
    font = widget.font()
    font.setPointSize(point_size)
    widget.setFont(font)
    shown(widget)
    QApplication.processEvents()

    needed = widget.fontMetrics().height()

    assert widget.height() >= needed
    assert widget.sizeHint().height() >= needed
    assert widget.height() >= 28


def test_the_field_resizes_when_the_font_changes_after_it_is_shown(shown):
    widget = shown(DecimalInput())
    before = widget.height()
    font = widget.font()
    font.setPointSize(40)

    widget.setFont(font)
    QApplication.processEvents()
    widget.parentWidget().layout().activate()

    assert widget.height() > before
    assert widget.height() >= widget.fontMetrics().height()


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("1,234.5", 1234.5),
        ("1.234,5", 1234.5),
        ("1,234,567", 1234567.0),
        ("12.5", 12.5),
        ("-1,234.5", -1234.5),
    ],
)
def test_grouped_spellings_can_be_typed_not_just_committed(shown, typed, expected):
    widget = shown(DecimalInput())
    widget.setRange(-1e9, 1e9)
    widget.setDecimals(2)

    _type(widget, typed)
    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget.value() == pytest.approx(expected)


def test_grouped_spellings_still_respect_the_decimal_limit(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1e9)
    widget.setDecimals(2)

    _type(widget, "1,234.567")

    assert widget._edit.text() == "1,234.56"


def test_a_grouped_number_can_be_pasted(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1e9)
    widget.setDecimals(2)
    widget._edit.selectAll()

    widget._edit.insert("1.234,5")
    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget.value() == pytest.approx(1234.5)


@pytest.fixture
def arabic_locale():
    previous = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.Arabic, QLocale.Country.Egypt))
    try:
        yield
    finally:
        QLocale.setDefault(previous)


def test_a_value_shown_in_a_non_latin_locale_reads_back_the_same(arabic_locale):
    widget = DecimalInput()
    widget.setRange(0.0, 1000.0)
    widget.setValue(12.5)
    shown_text = widget._edit.text()

    widget._edit.setText(shown_text)
    widget._commit_text()

    assert shown_text not in ("12.50", "12,50")
    assert widget.value() == pytest.approx(12.5)


def test_a_value_shown_in_a_non_latin_locale_can_be_edited_by_typing(shown, arabic_locale):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 1000.0)
    widget.setValue(12.5)
    shown_text = widget._edit.text()
    widget._edit.setFocus()
    widget._edit.setCursorPosition(len(shown_text))

    QTest.keyClick(widget._edit, Qt.Key.Key_Backspace)
    QTest.keyClick(widget._edit, Qt.Key.Key_Backspace)
    QTest.keyClicks(widget._edit, "7")
    QTest.keyClick(widget._edit, Qt.Key.Key_Return)

    assert widget.value() == pytest.approx(12.7)


def test_the_wheel_accumulates_partial_notches(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.setFocus()
    QApplication.processEvents()

    for _ in range(7):
        _wheel(widget._edit, 15)
    assert widget.value() == 5.0
    _wheel(widget._edit, 15)

    assert widget.value() == 6.0


def test_one_large_wheel_delta_steps_once_per_notch(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.setFocus()
    QApplication.processEvents()

    _wheel(widget._edit, 240)
    assert widget.value() == 7.0
    _wheel(widget._edit, -360)

    assert widget.value() == 4.0


def test_reversing_the_wheel_discards_the_pending_remainder(shown):
    widget = shown(DecimalInput())
    widget.setRange(0.0, 100.0)
    widget.setValue(5.0)
    widget._edit.setFocus()
    QApplication.processEvents()

    _wheel(widget._edit, 90)
    _wheel(widget._edit, -60)
    _wheel(widget._edit, -60)

    assert widget.value() == 4.0
