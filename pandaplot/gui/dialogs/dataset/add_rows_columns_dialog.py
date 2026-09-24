"""Dialog for growing an existing dataset to a desired table size."""

from typing import NamedTuple

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox

_MAX_SPINBOX_VALUE = 2_147_483_647
# Dataset combo sizing: characters of width it always reserves, and the width
# past which a long dataset name is elided rather than widening the dialog.
_MIN_COMBO_CHARS = 24
_MAX_COMBO_WIDTH = 360


class DatasetSize(NamedTuple):
    """A dataset the dialog can target, with its current table size."""
    id: str
    name: str
    rows: int
    columns: int


class AddRowsColumnsDialog(QDialog):
    """
    Dialog for adding rows and columns to an existing dataset.

    The user picks a target dataset and the table size they want; the rows and
    columns needed to reach that size are appended. Sizes are add-only: each
    spinbox has the dataset's current count as its minimum, so the dialog can
    never ask for data to be dropped.
    """

    def __init__(self, datasets: list[DatasetSize],
                 initial_dataset_id: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Rows / Columns")
        self.setModal(True)

        self._datasets = datasets
        self._setup_ui()

        index = self.dataset_combo.findData(initial_dataset_id)
        self.dataset_combo.setCurrentIndex(max(index, 0))
        # setCurrentIndex only fires when the index actually changes, so seed
        # the size widgets from the selection explicitly.
        self._on_dataset_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.dataset_combo = DropDownComboBox()
        for dataset in self._datasets:
            self.dataset_combo.addItem(dataset.name, dataset.id)
        # Grow to fit the longest dataset name instead of clipping it to the
        # combo's minimum width, with a floor so short names still get a
        # comfortable field and a ceiling so one long name can't stretch the
        # dialog across the screen (Qt elides past that).
        self.dataset_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.dataset_combo.setMinimumContentsLength(_MIN_COMBO_CHARS)
        self.dataset_combo.setMaximumWidth(_MAX_COMBO_WIDTH)
        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        form.addRow("Dataset:", self.dataset_combo)

        self.current_size_label = QLabel()
        form.addRow("Current size:", self.current_size_label)

        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setMaximum(_MAX_SPINBOX_VALUE)
        self.rows_spinbox.valueChanged.connect(self._update_ok_enabled)
        form.addRow("Total rows:", self.rows_spinbox)

        self.columns_spinbox = QSpinBox()
        self.columns_spinbox.setMaximum(_MAX_SPINBOX_VALUE)
        self.columns_spinbox.valueChanged.connect(self._update_ok_enabled)
        form.addRow("Total columns:", self.columns_spinbox)

        layout.addLayout(form)

        hint = QLabel("New rows and columns are appended to the end of the table.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _selected_dataset(self) -> DatasetSize | None:
        dataset_id = self.dataset_combo.currentData()
        for dataset in self._datasets:
            if dataset.id == dataset_id:
                return dataset
        return None

    def _on_dataset_changed(self):
        """Re-anchor the size spinboxes on the newly selected dataset."""
        dataset = self._selected_dataset()
        if dataset is None:
            self.current_size_label.setText("-")
            self._update_ok_enabled()
            return

        self.current_size_label.setText(
            f"{dataset.rows} rows x {dataset.columns} columns")
        # A name past _MAX_COMBO_WIDTH is clipped in the closed combo; the
        # tooltip keeps it readable without widening the dialog.
        self.dataset_combo.setToolTip(dataset.name)

        # Minimum first, then value: a value below the new minimum would be
        # clamped, and lowering the minimum afterwards would not restore it.
        self.rows_spinbox.setMinimum(dataset.rows)
        self.rows_spinbox.setValue(dataset.rows)
        self.columns_spinbox.setMinimum(dataset.columns)
        self.columns_spinbox.setValue(dataset.columns)

        self._update_ok_enabled()

    def _update_ok_enabled(self):
        """Nothing to add while the requested size still matches the current one."""
        dataset = self._selected_dataset()
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if dataset is None:
            ok_button.setEnabled(False)
            return
        grows = (self.rows_spinbox.value() > dataset.rows
                 or self.columns_spinbox.value() > dataset.columns)
        ok_button.setEnabled(grows)

    def get_dataset_id(self) -> str | None:
        return self.dataset_combo.currentData()

    def get_target_rows(self) -> int:
        return self.rows_spinbox.value()

    def get_target_columns(self) -> int:
        return self.columns_spinbox.value()
