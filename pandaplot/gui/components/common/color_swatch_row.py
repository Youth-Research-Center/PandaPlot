import re

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QHBoxLayout, QPushButton, QWidget

_HEX_PATTERN = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def is_valid_hex_color(text: str) -> bool:
    return bool(_HEX_PATTERN.match(text))


class ColorSwatchRow(QWidget):
    """Preset color palette row + a '+' swatch opening a full color dialog."""

    colorChanged = Signal(str)

    def __init__(self, palette: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        if not palette:
            raise ValueError("ColorSwatchRow requires a non-empty palette")
        self._palette = palette
        self._current_color = palette[0]
        self._swatch_buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for color in palette:
            button = QPushButton(self)
            button.setFixedSize(18, 18)
            button.clicked.connect(lambda _checked, c=color: self._select_color(c))
            layout.addWidget(button)
            self._swatch_buttons.append(button)

        self._custom_button = QPushButton("+", self)
        self._custom_button.setFixedSize(18, 18)
        self._custom_button.clicked.connect(self._open_color_dialog)
        layout.addWidget(self._custom_button)

        self._refresh_swatch_appearance()

    def currentColor(self) -> str:
        return self._current_color

    def setCurrentColor(self, hex_color: str):
        self._current_color = hex_color
        self._refresh_swatch_appearance()

    def set_tokens(self, tokens: dict):
        self._border_color = tokens.get("border_control", "#DCDEE4")
        self._selected_border = tokens.get("accent", "#4A56C6")
        self._refresh_swatch_appearance()

    def _select_color(self, color: str):
        self._current_color = color
        self._refresh_swatch_appearance()
        self.colorChanged.emit(color)

    def _open_color_dialog(self):
        color = QColorDialog.getColor(QColor(self._current_color), self, "Select Color")
        if color.isValid():
            self._select_color(color.name())

    def _refresh_swatch_appearance(self):
        border = getattr(self, "_border_color", "#DCDEE4")
        selected_border = getattr(self, "_selected_border", "#4A56C6")
        for color, button in zip(self._palette, self._swatch_buttons, strict=True):
            is_selected = color.lower() == self._current_color.lower()
            outline = f"2px solid {selected_border}" if is_selected else f"1px solid {border}"
            button.setStyleSheet(f"background-color: {color}; border: {outline}; border-radius: 4px;")
