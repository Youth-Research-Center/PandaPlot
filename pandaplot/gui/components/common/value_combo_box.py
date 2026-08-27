from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QWidget


class ValueComboBox(QComboBox):
    """QComboBox carrying a (label, value) item list, exposing the same
    currentValue()/setCurrentValue()/currentValueChanged/set_tokens() API
    as SegmentedControl so it's a drop-in replacement wherever a control's
    option count no longer fits a segmented control at 300px panel width.
    """

    currentValueChanged = Signal(object)

    def __init__(
        self,
        items: list[tuple[str, object]],
        icons: list[QIcon] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        if not items:
            raise ValueError("ValueComboBox requires at least one item")
        if icons is not None and len(icons) != len(items):
            raise ValueError("icons must be the same length as items")

        for index, (label, value) in enumerate(items):
            if icons is not None:
                self.addItem(icons[index], label, value)
            else:
                self.addItem(label, value)

        self.currentIndexChanged.connect(self._on_current_index_changed)

    def currentValue(self) -> object:  # noqa: N802
        return self.currentData()

    def setCurrentValue(self, value: object):  # noqa: N802
        index = self.findData(value)
        if index < 0:
            return
        self.blockSignals(True)  # noqa: FBT003 -- Qt bound method, positional-only
        self.setCurrentIndex(index)
        self.blockSignals(False)  # noqa: FBT003 -- Qt bound method, positional-only

    def set_tokens(self, tokens: dict):
        pass  # native Qt combo box styling; no token-driven QSS needed today

    def _on_current_index_changed(self, index: int):
        self.currentValueChanged.emit(self.itemData(index))
