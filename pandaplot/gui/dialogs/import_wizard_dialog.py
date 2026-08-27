"""
Dataset import wizard.

A single-window wizard that lets the user pick a structured data file
(CSV/TSV, Excel, JSON), tune how it is parsed (delimiter, header, skipped
rows, encoding, worksheet), and preview the resulting table before committing
the import. Sensible defaults are auto-detected so the common case is a
one-click confirm.

The dialog is a thin UI over :mod:`pandaplot.services.data_import`; it produces
an :class:`ImportOptions` plus the chosen file path and dataset name, which the
import command uses to read the full file.
"""

import os
import tempfile
from typing import Optional, override

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProxyStyle,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.data_import import (
    CSV_FORMAT,
    ENCODING_FALLBACKS,
    EXCEL_FORMAT,
    JSON_FORMAT,
    NAMED_DELIMITERS,
    ImportOptions,
    data_importer,
    default_options,
    is_supported,
)
from pandaplot.services.theme.theme_manager import ThemeManager

# Rows read for the live preview. Kept small so previewing stays instant even
# for large files; the full file is read later during the actual import.
PREVIEW_ROWS = 100

_AUTO_DETECT = "Auto-detect"
_CUSTOM = "Custom…"

_FORMAT_LABELS = {
    CSV_FORMAT: "Delimited text (CSV / TSV)",
    EXCEL_FORMAT: "Excel workbook",
    JSON_FORMAT: "JSON",
}

# All-files first so the wizard can open anything; specific filters help users
# narrow down in the native dialog.
_FILE_FILTER = (
    "Data files (*.csv *.tsv *.txt *.tab *.dat *.xlsx *.xls *.xlsm *.json);;"
    "Delimited text (*.csv *.tsv *.txt *.tab *.dat);;"
    "Excel files (*.xlsx *.xls *.xlsm);;"
    "JSON files (*.json);;"
    "All files (*.*)"
)


def _caret_icon_path(color_hex: str) -> str:
    """
    Return a filesystem path to a small downward-caret PNG in ``color_hex``,
    generating and caching it on first use. Qt stylesheets can only point
    ``::down-arrow`` at an image URL, so we render one on demand rather than
    ship a per-theme asset. The path uses forward slashes for QSS on all
    platforms.
    """
    key = color_hex.lstrip("#")
    path = os.path.join(tempfile.gettempdir(), f"pandaplot_caret_{key}.png")
    if not os.path.exists(path):
        size = 12
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color_hex))
        painter.drawPolygon(QPolygonF([QPointF(2.5, 4.5), QPointF(9.5, 4.5), QPointF(6.0, 8.5)]))
        painter.end()
        pixmap.save(path)
    return path.replace(os.sep, "/")


class _DropDownComboStyle(QProxyStyle):
    """
    Forces combo boxes to open as a dropdown list attached below the field,
    instead of macOS's native combo-box style, which pops the menu up
    centered over the current item (like an NSPopUpButton). That default
    reads as broken here since the wizard's combos are plain lists, not
    "current selection" menus.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


class ImportWizardDialog(PDialog):
    """Interactive wizard for importing a structured data file as a dataset."""

    def __init__(self, app_context: AppContext, parent=None, initial_file_path: Optional[str] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.file_path: Optional[str] = None
        # Guard against option-change handlers firing while we programmatically
        # repopulate widgets after loading a file.
        self._loading = False
        # Reverse map (separator char -> wizard label) for reflecting a detected
        # delimiter back onto the combo box.
        self._delimiter_by_value = {value: label for label, value in NAMED_DELIMITERS.items()}
        # Shared style forcing combos to drop down below the field rather than
        # macOS's centered popup-menu behaviour; kept as an attribute since
        # QWidget.setStyle() does not take ownership of the QStyle instance.
        self._combo_style = _DropDownComboStyle()

        self._initialize()

        if initial_file_path:
            self._load_file(initial_file_path)
        else:
            self._update_controls_enabled()
            self._set_status("Choose a file to begin.", error=False)

    # ------------------------------------------------------------------ UI setup

    @override
    def _init_ui(self):
        self.setWindowTitle("📥 Import Dataset")
        self.setModal(True)
        self.resize(820, 620)
        self.setMinimumSize(720, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._build_file_row(layout)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._build_options_panel(), 0)
        body.addWidget(self._build_preview_panel(), 1)
        layout.addLayout(body, 1)

        self._build_buttons(layout)

    def _build_file_row(self, parent_layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("File:"))
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.file_path_label, 1)

        self.browse_button = PButton("Browse…", role="secondary", on_click=self._browse_file)
        row.addWidget(self.browse_button, 0)

        parent_layout.addLayout(row)

    def _build_options_panel(self) -> QWidget:
        group = QGroupBox("Parse options")
        form = QFormLayout(group)
        form.setSpacing(10)

        # Format
        self.format_combo = QComboBox()
        self.format_combo.setStyle(self._combo_style)
        for fmt, label in _FORMAT_LABELS.items():
            self.format_combo.addItem(label, fmt)
        self.format_combo.currentIndexChanged.connect(self._on_option_changed)
        form.addRow("Format:", self.format_combo)

        # Delimiter (CSV only)
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.setStyle(self._combo_style)
        self.delimiter_combo.addItem(_AUTO_DETECT)
        for label in NAMED_DELIMITERS:
            self.delimiter_combo.addItem(label)
        self.delimiter_combo.addItem(_CUSTOM)
        self.delimiter_combo.currentIndexChanged.connect(self._on_delimiter_changed)
        form.addRow("Delimiter:", self.delimiter_combo)

        self.custom_delimiter_edit = QLineEdit()
        self.custom_delimiter_edit.setMaxLength(8)
        self.custom_delimiter_edit.setPlaceholderText("e.g. ; or |")
        self.custom_delimiter_edit.textChanged.connect(self._on_option_changed)
        form.addRow("Custom delimiter:", self.custom_delimiter_edit)

        # Header
        self.header_checkbox = QCheckBox("First row contains column names")
        self.header_checkbox.setChecked(True)
        self.header_checkbox.toggled.connect(self._on_option_changed)
        form.addRow("Header:", self.header_checkbox)

        # Skip rows
        self.skip_rows_spin = QSpinBox()
        self.skip_rows_spin.setRange(0, 100000)
        self.skip_rows_spin.valueChanged.connect(self._on_option_changed)
        form.addRow("Skip top rows:", self.skip_rows_spin)

        # Encoding (CSV / JSON)
        self.encoding_combo = QComboBox()
        self.encoding_combo.setStyle(self._combo_style)
        for encoding in ENCODING_FALLBACKS:
            self.encoding_combo.addItem(encoding)
        self.encoding_combo.currentIndexChanged.connect(self._on_option_changed)
        form.addRow("Encoding:", self.encoding_combo)

        # Worksheets (Excel only). A checkable list so multiple sheets can be
        # imported at once, each becoming its own dataset. The preview follows
        # the first checked sheet.
        self.sheet_list = QListWidget()
        self.sheet_list.setMaximumHeight(110)
        self.sheet_list.itemChanged.connect(self._on_option_changed)
        form.addRow("Worksheets:", self.sheet_list)

        # Dataset name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Dataset name")
        form.addRow("Name:", self.name_edit)

        group.setMaximumWidth(360)
        return group

    def _build_preview_panel(self) -> QWidget:
        group = QGroupBox("Preview")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.verticalHeader().setVisible(True)
        layout.addWidget(self.preview_table, 1)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label, 0)

        return group

    def _build_buttons(self, parent_layout: QVBoxLayout):
        self.button_frame = QFrame()
        row = QHBoxLayout(self.button_frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        row.addWidget(self.cancel_button)

        self.import_button = PButton("Import", role="primary", on_click=self.accept)
        self.import_button.setDefault(True)
        row.addWidget(self.import_button)

        parent_layout.addWidget(self.button_frame)

    # -------------------------------------------------------------- file loading

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Data File", "", _FILE_FILTER)
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        """Detect defaults for the given file and populate the option widgets."""
        if not os.path.exists(path):
            self._set_status(f"File does not exist: {path}", error=True)
            return
        if not is_supported(path):
            self._set_status(f"Unsupported file type: {os.path.splitext(path)[1] or '(none)'}", error=True)
            return

        self.file_path = path
        self.file_path_label.setText(path)
        if not self.name_edit.text().strip():
            self.name_edit.setText(os.path.splitext(os.path.basename(path))[0])

        try:
            options = default_options(path)
        except Exception as error:  # noqa: BLE001 - surfaced to the user below
            self.logger.warning("Failed to detect import defaults for %s: %s", path, error)
            self._set_status(f"Could not inspect file: {error}", error=True)
            return

        self._apply_options_to_widgets(options)
        self._refresh_preview()

    def _apply_options_to_widgets(self, options: ImportOptions):
        """Reflect detected/default options onto the widgets without recursion."""
        self._loading = True
        try:
            self._select_combo_data(self.format_combo, options.file_format)
            self.header_checkbox.setChecked(options.has_header)
            self.skip_rows_spin.setValue(options.skip_rows)
            self._select_combo_text(self.encoding_combo, options.encoding)

            # Delimiter: reflect the detected char onto the combo/custom field.
            if options.file_format == CSV_FORMAT:
                label = self._delimiter_by_value.get(options.delimiter)
                if label is not None:
                    self._select_combo_text(self.delimiter_combo, label)
                    self.custom_delimiter_edit.clear()
                else:
                    self._select_combo_text(self.delimiter_combo, _CUSTOM)
                    self.custom_delimiter_edit.setText(options.delimiter)

            # Worksheets for Excel: list every sheet, checked by default so a
            # plain confirm imports the whole workbook.
            self.sheet_list.clear()
            if options.file_format == EXCEL_FORMAT and self.file_path:
                try:
                    for sheet in data_importer.list_excel_sheets(self.file_path):
                        item = QListWidgetItem(str(sheet))
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(Qt.CheckState.Checked)
                        self.sheet_list.addItem(item)
                except Exception as error:  # noqa: BLE001
                    self.logger.warning("Failed to list Excel sheets: %s", error)
        finally:
            self._loading = False

        self._update_controls_enabled()

    # ---------------------------------------------------------------- option read

    def _current_options(self) -> ImportOptions:
        """Build an ImportOptions from the current widget state."""
        file_format = self.format_combo.currentData()
        return ImportOptions(
            file_format=file_format,
            delimiter=self._resolve_delimiter(),
            has_header=self.header_checkbox.isChecked(),
            skip_rows=self.skip_rows_spin.value(),
            encoding=self.encoding_combo.currentText(),
            # Preview follows the first checked sheet; the full set is exposed
            # separately via get_selected_sheets().
            sheet_name=self._first_checked_sheet(),
        )

    def _first_checked_sheet(self) -> "str | int":
        for sheet in self.get_selected_sheets():
            return sheet
        return 0

    def get_selected_sheets(self) -> list:
        """Return the checked worksheet names, in workbook order (Excel only)."""
        return [
            self.sheet_list.item(row).text()
            for row in range(self.sheet_list.count())
            if self.sheet_list.item(row).checkState() == Qt.CheckState.Checked
        ]

    def _resolve_delimiter(self) -> str:
        choice = self.delimiter_combo.currentText()
        if choice == _AUTO_DETECT:
            if self.file_path:
                return data_importer.sniff_delimiter(self.file_path, self.encoding_combo.currentText())
            return ","
        if choice == _CUSTOM:
            text = self.custom_delimiter_edit.text()
            # An empty custom delimiter is meaningless; fall back to a comma.
            return text if text else ","
        return NAMED_DELIMITERS.get(choice, ",")

    # -------------------------------------------------------------- event handlers

    def _on_option_changed(self, *_):
        if self._loading:
            return
        self._update_controls_enabled()
        self._refresh_preview()

    def _on_delimiter_changed(self, *_):
        if self._loading:
            return
        self._update_controls_enabled()
        self._refresh_preview()

    def _update_controls_enabled(self):
        """Enable only the option widgets relevant to the selected format."""
        has_file = self.file_path is not None
        file_format = self.format_combo.currentData()

        is_csv = file_format == CSV_FORMAT
        is_excel = file_format == EXCEL_FORMAT
        is_json = file_format == JSON_FORMAT

        self.format_combo.setEnabled(has_file)
        self.delimiter_combo.setEnabled(has_file and is_csv)
        self.custom_delimiter_edit.setEnabled(has_file and is_csv and self.delimiter_combo.currentText() == _CUSTOM)
        self.header_checkbox.setEnabled(has_file and (is_csv or is_excel))
        self.skip_rows_spin.setEnabled(has_file and (is_csv or is_excel))
        self.encoding_combo.setEnabled(has_file and (is_csv or is_json))
        self.sheet_list.setEnabled(has_file and is_excel and self.sheet_list.count() > 0)
        self.name_edit.setEnabled(has_file)

    # -------------------------------------------------------------------- preview

    def _refresh_preview(self):
        """Read a small preview with the current options and render the table."""
        if not self.file_path:
            self._set_import_enabled(enabled=False)
            return

        # For Excel, at least one worksheet must be checked to import anything.
        if self.format_combo.currentData() == EXCEL_FORMAT and self.sheet_list.count() and not self.get_selected_sheets():
            self.preview_table.clearContents()
            self.preview_table.setRowCount(0)
            self._set_status("Select at least one worksheet to import.", error=True)
            self._set_import_enabled(enabled=False)
            return

        try:
            options = self._current_options()
            df = data_importer.read_dataframe(self.file_path, options, nrows=PREVIEW_ROWS)
        except Exception as error:  # noqa: BLE001 - any parse failure is user-facing
            self.logger.info("Preview failed for %s: %s", self.file_path, error)
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            self._set_status(f"Could not parse with these options: {error}", error=True)
            self._set_import_enabled(enabled=False)
            return

        self._populate_table(df)

        if df.shape[1] == 0:
            self._set_status("No columns found. Adjust the options above.", error=True)
            self._set_import_enabled(enabled=False)
            return

        if df.empty:
            self._set_status("File parsed but contains no data rows.", error=True)
            self._set_import_enabled(enabled=False)
            return

        shown = df.shape[0]
        more = " (first rows shown)" if shown >= PREVIEW_ROWS else ""
        self._set_status(f"Preview: {shown} row(s){more} · {df.shape[1]} column(s).", error=False)
        self._set_import_enabled(enabled=True)

    def _populate_table(self, df):
        self.preview_table.clear()
        self.preview_table.setColumnCount(df.shape[1])
        self.preview_table.setRowCount(df.shape[0])
        self.preview_table.setHorizontalHeaderLabels([str(col) for col in df.columns])

        for row in range(df.shape[0]):
            for col in range(df.shape[1]):
                value = df.iat[row, col]
                text = "" if value is None or (isinstance(value, float) and value != value) else str(value)
                self.preview_table.setItem(row, col, QTableWidgetItem(text))

    def _set_status(self, message: str, *, error: bool):
        self.status_label.setText(message)
        self._status_is_error = error
        # Colour is applied in _apply_theme; refresh it here for live updates.
        self._style_status()

    def _set_import_enabled(self, *, enabled: bool):
        self.import_button.setEnabled(enabled)

    # ---------------------------------------------------------------- public API

    def get_file_path(self) -> Optional[str]:
        return self.file_path

    def get_import_options(self) -> ImportOptions:
        return self._current_options()

    def get_dataset_name(self) -> str:
        name = self.name_edit.text().strip()
        if name:
            return name
        if self.file_path:
            return os.path.splitext(os.path.basename(self.file_path))[0]
        return "Imported Dataset"

    @override
    def accept(self):
        # Belt-and-braces: never accept without a valid, previewable file.
        if not self.file_path or not self.import_button.isEnabled():
            return
        super().accept()

    # ------------------------------------------------------------------ theming

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")
        accent = palette.get("accent", "#4A90E2")
        # Inputs sit one shade off the card so fields read as distinct wells.
        input_bg = palette.get("card_hover", "#e9ecef")
        self._secondary_fg = secondary_fg
        # Styling ::drop-down suppresses Qt's native arrow, so supply our own
        # caret drawn in the theme's foreground colour.
        arrow = _caret_icon_path(base_fg)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {card_border};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {secondary_fg};
            }}
            QLabel, QCheckBox {{
                color: {base_fg};
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
                color: {base_fg};
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {accent};
            }}
            QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
                border-color: {accent};
            }}
            QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
                color: {secondary_fg};
                background-color: {card_bg};
                border-color: {card_border};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border: none;
                border-left: 1px solid {card_border};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                image: url({arrow});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
                outline: none;
                padding: 2px;
                selection-background-color: {accent};
                selection-color: white;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 22px;
                padding: 2px 6px;
                border-radius: 3px;
            }}
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QTableWidget {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                gridline-color: {card_border};
                color: {base_fg};
            }}
            QHeaderView::section {{
                background-color: {card_border};
                color: {base_fg};
                padding: 4px;
                border: none;
            }}
            QListWidget {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                color: {base_fg};
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 4px;
            }}
            QListWidget::item:selected {{
                background-color: {accent};
                color: white;
            }}
        """)

        self._style_status()

    def _style_status(self):
        if not hasattr(self, "status_label"):
            return
        error = getattr(self, "_status_is_error", False)
        color = "#d9534f" if error else getattr(self, "_secondary_fg", "#555555")
        self.status_label.setStyleSheet(f"color: {color};")

    # ------------------------------------------------------------- combo helpers

    @staticmethod
    def _select_combo_data(combo: QComboBox, data):
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _select_combo_text(combo: QComboBox, text: str):
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
