"""Dialog for choosing how to export a sketch."""
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.number_input import DecimalInput
from pandaplot.gui.components.tabs.sketch.sketch_export import (
    FORMATS,
    MAX_RASTER_PIXELS,
    ExportFormat,
    ExportRegion,
    SketchExportOptions,
    export_rect,
    output_size,
)
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

LAYER_ID_ROLE = Qt.ItemDataRole.UserRole
_NUMBER_WIDTH = 120


class ExportSketchDialog(PDialog):
    """Asks for the export format, region, background, scale and layers,
    and shows the size of the file that will be written."""

    def __init__(
        self, app_context: AppContext, sketch: Sketch, parent: QWidget | None = None, *, initial: SketchExportOptions | None = None,
    ):
        super().__init__(app_context, parent)
        self.sketch = sketch
        self._initial = initial or SketchExportOptions()
        self._initialize()

    @classmethod
    def ask(
        cls, app_context: AppContext, sketch: Sketch, parent: QWidget | None = None, *, initial: SketchExportOptions | None = None,
    ) -> SketchExportOptions | None:
        """Show the dialog; the chosen options, or None if cancelled."""
        dialog = cls(app_context, sketch, parent, initial=initial)
        try:
            return dialog.options() if dialog.exec() == QDialog.DialogCode.Accepted else None
        finally:
            dialog.deleteLater()

    @override
    def _init_ui(self):
        self.setWindowTitle(f"Export {self.sketch.name}")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        initial = self._initial

        self.format_combo = DropDownComboBox(self)
        for export_format, info in FORMATS.items():
            self.format_combo.addItem(f"{info.label} ({info.extension})", export_format.value)
        self.format_combo.setCurrentIndex(self.format_combo.findData(initial.format.value))
        self.format_combo.setAccessibleName("Format")
        form.addRow("Format:", self.format_combo)

        self.canvas_radio = QRadioButton(f"Whole canvas ({self.sketch.canvas_width:g} × {self.sketch.canvas_height:g})", self)
        self.elements_radio = QRadioButton("Drawn elements, with padding", self)
        self.padding_input = DecimalInput(self)
        self.padding_input.setRange(0.0, 500.0)
        self.padding_input.setDecimals(0)
        self.padding_input.setSuffix(" px")
        self.padding_input.setValue(initial.padding)
        self.padding_input.setAccessibleName("Padding")
        self.padding_input.setMaximumWidth(_NUMBER_WIDTH)
        self._region_group = QButtonGroup(self)
        self._region_group.addButton(self.canvas_radio)
        self._region_group.addButton(self.elements_radio)
        (self.canvas_radio if initial.region is ExportRegion.CANVAS else self.elements_radio).setChecked(True)
        elements_row = QHBoxLayout()
        elements_row.addWidget(self.elements_radio)
        elements_row.addWidget(self.padding_input)
        elements_row.addStretch(1)
        region = QVBoxLayout()
        region.addWidget(self.canvas_radio)
        region.addLayout(elements_row)
        form.addRow("Region:", region)

        self.solid_radio = QRadioButton("Canvas colour", self)
        self.transparent_radio = QRadioButton("Transparent", self)
        self._background_group = QButtonGroup(self)
        self._background_group.addButton(self.solid_radio)
        self._background_group.addButton(self.transparent_radio)
        (self.transparent_radio if initial.transparent else self.solid_radio).setChecked(True)
        background = QHBoxLayout()
        background.addWidget(self.solid_radio)
        background.addWidget(self.transparent_radio)
        background.addStretch(1)
        form.addRow("Background:", background)

        self.scale_input = DecimalInput(self)
        self.scale_input.setRange(0.25, 10.0)
        self.scale_input.setSingleStep(0.5)
        self.scale_input.setSuffix(" ×")
        self.scale_input.setValue(initial.scale)
        self.scale_input.setAccessibleName("Scale")
        self.scale_input.setMaximumWidth(_NUMBER_WIDTH)
        self.scale_input.setToolTip("Output pixels per canvas pixel (PNG and JPEG). 2× doubles the width and height.")
        form.addRow("Scale:", self.scale_input)

        self.layer_list = QListWidget(self)
        self.layer_list.setAccessibleName("Layers to export")
        for layer in reversed(self.sketch.layers):
            item = QListWidgetItem(layer.name if layer.visible else f"{layer.name} (hidden)")
            item.setData(LAYER_ID_ROLE, layer.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            chosen = layer.visible if initial.layer_ids is None else layer.id in initial.layer_ids
            item.setCheckState(Qt.CheckState.Checked if chosen else Qt.CheckState.Unchecked)
            self.layer_list.addItem(item)
        self.layer_list.setMaximumHeight(120)
        form.addRow("Layers:", self.layer_list)

        self.size_label = QLabel(self)
        self.size_label.setAccessibleName("Output size")
        layout.addWidget(self.size_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.export_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.export_button.setText("Export…")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.format_combo.currentIndexChanged.connect(lambda _index: self._update())
        self._region_group.buttonToggled.connect(lambda _button, _checked: self._update())
        self._background_group.buttonToggled.connect(lambda _button, _checked: self._update())
        self.padding_input.valueChanged.connect(lambda _value: self._update())
        self.scale_input.valueChanged.connect(lambda _value: self._update())
        self.layer_list.itemChanged.connect(lambda _item: self._update())
        self._update()

    @override
    def _apply_theme(self):
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        self.setStyleSheet(f"""
            ExportSketchDialog {{
                background-color: {tokens["surface_white"]};
            }}
            QLabel, QRadioButton {{
                color: {tokens["text_primary"]};
            }}
        """)
        self.size_label.setStyleSheet(f"color: {tokens['text_secondary']};")

    def _format(self) -> ExportFormat:
        return ExportFormat(self.format_combo.currentData())

    def _chosen_layer_ids(self) -> frozenset[str]:
        return frozenset(
            self.layer_list.item(row).data(LAYER_ID_ROLE)
            for row in range(self.layer_list.count())
            if self.layer_list.item(row).checkState() == Qt.CheckState.Checked
        )

    def options(self) -> SketchExportOptions:
        """The options the controls describe."""
        export_format = self._format()
        return SketchExportOptions(
            format=export_format,
            region=ExportRegion.CANVAS if self.canvas_radio.isChecked() else ExportRegion.ELEMENTS,
            transparent=self.transparent_radio.isChecked() and FORMATS[export_format].supports_transparency,
            scale=self.scale_input.value(),
            padding=self.padding_input.value(),
            layer_ids=self._chosen_layer_ids(),
        )

    def _update(self) -> None:
        info = FORMATS[self._format()]
        self.transparent_radio.setEnabled(info.supports_transparency)
        self.transparent_radio.setToolTip("" if info.supports_transparency else f"{info.label}s always have a solid background")
        self.scale_input.setEnabled(info.raster)
        self.padding_input.setEnabled(self.elements_radio.isChecked())
        options = self.options()
        rect = export_rect(self.sketch, options) if options.layer_ids else None
        if rect is None:
            reason = "Choose at least one layer." if not options.layer_ids else "The chosen layers have no elements."
            self.size_label.setText(f"Nothing to export. {reason}")
            self.export_button.setEnabled(False)
            return
        size = output_size(rect, options)
        unit = "px" if info.raster or options.format is ExportFormat.SVG else "pt"
        too_large = info.raster and size.width() * size.height() > MAX_RASTER_PIXELS
        note = " (too large: choose a smaller scale or region)" if too_large else ""
        self.size_label.setText(f"Output: {size.width()} × {size.height()} {unit}{note}")
        self.export_button.setEnabled(not too_large)
