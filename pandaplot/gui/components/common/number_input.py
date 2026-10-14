"""Shared numeric inputs that replace QSpinBox / QDoubleSpinBox.

A spin box has tiny up/down arrows and changes value when the mouse wheel
passes over it, so scrolling a sidebar edits numbers by accident.
``DecimalInput`` and ``IntegerInput`` keep the spin-box API that call sites use
(``setRange``, ``setValue``, ``value``, ``valueChanged`` ...) and its keyboard
tracking (``value()`` follows what is typed as soon as it is a valid, in-range
number, so a button that reads it right after typing sees the typed value), but:

* Large ``-`` / ``+`` buttons sit on either side of the field (hold to repeat).
* The wheel only changes the value while the field has focus; otherwise it
  scrolls the surrounding panel.
* Up/Down step by the single step, Page Up/Down and Shift step ten times as
  much, and Escape discards text that is not a usable number.
* ``.`` and ``,`` are both accepted as the decimal separator, at most
  ``decimals`` digits can follow it, and values are clamped into range when
  the field is left; text outside the range is outlined as invalid while it is
  typed.
* The unit (``setSuffix``) is a fixed label, not part of the editable text.

The look comes from ThemeManager's ``QFrame[numberInput="true"]`` rules, driven
by dynamic properties like ``PButton``.
"""
from __future__ import annotations

import math

import shiboken6
from PySide6.QtCore import QEvent, QLocale, QObject, QRegularExpression, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QRegularExpressionValidator, QWheelEvent
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

_FIELD_HEIGHT = 28
_BUTTON_WIDTH = 24
_TEXT_WIDTH = 64
_MIN_TEXT_WIDTH = 36
_COARSE_STEP_FACTOR = 10
_INT_MIN = -2_147_483_648
_INT_MAX = 2_147_483_647
_REPEAT_DELAY_MS = 400
_REPEAT_INTERVAL_MS = 60
_MINUS_SIGNS = ("−", "–")


class NumberInput(QFrame):
    """Common implementation of ``DecimalInput`` and ``IntegerInput``.

    Not used directly: the subclasses declare the typed ``valueChanged`` signal
    and the value type. The value is held as a float here and the subclasses
    convert it as it leaves the widget.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        steppers: bool = True,
        allow_fraction: bool = True,
    ):
        """Create the field.

        Args:
            parent: Parent widget.
            steppers: Show the ``-`` / ``+`` buttons. Turn off where another
                control (such as a slider) already changes the value.
            allow_fraction: Whether the decimal separator and exponent can be
                typed. ``IntegerInput`` turns this off.
        """
        super().__init__(parent)
        self._minimum = 0.0
        self._maximum = 99.99 if allow_fraction else 99.0
        self._decimals = 2 if allow_fraction else 0
        self._single_step = 1.0
        self._suffix = ""
        self._special_text = ""
        self._value = 0.0
        self._locale = QLocale()
        self._locale.setNumberOptions(self._locale.numberOptions() | QLocale.NumberOption.OmitGroupSeparator)

        self.setProperty("numberInput", True)  # noqa: FBT003 -- Qt dynamic-property API takes the value positionally
        self.setProperty("focused", False)  # noqa: FBT003 -- Qt dynamic-property API takes the value positionally
        self.setProperty("invalid", False)  # noqa: FBT003 -- Qt dynamic-property API takes the value positionally
        self.setFixedHeight(_FIELD_HEIGHT)

        self._edit = QLineEdit(self)
        self._allow_fraction = allow_fraction
        self._edit.setValidator(QRegularExpressionValidator(self._edit))
        self._refresh_validator()
        # The frame draws the border, so the edit inside it must stay flat. A
        # widget's own stylesheet outranks any dialog-level ``QLineEdit`` rule,
        # which would otherwise draw a second box inside the field.
        self._edit.setStyleSheet("QLineEdit { background: transparent; border: none; padding: 0 6px; }")
        self._edit.installEventFilter(self)
        self._edit.editingFinished.connect(self._commit_text)
        self._edit.textEdited.connect(self._on_text_edited)
        self.setFocusProxy(self._edit)

        self._suffix_label = QLabel(self)
        self._suffix_label.setObjectName("numberInputSuffix")
        self._suffix_label.hide()

        self._decrease = self._make_step_button("numberInputDecrease", "−", "Decrease value", direction=-1)
        self._increase = self._make_step_button("numberInputIncrease", "+", "Increase value", direction=1)
        self._decrease.setVisible(steppers)
        self._increase.setVisible(steppers)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self._decrease)
        layout.addWidget(self._edit, stretch=1)
        layout.addWidget(self._suffix_label)
        layout.addWidget(self._increase)

        self._refresh_display()
        self._refresh_step_buttons()

    # -- spin-box compatible API ------------------------------------------------

    def setRange(self, minimum: float, maximum: float) -> None:
        """Set the allowed range and clamp the current value into it."""
        self._minimum = float(minimum)
        self._maximum = max(float(maximum), self._minimum)
        self._apply_value(self._value)

    def setMinimum(self, minimum: float) -> None:
        self.setRange(minimum, self._maximum)

    def setMaximum(self, maximum: float) -> None:
        self.setRange(self._minimum, maximum)

    def setSingleStep(self, step: float) -> None:
        """Set how much the buttons, arrow keys and wheel change the value."""
        self._single_step = abs(float(step))

    def setSuffix(self, suffix: str) -> None:
        """Show a fixed, non-editable unit after the number."""
        self._suffix = suffix
        self._refresh_display()

    def setSpecialValueText(self, text: str) -> None:
        """Show ``text`` instead of the number while the value is the minimum."""
        self._special_text = text
        self._refresh_display()

    def setValue(self, value: float) -> None:
        """Set the value, clamped into range; emits ``valueChanged`` if it changed."""
        self._apply_value(value)

    def minimum(self) -> float:
        return self._minimum

    def maximum(self) -> float:
        return self._maximum

    def singleStep(self) -> float:
        return self._single_step

    def suffix(self) -> str:
        return self._suffix

    def specialValueText(self) -> str:
        return self._special_text

    def value(self) -> float:
        return self._value

    def text(self) -> str:
        """What the field shows, including the unit (``"Auto"`` for the special value)."""
        if self._suffix_label.isHidden():
            return self._edit.text()
        return self._edit.text() + self._suffix

    def cleanText(self) -> str:
        """The field's text without the unit."""
        return self._edit.text()

    def sizeHint(self) -> QSize:
        """A compact field: room for the buttons and about eight digits."""
        steppers = 2 * _BUTTON_WIDTH if self._decrease.isVisibleTo(self) else 0
        return QSize(steppers + _TEXT_WIDTH, _FIELD_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        steppers = 2 * _BUTTON_WIDTH if self._decrease.isVisibleTo(self) else 0
        return QSize(steppers + _MIN_TEXT_WIDTH, _FIELD_HEIGHT)

    def setAccessibleName(self, name: str) -> None:
        """Name the field itself for assistive technology, not just its frame."""
        super().setAccessibleName(name)
        self._edit.setAccessibleName(name)

    def setAccessibleDescription(self, description: str) -> None:
        super().setAccessibleDescription(description)
        self._edit.setAccessibleDescription(description)

    # -- value handling -----------------------------------------------------------

    def _emit_value_changed(self, value: float) -> None:
        """Emit the subclass's typed ``valueChanged`` signal."""
        raise NotImplementedError

    def _clamp(self, value: float) -> float:
        return min(max(value, self._minimum), self._maximum)

    def _normalise(self, value: float) -> float:
        return round(self._clamp(value), self._decimals)

    def _apply_value(self, value: float, *, rewrite_text: bool = True) -> None:
        """Store ``value`` (clamped, rounded), refresh the field, emit on change.

        Args:
            value: The new value.
            rewrite_text: Redraw the field's text from the value. Typing passes
                ``False`` so the text under the user's cursor is left alone.
        """
        value = float(value)
        if not math.isfinite(value):
            value = self._value
        new_value = self._normalise(value)
        changed = new_value != self._value
        self._value = new_value
        if rewrite_text:
            self._refresh_display()
        self._refresh_step_buttons()
        if changed:
            self._emit_value_changed(new_value)

    def _step(self, direction: int, factor: int = 1) -> None:
        """Move one (or ``factor``) steps up or down from what is currently shown."""
        parsed = self._parse(self._edit.text())
        base = self._value if parsed is None else parsed
        self._apply_value(base + direction * self._single_step * factor)

    # -- text <-> value -----------------------------------------------------------

    def _format(self, value: float) -> str:
        if self._special_text and value == self._minimum:
            return self._special_text
        return self._locale.toString(value, "f", self._decimals)

    def _parse(self, text: str) -> float | None:
        """Read a number from typed text; ``None`` if it is not a finite number.

        Both ``.`` and ``,`` work as the decimal separator. When both appear,
        the last one is the decimal separator and the other is a thousands
        separator, so ``1,234.5`` and ``1.234,5`` both mean 1234.5.
        """
        text = text.strip()
        if self._special_text and text.casefold() == self._special_text.casefold():
            return self._minimum
        for minus in _MINUS_SIGNS:
            text = text.replace(minus, "-")
        text = text.replace(" ", "").replace(" ", "")
        if "," in text and "." in text:
            decimal = "," if text.rfind(",") > text.rfind(".") else "."
            thousands = "." if decimal == "," else ","
            text = text.replace(thousands, "").replace(decimal, ".")
        else:
            text = text.replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None

    def _refresh_validator(self) -> None:
        """Only let characters through that can still become a number."""
        sign = "[+\\-\u2212]?"
        if not self._allow_fraction or self._decimals == 0:
            pattern = f"^{sign}[0-9]*$"
        else:
            pattern = f"^{sign}[0-9]*([.,][0-9]{{0,{self._decimals}}})?([eE][+\\-]?[0-9]*)?$"
        validator = self._edit.validator()
        if isinstance(validator, QRegularExpressionValidator):
            validator.setRegularExpression(QRegularExpression(pattern))

    def _refresh_display(self) -> None:
        text = self._format(self._value)
        if self._edit.text() != text:
            self._edit.setText(text)
        showing_special = bool(self._special_text) and self._value == self._minimum
        unit = self._suffix.strip()
        self._suffix_label.setText(unit)
        self._suffix_label.setVisible(bool(unit) and not showing_special)
        self._set_invalid(invalid=False)

    def _has_unusable_text(self) -> bool:
        """Whether the field shows text that is not (or is out of range for) the value."""
        parsed = self._parse(self._edit.text())
        return parsed is None or not self._minimum <= parsed <= self._maximum

    def _commit_text(self) -> None:
        """On leaving the field: clamp and reformat the text, or restore the value."""
        parsed = self._parse(self._edit.text())
        if parsed is None:
            self._refresh_display()
            return
        self._apply_value(parsed)

    def _on_text_edited(self, text: str) -> None:
        """Follow typing: a complete number in range becomes the value at once.

        Anything else (half-typed text, a number outside the range) leaves the
        value alone until the field is left; an out-of-range number is flagged.
        """
        parsed = self._parse(text)
        out_of_range = parsed is not None and not self._minimum <= parsed <= self._maximum
        self._set_invalid(invalid=out_of_range)
        if parsed is not None and not out_of_range:
            self._apply_value(parsed, rewrite_text=False)

    def _set_invalid(self, *, invalid: bool) -> None:
        self._set_state_property("invalid", state=invalid)

    def _set_state_property(self, name: str, *, state: bool) -> None:
        """Set a dynamic property the stylesheet keys on, re-polishing on change."""
        if self.property(name) == state:
            return
        self.setProperty(name, state)
        self.style().unpolish(self)
        self.style().polish(self)

    def _refresh_step_buttons(self) -> None:
        self._decrease.setEnabled(self._value > self._minimum)
        self._increase.setEnabled(self._value < self._maximum)

    # -- widgets ------------------------------------------------------------------

    def _make_step_button(self, object_name: str, text: str, name: str, *, direction: int) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setText(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(_REPEAT_DELAY_MS)
        button.setAutoRepeatInterval(_REPEAT_INTERVAL_MS)
        button.setFixedWidth(_BUTTON_WIDTH)
        button.setCursor(Qt.CursorShape.ArrowCursor)
        button.setAccessibleName(name)
        button.setAccessibleDescription("Changes the value by one step. The Up and Down arrow keys in the field do the same.")
        button.clicked.connect(lambda: self._step(direction, self._modifier_factor()))
        button.installEventFilter(self)
        return button

    @staticmethod
    def _modifier_factor() -> int:
        shift = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        return _COARSE_STEP_FACTOR if shift else 1

    # -- events -------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.Wheel and isinstance(event, QWheelEvent) and watched in (self._edit, self._decrease, self._increase):
            return self._handle_wheel(event)
        if watched is self._edit:
            if kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                return self._handle_key(event)
            if kind == QEvent.Type.FocusIn:
                self._set_state_property("focused", state=True)
                # After the click or Tab that gave focus has finished moving the cursor.
                QTimer.singleShot(0, self._select_all)
            elif kind == QEvent.Type.FocusOut:
                self._set_state_property("focused", state=False)
        return super().eventFilter(watched, event)

    def _select_all(self) -> None:
        if shiboken6.isValid(self._edit) and self._edit.hasFocus():
            self._edit.selectAll()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._handle_wheel(event)

    def _handle_wheel(self, event: QWheelEvent) -> bool:
        """Step on the wheel only while focused; otherwise let the panel scroll.

        Returns:
            Whether the event was consumed.
        """
        if not self._edit.hasFocus():
            event.ignore()
            return False
        delta = event.angleDelta().y()
        if delta:
            self._step(1 if delta > 0 else -1, self._modifier_factor())
        event.accept()
        return True

    def _handle_key(self, event: QKeyEvent) -> bool:
        """Arrow, Page and Escape keys; everything else is typed as usual."""
        key = event.key()
        factor = _COARSE_STEP_FACTOR if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        if key == Qt.Key.Key_Up:
            self._step(1, factor)
        elif key == Qt.Key.Key_Down:
            self._step(-1, factor)
        elif key == Qt.Key.Key_PageUp:
            self._step(1, _COARSE_STEP_FACTOR)
        elif key == Qt.Key.Key_PageDown:
            self._step(-1, _COARSE_STEP_FACTOR)
        elif key == Qt.Key.Key_Escape and self._has_unusable_text():
            self._refresh_display()
            self._edit.selectAll()
        else:
            return False
        event.accept()
        return True


class DecimalInput(NumberInput):
    """Floating-point input; the drop-in replacement for ``QDoubleSpinBox``.

    Defaults match ``QDoubleSpinBox``: range 0 to 99.99, two decimals, step 1.
    """

    valueChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None, *, steppers: bool = True):
        super().__init__(parent, steppers=steppers, allow_fraction=True)

    def setDecimals(self, decimals: int) -> None:
        """Set how many digits follow the decimal separator (0 to 15)."""
        self._decimals = min(max(int(decimals), 0), 15)
        self._refresh_validator()
        self._apply_value(self._value)

    def decimals(self) -> int:
        return self._decimals

    def _emit_value_changed(self, value: float) -> None:
        self.valueChanged.emit(value)


class IntegerInput(NumberInput):
    """Whole-number input; the drop-in replacement for ``QSpinBox``.

    Defaults match ``QSpinBox``: range 0 to 99, step 1. ``value()`` and
    ``valueChanged`` carry ``int``.
    """

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None, *, steppers: bool = True):
        super().__init__(parent, steppers=steppers, allow_fraction=False)

    def setRange(self, minimum: float, maximum: float) -> None:
        super().setRange(max(int(minimum), _INT_MIN), min(int(maximum), _INT_MAX))

    def setSingleStep(self, step: float) -> None:
        super().setSingleStep(max(int(abs(step)), 1))

    def value(self) -> int:
        return int(self._value)

    def minimum(self) -> int:
        return int(self._minimum)

    def maximum(self) -> int:
        return int(self._maximum)

    def singleStep(self) -> int:
        return int(self._single_step)

    def _emit_value_changed(self, value: float) -> None:
        self.valueChanged.emit(int(value))
