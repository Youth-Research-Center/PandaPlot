"""Dialog for selecting/configuring a table to insert into a note."""

import re
from typing import override

import pandas as pd
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.number_input import IntegerInput
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_display_options import dataset_display_options


def _escape_markdown_table_cell(val: object) -> str:
    """Escape a value for safe embedding in a single Markdown table cell."""
    # pd.isna, not a string comparison: a literal string "nan" is a real
    # cell value, not a missing one (see PandasTableModel.data and
    # tests/gui/test_pandas_table_model.py's test_literal_nan_string_displays_as_nan
    # for the same distinction).
    # Gated on pd.api.types.is_scalar first: pd.isna(val) itself raises
    # "truth value of an array is ambiguous" for a non-scalar cell (a
    # NumPy array; a tuple happens not to trigger it, but object-dtype
    # DataFrame columns can hold arbitrary values) -- is_scalar is the
    # general predicate for what pd.isna can safely evaluate, rather than
    # hand-picking the non-scalar types to exclude.
    if pd.api.types.is_scalar(val) and pd.isna(val):
        return ""
    text = str(val)
    # Backslashes right before a pipe are doubled too: a literal `\|` escaped
    # as `\\|` would read as an escaped backslash plus a column separator.
    text = re.sub(r"(\\*)\|", lambda match: match.group(1) * 2 + "\\|", text)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text


def dataset_to_markdown_table(dataset: Dataset, max_rows: int | None = None) -> str:
    """Convert a Dataset item's DataFrame into a Markdown table string."""
    df = dataset.data
    if df is None or df.empty:
        return ""
    sub_df = df.iloc[:max_rows] if max_rows and len(df) > max_rows else df
    headers = [_escape_markdown_table_cell(col) for col in sub_df.columns]
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    # itertuples keeps each column's own dtype; iterrows would upcast a row
    # mixing int and float columns, rendering 1 as 1.0.
    data_rows = [
        "| " + " | ".join(_escape_markdown_table_cell(val) for val in row) + " |"
        for row in sub_df.itertuples(index=False, name=None)
    ]
    return "\n".join([header_row, separator_row] + data_rows)


def custom_to_markdown_table(rows: int, cols: int, *, include_header: bool = True) -> str:
    """Generate a custom blank Markdown table string.

    A Markdown table requires a header row followed by a delimiter row as
    its first two lines regardless of whether the header labels should be
    visible -- without them, a renderer treats the remaining lines as plain
    text rather than a table. When `include_header` is False the header
    row's cells are just left blank instead of being omitted.
    """
    headers = [f"Header {i+1}" for i in range(cols)] if include_header else [""] * cols
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * cols) + " |",
    ]
    for _r in range(rows):
        cells = ["Cell" for _ in range(cols)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# Most rows of a dataset table shown in the live preview.
_PREVIEW_MAX_ROWS = 50


class NoteTablePickerDialog(PDialog):
    """
    Dialog allowing the user to insert a table into a Markdown note, either
    by converting an existing project Dataset or configuring a custom blank table.
    """

    def __init__(
        self,
        app_context: AppContext,
        project,
        parent: QWidget | None = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.project = project
        self._datasets: list[Dataset] = []
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
        self.dataset_combo = DropDownComboBox()
        display_names = dict(dataset_display_options(self.project)) if self.project is not None else {}
        for ds in self._datasets:
            self.dataset_combo.addItem(f"📊 {display_names.get(ds.id, ds.name)}", ds.id)
        self.dataset_combo.currentIndexChanged.connect(self._update_preview)
        dataset_form.addRow("Select Dataset:", self.dataset_combo)

        row_limit_box = QHBoxLayout()
        self.limit_rows_cb = QCheckBox("Limit rows:")
        self.limit_rows_cb.setChecked(True)
        self.limit_rows_cb.toggled.connect(self._update_preview)

        self.max_rows_spin = IntegerInput()
        self.max_rows_spin.setRange(1, 1000)
        self.max_rows_spin.setValue(20)
        self.max_rows_spin.valueChanged.connect(self._update_preview)
        row_limit_box.addWidget(self.limit_rows_cb)
        row_limit_box.addWidget(self.max_rows_spin)
        dataset_form.addRow(row_limit_box)

        dataset_layout.addLayout(dataset_form)
        self.no_datasets_label: QLabel | None = None
        if not self._datasets:
            palette = self.app_context.get_manager(ThemeManager).get_surface_palette()
            secondary_fg = palette.get("secondary_fg", "#555555")
            self.no_datasets_label = QLabel("No datasets found in current project.")
            self.no_datasets_label.setStyleSheet(f"color: {secondary_fg}; font-style: italic;")
            dataset_layout.addWidget(self.no_datasets_label)

        # Tab 2: Custom Table
        self.custom_tab = QWidget()
        custom_layout = QFormLayout(self.custom_tab)

        self.rows_spin = IntegerInput()
        self.rows_spin.setRange(1, 50)
        self.rows_spin.setValue(3)
        self.rows_spin.valueChanged.connect(self._update_preview)
        custom_layout.addRow("Rows:", self.rows_spin)

        self.cols_spin = IntegerInput()
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

    def _build_markdown(self, *, preview: bool) -> str:
        """The table for the current controls. A preview of a dataset table is
        capped at `_PREVIEW_MAX_ROWS` rows, so a huge dataset doesn't rebuild
        and re-lay-out its whole table on every control change; the inserted
        table is never capped beyond the user's own row limit."""
        if self.tab_widget.currentIndex() == 0:  # From Dataset
            dataset_id = self.dataset_combo.currentData()
            dataset = self.project.find_item(dataset_id) if (self.project and dataset_id) else None
            if not isinstance(dataset, Dataset):
                return ""
            max_rows = self.max_rows_spin.value() if self.limit_rows_cb.isChecked() else None
            if preview and (max_rows is None or max_rows > _PREVIEW_MAX_ROWS):
                return dataset_to_markdown_table(dataset, max_rows=_PREVIEW_MAX_ROWS)
            return dataset_to_markdown_table(dataset, max_rows=max_rows)
        return custom_to_markdown_table(
            self.rows_spin.value(), self.cols_spin.value(), include_header=self.header_cb.isChecked())

    def _update_preview(self) -> None:
        table_md = self._build_markdown(preview=True)
        self.ok_button.setEnabled(bool(table_md) or self.tab_widget.currentIndex() != 0)
        self.preview_edit.setPlainText(table_md)

    def _on_ok_clicked(self) -> None:
        if self.get_markdown_table():
            self.accept()

    def get_markdown_table(self) -> str:
        """Return the generated Markdown table string (the full table, not the
        capped preview)."""
        return self._build_markdown(preview=False)
