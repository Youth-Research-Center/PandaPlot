from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from pandaplot.gui.components.common.p_button import PButton


def format_status_text(*, is_modified: bool, change_count: int) -> str:
    if not is_modified or change_count <= 0:
        return "No changes"
    if change_count == 1:
        return "Modified"
    return f"{change_count} unsaved changes"


class DirtyFooter(QWidget):
    """Sticky footer: status text (amber dot when modified) + Revert/Apply."""

    revertClicked = Signal()
    applyClicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._status_label = QLabel("No changes", self)
        self._revert_button = PButton(
            "Revert", role="secondary", on_click=self.revertClicked, enabled=False, parent=self
        )
        self._apply_button = PButton(
            "Apply", role="primary", on_click=self.applyClicked, enabled=False, parent=self
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._status_label, stretch=1)
        layout.addWidget(self._revert_button)
        layout.addWidget(self._apply_button)

    def setModified(self, *, is_modified: bool, change_count: int = 0):  # noqa: N802
        self._status_label.setText(
            format_status_text(is_modified=is_modified, change_count=change_count)
        )
        is_effectively_modified = is_modified and change_count > 0
        self._revert_button.setEnabled(is_effectively_modified)
        self._apply_button.setEnabled(is_effectively_modified)

    def set_tokens(self, tokens: dict):
        modified_color = tokens.get("status_modified_text", "#B06A00")
        muted_color = tokens.get("text_hint", "#9AA0AB")
        is_modified = self._apply_button.isEnabled()
        self._status_label.setStyleSheet(
            f"color: {modified_color if is_modified else muted_color};"
        )
        self._apply_button.style().unpolish(self._apply_button)
        self._apply_button.style().polish(self._apply_button)
