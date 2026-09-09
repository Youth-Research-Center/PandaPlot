"""Dialog for selecting/configuring a table to insert into a note."""

from typing import List, Optional, override

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


def _escape_markdown_table_cell(val: object) -> str:
    """Escape a value for safe embedding in a single Markdown table cell."""
    if val is None or str(val) == "nan":
        return ""
    text = str(val)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text


def dataset_to_markdown_table(dataset: Dataset, max_rows: Optional[int] = None) -> str:
    """Convert a Dataset item's DataFrame into a Markdown table string."""
    df = dataset.df
    if df is None or df.empty:
        return ""
    sub_df = df.iloc[:max_rows] if max_rows and len(df) > max_rows else df
    headers = [_escape_markdown_table_cell(col) for col in sub_df.columns]
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = []
    for _, row in sub_df.iterrows():
        data_rows.append(
            "| " + " | ".join(_escape_markdown_table_cell(val) for val in row) + " |"
        )
    return "\n".join([header_row, separator_row] + data_rows)


def custom_to_markdown_table(rows: int, cols: int, include_header: bool = True) -> str:  # noqa: FBT001, FBT002
    """Generate a custom blank Markdown table string."""
    lines = []
    if include_header:
        headers = [f"Header {i+1}" for i in range(cols)]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * cols) + " |")
    for _r in range(rows):
        cells = ["Cell" for _ in range(cols)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


class NoteTablePickerDialog(PDialog):
    """
    Dialog allowing the user to insert a table into a Markdown note, either
    by converting an existing project Dataset or configuring a custom blank table.
    """

    def __init__(
        self,
        app_context: AppContext,
        project,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.project = project
        self._markdown_result: str = ""
        self._datasets: List[Dataset] = []
        if self.project is not None:
            self._datasets = [item for item in self.project.get_all_items() if isinstance(item, Dataset)]

        self._initialize()
        self._update_preview()

    @override
    def _init_ui(self):
        self.setWindowTitle("Insert Table into Note")
        self.resize(450, 420)
        layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()

        # Tab 1: From Dataset
        self.dataset_tab = QWidget()
        dataset_layout = QVBoxLayout(self.dataset_tab)

        dataset_form = QFormLayout()
        self.dataset_combo = QComboBox()
        for ds in self._datasets:
            self.dataset_combo.addItem(f"📊 {ds.name}", ds.id)
        self.dataset_combo.currentIndexChanged.connect(self._update_preview)
        dataset_form.addRow("Select Dataset:", self.dataset_combo)

        row_limit_box = QHBoxLayout()
        self.limit_rows_cb = QCheckBox("Limit rows:")
        self.limit_rows_cb.setChecked(True)
        self.limit_rows_cb.toggled.connect(self._update_preview)

        self.max_rows_spin = QSpinBox()
        self.max_rows_spin.setRange(1, 1000)
        self.max_rows_spin.setValue(20)
        self.max_rows_spin.valueChanged.connect(self._update_preview)
        row_limit_box.addWidget(self.limit_rows_cb)
        row_limit_box.addWidget(self.max_rows_spin)
        dataset_form.addRow(row_limit_box)

        dataset_layout.addLayout(dataset_form)
        if not self._datasets:
            no_ds_lbl = QLabel("No datasets found in current project.")
            no_ds_lbl.setStyleSheet("color: #777; font-style: italic;")
            dataset_layout.addWidget(no_ds_lbl)

        # Tab 2: Custom Table
        self.custom_tab = QWidget()
        custom_layout = QFormLayout(self.custom_tab)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(3)
        self.rows_spin.valueChanged.connect(self._update_preview)
        custom_layout.addRow("Rows:", self.rows_spin)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 20)
        self.cols_spin.setValue(3)
        self.cols_spin.valueChanged.connect(self._update_preview)
        custom_layout.addRow("Columns:", self.cols_spin)

        self.header_cb = QCheckBox("Include header row")
        self.header_cb.setChecked(True)
        self.header_cb.toggled.connect(self._update_preview)
        custom_layout.addRow(self.header_cb)

        self.tab_widget.addTab(self.dataset_tab, "From Dataset")
        self.tab_widget.addTab(self.custom_tab, "Custom Table")
        self.tab_widget.currentChanged.connect(self._update_preview)
        layout.addWidget(self.tab_widget)

        # Live Preview
        preview_label = QLabel("Markdown Preview:")
        layout.addWidget(preview_label)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setMaximumHeight(130)
        layout.addWidget(self.preview_edit)

        # Buttons
        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("Insert Table", role="primary", on_click=self._on_ok_clicked)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def _update_preview(self) -> None:
        if self.tab_widget.currentIndex() == 0:  # From Dataset
            dataset_id = self.dataset_combo.currentData()
            dataset = self.project.find_item(dataset_id) if (self.project and dataset_id) else None
            if dataset and isinstance(dataset, Dataset):
                max_rows = self.max_rows_spin.value() if self.limit_rows_cb.isChecked() else None
                table_md = dataset_to_markdown_table(dataset, max_rows=max_rows)
            else:
                table_md = ""
            self.ok_button.setEnabled(bool(table_md))
        else:  # Custom Table
            rows = self.rows_spin.value()
            cols = self.cols_spin.value()
            include_header = self.header_cb.isChecked()
            table_md = custom_to_markdown_table(rows, cols, include_header=include_header)
            self.ok_button.setEnabled(True)

        self._markdown_result = table_md
        self.preview_edit.setPlainText(table_md)

    def _on_ok_clicked(self) -> None:
        self._update_preview()
        if self._markdown_result:
            self.accept()

    def get_markdown_table(self) -> str:
        """Return the generated Markdown table string."""
        return self._markdown_result
