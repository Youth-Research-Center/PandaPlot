from __future__ import annotations

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.slider_with_spinbox import SliderWithSpinbox
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot_storybook.registry import (
    BoolControl,
    ChoiceControl,
    Control,
    FloatControl,
    IntControl,
    TextControl,
)

NO_CONTROLS_MESSAGE = "No configurable properties for this component."


class ControlsPanel(QWidget):
    """Renders one labeled editor per Control and reports the live values dict.

    When `controls` is empty, shows a small muted empty-state label instead
    of an empty form.
    """

    valuesChanged = Signal(dict)

    def __init__(
        self,
        controls: list[Control],
        tokens: dict | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._values: dict[str, object] = {control.name: control.default for control in controls}
        if not controls:
            muted = (tokens or {}).get("text_muted", "#6B7280")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            empty_label = QLabel(NO_CONTROLS_MESSAGE)
            empty_label.setObjectName("controlsEmptyState")
            empty_label.setWordWrap(True)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            empty_label.setStyleSheet(f"font-style: italic; color: {muted};")
            layout.addWidget(empty_label)
            return
        layout = QFormLayout(self)
        for control in controls:
            layout.addRow(control.name.replace("_", " ").title(), self._build_editor(control))

    def values(self) -> dict[str, object]:
        return dict(self._values)

    def _build_editor(self, control: Control) -> QWidget:
        if isinstance(control, TextControl):
            editor = QLineEdit(control.default)
            editor.textChanged.connect(lambda text: self._set(control.name, text))
            return editor
        if isinstance(control, BoolControl):
            editor = QCheckBox()
            editor.setChecked(control.default)
            editor.toggled.connect(lambda checked: self._set(control.name, checked))
            return editor
        if isinstance(control, ChoiceControl):
            editor = DropDownComboBox()
            editor.addItems(control.options)
            editor.setCurrentText(control.default)
            editor.currentTextChanged.connect(lambda text: self._set(control.name, text))
            return editor
        if isinstance(control, IntControl):
            editor = QSpinBox()
            editor.setRange(control.minimum, control.maximum)
            editor.setValue(control.default)
            editor.valueChanged.connect(lambda value: self._set(control.name, value))
            return editor
        if isinstance(control, FloatControl):
            editor = SliderWithSpinbox(control.minimum, control.maximum)
            editor.setValue(control.default)
            editor.valueChanged.connect(lambda value: self._set(control.name, value))
            return editor
        raise TypeError(f"Unsupported control type: {type(control)!r}")

    def _set(self, name: str, value: object) -> None:
        self._values[name] = value
        self.valuesChanged.emit(self.values())


__all__ = ["NO_CONTROLS_MESSAGE", "ControlsPanel"]
