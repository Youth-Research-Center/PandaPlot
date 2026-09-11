from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolBar,
    QWidget,
)

from pandaplot.commands.project.sketch.sketch_commands import UpdateComponentLabelCommand
from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.models.project.items.sketch import CircuitComponentElement


class SketchPropertyInspector(QToolBar):
    """Property Inspector toolbar for controlling stroke, fill, and font properties."""

    property_changed = Signal(object)

    def __init__(self, canvas: SketchCanvas, parent: Optional[QWidget] = None):
        super().__init__("Sketch Property Inspector", parent)
        self.canvas: SketchCanvas = canvas

        self.stroke_color_btn = QPushButton("Stroke")
        self.stroke_color_btn.clicked.connect(self._choose_stroke_color)
        self.addWidget(self.stroke_color_btn)

        self.stroke_width_spin = QDoubleSpinBox()
        self.stroke_width_spin.setRange(0.5, 50.0)
        self.stroke_width_spin.setValue(2.0)
        self.stroke_width_spin.setSingleStep(0.5)
        self.stroke_width_spin.setPrefix("Width: ")
        self.stroke_width_spin.valueChanged.connect(self._on_stroke_width_changed)
        self.addWidget(self.stroke_width_spin)

        self.stroke_style_combo = QComboBox()
        self.stroke_style_combo.addItems(["Solid", "Dashed", "Dotted", "Dash_Dot"])
        self.stroke_style_combo.currentTextChanged.connect(self._on_stroke_style_changed)
        self.addWidget(self.stroke_style_combo)

        self.fill_color_btn = QPushButton("Fill")
        self.fill_color_btn.clicked.connect(self._choose_fill_color)
        self.addWidget(self.fill_color_btn)

        self.addSeparator()

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._on_font_family_changed)
        self.addWidget(self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 144)
        self.font_size_spin.setValue(14)
        self.font_size_spin.setPrefix("Size: ")
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self.addWidget(self.font_size_spin)

        self.bold_btn = QPushButton("B")
        self.bold_btn.setCheckable(True)
        self.bold_btn.clicked.connect(self._on_font_bold_toggled)
        self.addWidget(self.bold_btn)

        self.italic_btn = QPushButton("I")
        self.italic_btn.setCheckable(True)
        self.italic_btn.clicked.connect(self._on_font_italic_toggled)
        self.addWidget(self.italic_btn)

        self.addSeparator()

        # Circuit Component Label Editors
        self.desig_label = QLabel("Designator:")
        self.addWidget(self.desig_label)
        self.desig_edit = QLineEdit()
        self.desig_edit.setMaximumWidth(80)
        self.desig_edit.editingFinished.connect(self._on_designator_edited)
        self.addWidget(self.desig_edit)

        self.val_label = QLabel("Value:")
        self.addWidget(self.val_label)
        self.val_edit = QLineEdit()
        self.val_edit.setMaximumWidth(80)
        self.val_edit.editingFinished.connect(self._on_value_edited)
        self.addWidget(self.val_edit)

        self._set_circuit_fields_visible(False)

        self.canvas.selection_changed.connect(self.update_from_selection)

    def _set_circuit_fields_visible(self, visible: bool) -> None:
        self.desig_label.setVisible(visible)
        self.desig_edit.setVisible(visible)
        self.val_label.setVisible(visible)
        self.val_edit.setVisible(visible)

    def _get_selected_circuit_elements(self):
        selected_items = self.canvas.scene().selectedItems()
        return [
            item.element for item in selected_items
            if isinstance(item, BaseGraphicsItem) and isinstance(item.element, CircuitComponentElement)
        ]

    def _on_designator_edited(self) -> None:
        elems = self._get_selected_circuit_elements()
        if not elems:
            return
        new_text = self.desig_edit.text().strip()
        cmd = UpdateComponentLabelCommand(
            self.canvas.sketch, [e.id for e in elems], designator=new_text
        )
        if self.canvas.command_executor:
            self.canvas.command_executor.execute_command(cmd)
        else:
            cmd.execute()
        self.canvas.rebuild_scene()
        self.canvas.notify_sketch_changed()

    def _on_value_edited(self) -> None:
        elems = self._get_selected_circuit_elements()
        if not elems:
            return
        new_text = self.val_edit.text().strip()
        cmd = UpdateComponentLabelCommand(
            self.canvas.sketch, [e.id for e in elems], value=new_text
        )
        if self.canvas.command_executor:
            self.canvas.command_executor.execute_command(cmd)
        else:
            cmd.execute()
        self.canvas.rebuild_scene()
        self.canvas.notify_sketch_changed()

    def _choose_stroke_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.canvas.active_stroke_color), self, "Select Stroke Color")
        if color.isValid():
            hex_color = color.name()
            self.canvas.active_stroke_color = hex_color
            self.property_changed.emit({"stroke_color": hex_color})

    def _choose_fill_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.canvas.active_fill_color) if self.canvas.active_fill_color != "none" else Qt.white, self, "Select Fill Color")
        if color.isValid():
            hex_color = color.name()
            self.canvas.active_fill_color = hex_color
            self.property_changed.emit({"fill_color": hex_color})

    def _on_stroke_width_changed(self, val: float) -> None:
        self.canvas.active_stroke_width = val
        self.property_changed.emit({"stroke_width": val})

    def _on_stroke_style_changed(self, style_str: str) -> None:
        style_lower = style_str.lower()
        self.canvas.active_stroke_style = style_lower
        self.property_changed.emit({"stroke_style": style_lower})

    def _on_font_family_changed(self, font) -> None:
        family = font.family()
        self.canvas.active_font_family = family
        self.property_changed.emit({"font_family": family})

    def _on_font_size_changed(self, size: int) -> None:
        self.canvas.active_font_size = size
        self.property_changed.emit({"font_size": size})

    def _on_font_bold_toggled(self, checked: bool) -> None:
        self.property_changed.emit({"is_bold": checked})

    def _on_font_italic_toggled(self, checked: bool) -> None:
        self.property_changed.emit({"is_italic": checked})

    def update_from_selection(self) -> None:
        selected_items = self.canvas.scene().selectedItems()
        if not selected_items:
            self._set_circuit_fields_visible(False)
            return

        circuit_elems = self._get_selected_circuit_elements()
        if circuit_elems:
            self._set_circuit_fields_visible(True)
            self.desig_edit.blockSignals(True)
            self.val_edit.blockSignals(True)

            first_desig = circuit_elems[0].designator
            all_desig_same = all(e.designator == first_desig for e in circuit_elems)
            if all_desig_same:
                self.desig_edit.setPlaceholderText("")
                self.desig_edit.setText(first_desig)
            else:
                self.desig_edit.clear()
                self.desig_edit.setPlaceholderText("Mixed")

            first_val = circuit_elems[0].value
            all_val_same = all(e.value == first_val for e in circuit_elems)
            if all_val_same:
                self.val_edit.setPlaceholderText("")
                self.val_edit.setText(first_val)
            else:
                self.val_edit.clear()
                self.val_edit.setPlaceholderText("Mixed")

            self.desig_edit.blockSignals(False)
            self.val_edit.blockSignals(False)
        else:
            self._set_circuit_fields_visible(False)

        item = selected_items[0]
        if hasattr(item, "element"):
            elem = item.element

            self.stroke_width_spin.blockSignals(True)
            self.font_combo.blockSignals(True)
            self.font_size_spin.blockSignals(True)
            self.bold_btn.blockSignals(True)
            self.italic_btn.blockSignals(True)

            if hasattr(elem, "stroke_width"):
                self.stroke_width_spin.setValue(elem.stroke_width)
            if hasattr(elem, "stroke_color"):
                self.canvas.active_stroke_color = elem.stroke_color
            if hasattr(elem, "fill_color"):
                self.canvas.active_fill_color = elem.fill_color
            if hasattr(elem, "font_family"):
                self.font_combo.setCurrentFont(QFont(elem.font_family))
            if hasattr(elem, "font_size"):
                self.font_size_spin.setValue(elem.font_size)
            if hasattr(elem, "is_bold"):
                self.bold_btn.setChecked(elem.is_bold)
            if hasattr(elem, "is_italic"):
                self.italic_btn.setChecked(elem.is_italic)

            self.stroke_width_spin.blockSignals(False)
            self.font_combo.blockSignals(False)
            self.font_size_spin.blockSignals(False)
            self.bold_btn.blockSignals(False)
            self.italic_btn.blockSignals(False)
