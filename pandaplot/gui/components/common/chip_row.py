from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ChipRow(QWidget):
    """Row of rounded selectable chips (series/axis switcher)."""

    currentValueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._values: list[object] = []
        self._buttons: list[QPushButton] = []
        self._current_index: int | None = None

    def setItems(self, items: list[tuple[str, object]]):  # noqa: N802
        previous_value = self.currentValue()

        for button in self._buttons:
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()
        self._values = [value for _, value in items]

        for label, _ in items:
            button = QPushButton(label, self)
            button.setProperty("chip", True)  # noqa: FBT003 -- Qt bound method, positional-only
            button.setFlat(True)
            button.clicked.connect(lambda _checked, b=button: self._select_button(b))
            self._layout.addWidget(button)
            self._buttons.append(button)

        if not self._values:
            self._current_index = None
        elif previous_value in self._values:
            self._current_index = self._values.index(previous_value)
        else:
            self._current_index = 0
        self._refresh_selected_properties()

    def currentValue(self) -> object | None:  # noqa: N802
        if self._current_index is None:
            return None
        return self._values[self._current_index]

    def setCurrentValue(self, value: object):  # noqa: N802
        if value not in self._values:
            return
        self._current_index = self._values.index(value)
        self._refresh_selected_properties()

    def set_tokens(self, tokens: dict):
        for button in self._buttons:
            button.style().unpolish(button)
            button.style().polish(button)

    def _select_button(self, button: QPushButton):
        index = self._buttons.index(button)
        if index == self._current_index:
            return
        self._current_index = index
        self._refresh_selected_properties()
        self.currentValueChanged.emit(self.currentValue())

    def _refresh_selected_properties(self):
        for index, button in enumerate(self._buttons):
            button.setProperty("selected", index == self._current_index)
            button.style().unpolish(button)
            button.style().polish(button)
