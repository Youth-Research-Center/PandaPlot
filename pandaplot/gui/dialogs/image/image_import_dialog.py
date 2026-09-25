"""
Import dialog for adding images to an image gallery, from local files or a
single web URL, with a choice between copying the bytes into the project or
storing only an external reference.
"""

from typing import override

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.state.app_context import AppContext

_IMAGE_FILE_FILTER = "Image files (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All files (*.*)"


class ImageImportDialog(PDialog):
    """Dialog for selecting one or more images (files or a URL) to import into a gallery."""

    def __init__(self, app_context: AppContext, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self._selected_files: list[str] = []
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle("Import Images")
        layout = QVBoxLayout(self)

        self.files_radio = QRadioButton("From files")
        self.url_radio = QRadioButton("From URL")
        self.files_radio.setChecked(True)
        source_mode_group = QButtonGroup(self)
        source_mode_group.addButton(self.files_radio)
        source_mode_group.addButton(self.url_radio)
        self.source_mode_group = source_mode_group

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.files_radio)
        mode_row.addWidget(self.url_radio)
        layout.addLayout(mode_row)

        self.browse_button = PButton("Browse...", on_click=self._browse_files)
        self.selected_files_label = QLabel("No files selected")
        files_row = QHBoxLayout()
        files_row.addWidget(self.browse_button)
        files_row.addWidget(self.selected_files_label)
        layout.addLayout(files_row)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/image.png")
        layout.addWidget(self.url_edit)

        self.copy_checkbox = QCheckBox("Copy into project")
        self.copy_checkbox.setChecked(True)
        layout.addWidget(self.copy_checkbox)

        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.import_button = PButton("Import", role="primary", on_click=self.accept, enabled=False)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.import_button)
        layout.addLayout(button_row)

        self.url_edit.textChanged.connect(self._refresh_import_enabled)
        self.files_radio.toggled.connect(self._refresh_import_enabled)
        self.url_radio.toggled.connect(self._refresh_import_enabled)

    @override
    def _apply_theme(self):
        pass

    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", _IMAGE_FILE_FILTER)
        if paths:
            self._set_selected_files(paths)

    def _set_selected_files(self, paths: list[str]):
        """Test/production hook to set the selected local files without a real file dialog."""
        self._selected_files = paths
        self.selected_files_label.setText(f"{len(paths)} file(s) selected" if paths else "No files selected")
        self._refresh_import_enabled()

    def _refresh_import_enabled(self):
        self.import_button.setEnabled(bool(self.get_sources()))

    def get_sources(self) -> list[str]:
        """Return the local file paths (files mode) or a single-item list with the URL (URL mode)."""
        if self.url_radio.isChecked():
            url = self.url_edit.text().strip()
            return [url] if url else []
        return list(self._selected_files)

    def get_copy_into_project(self) -> bool:
        """Whether images should be copied into the project (vs. stored as an external reference)."""
        return self.copy_checkbox.isChecked()
