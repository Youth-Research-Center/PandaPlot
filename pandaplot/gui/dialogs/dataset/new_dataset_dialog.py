"""Dialog for choosing name, size, and initial fill value of a new empty dataset."""

import math

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_MAX_SPINBOX_VALUE = 2_147_483_647


class NewDatasetDialog(QDialog):
    """
    Dialog for creating a new empty dataset: asks for a name, row count,
    column count, and whether new cells start as NaN or 0.0.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Create New Dataset")
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit("New Dataset")
        form.addRow("Name:", self.name_edit)

        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setMinimum(1)
        self.rows_spinbox.setMaximum(_MAX_SPINBOX_VALUE)
        self.rows_spinbox.setValue(10)
        form.addRow("Rows:", self.rows_spinbox)

        self.columns_spinbox = QSpinBox()
        self.columns_spinbox.setMinimum(1)
        self.columns_spinbox.setMaximum(_MAX_SPINBOX_VALUE)
        self.columns_spinbox.setValue(3)
        form.addRow("Columns:", self.columns_spinbox)

        self.fill_value_combo = QComboBox()
        self.fill_value_combo.addItem("Empty (NaN)")
        self.fill_value_combo.addItem("Zero (0.0)")
        form.addRow("Initial value:", self.fill_value_combo)

        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.name_edit.textChanged.connect(self._update_ok_enabled)
        self._update_ok_enabled()

    def _update_ok_enabled(self):
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(bool(self.name_edit.text().strip()))

    def get_dataset_name(self) -> str:
        return self.name_edit.text().strip()

    def get_rows(self) -> int:
        return self.rows_spinbox.value()

    def get_columns(self) -> int:
        return self.columns_spinbox.value()

    def get_fill_value(self) -> float:
        return math.nan if self.fill_value_combo.currentIndex() == 0 else 0.0
