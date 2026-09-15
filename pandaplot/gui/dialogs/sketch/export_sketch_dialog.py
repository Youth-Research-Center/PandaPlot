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
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "SVG", "PDF"])
        form_layout.addRow("Format:", self.format_combo)

        self.region_combo = QComboBox()
        self.region_combo.addItems(["Entire Canvas", "Bounding Box of Elements"])
        form_layout.addRow("Region:", self.region_combo)

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems(["72 DPI", "150 DPI", "300 DPI (Publication)", "600 DPI (High Res)"])
        self.dpi_combo.setCurrentIndex(2)
        form_layout.addRow("Resolution:", self.dpi_combo)

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

    def _get_selected_dpi(self) -> int:
        idx = self.dpi_combo.currentIndex()
        dpi_map = {0: 72, 1: 150, 2: 300, 3: 600}
        return dpi_map.get(idx, 300)

    def _do_export(self) -> None:
        filepath = self.file_path_edit.text().strip()
        if not filepath:
            self._browse_file()
            filepath = self.file_path_edit.text().strip()
            if not filepath:
                return

        fmt = self.format_combo.currentText()
        dpi = self._get_selected_dpi()
        transparent = self.transparent_cb.isChecked()
        use_bbox = self.region_combo.currentIndex() == 1

        if SketchExporter.export_to_image(
            self.canvas,
            filepath,
            format_str=fmt,
            dpi=dpi,
            transparent=transparent,
            use_bounding_box=use_bbox,
        ):
            self.accept()
