from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    """Bordered group of mutually-exclusive text/icon cells."""

    currentValueChanged = Signal(object)

    def __init__(self, items: list[tuple[str, object]], parent: QWidget | None = None):
        super().__init__(parent)
        if not items:
            raise ValueError("SegmentedControl requires at least one item")
        self._values = [value for _, value in items]
        self._buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        for label, _ in items:
            button = QPushButton(label, self)
            button.setProperty("segment", True)  # noqa: FBT003 -- Qt bound method, positional-only
            button.setFlat(True)
            button.clicked.connect(lambda _checked, b=button: self._select_button(b))
            layout.addWidget(button)
            self._buttons.append(button)

        self._current_index = 0
        self._refresh_selected_properties()

    def currentValue(self) -> object:  # noqa: N802
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
