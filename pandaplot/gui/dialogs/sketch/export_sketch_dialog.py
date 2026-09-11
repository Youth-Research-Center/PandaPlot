from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.sketch_exporter import SketchExporter


class ExportSketchDialog(QDialog):
    """Dialog for exporting a Sketch to raster or vector image formats."""

    def __init__(self, canvas: SketchCanvas, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.canvas: SketchCanvas = canvas
        self.setWindowTitle("Export Sketch")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "SVG", "PDF"])
        form_layout.addRow("Format:", self.format_combo)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        form_layout.addRow("Resolution:", self.dpi_spin)

        self.transparent_cb = QCheckBox("Transparent Background")
        form_layout.addRow("", self.transparent_cb)

        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_btn)
        form_layout.addRow("Export Path:", file_layout)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._do_export)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _browse_file(self) -> None:
        fmt = self.format_combo.currentText().lower()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Sketch Image", f"{self.canvas.sketch.name}.{fmt}", f"{fmt.upper()} Files (*.{fmt})"
        )
        if filepath:
            self.file_path_edit.setText(filepath)

    def _do_export(self) -> None:
        filepath = self.file_path_edit.text().strip()
        if not filepath:
            self._browse_file()
            filepath = self.file_path_edit.text().strip()
            if not filepath:
                return

        fmt = self.format_combo.currentText()
        dpi = self.dpi_spin.value()
        transparent = self.transparent_cb.isChecked()

        if SketchExporter.export_to_image(self.canvas, filepath, format_str=fmt, dpi=dpi, transparent=transparent):
            self.accept()
        else:
            pass
