from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.models.project.items.sketch import (
    CircuitComponentElement,
    Sketch,
    SketchLayer,
    WireElement,
)


class LayerManagerPanel(QWidget):
    """Sidebar widget for managing sketch layers and viewing/deleting individual layer elements."""

    layer_changed = Signal()

    def __init__(self, sketch: Sketch, canvas: SketchCanvas, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sketch: Sketch = sketch
        self.canvas: SketchCanvas = canvas

        layout = QVBoxLayout(self)

        title_label = QLabel("Layers & Elements")
        title_label.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title_label)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Layer")
        self.add_btn.clicked.connect(self._add_layer)
        self.del_btn = QPushButton("- Delete")
        self.del_btn.clicked.connect(self._delete_selected)
        self.up_btn = QPushButton("▲")
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn = QPushButton("▼")
        self.down_btn.clicked.connect(self._move_down)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        layout.addLayout(btn_layout)

        self.canvas.sketch_changed.connect(self.refresh_layer_list)

        self.refresh_layer_list()

    def refresh_layer_list(self) -> None:
        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()

        for layer in reversed(self.sketch.layers):
            vis_str = "👁" if layer.visible else "🙈"
            lock_str = "🔒" if layer.locked else "🔓"
            active_str = " ★" if layer.id == self.sketch.active_layer_id else ""
            layer_text = f"{vis_str} {lock_str} {layer.name}{active_str}"

            layer_item = QTreeWidgetItem([layer_text])
            layer_item.setData(0, Qt.UserRole, {"type": "layer", "id": layer.id})
            layer_item.setExpanded(True)

            if layer.id == self.sketch.active_layer_id:
                layer_item.setSelected(True)

            for elem in layer.elements:
                if isinstance(elem, CircuitComponentElement):
                    elem_text = f"⚡ {elem.designator or elem.component_type} ({elem.value})" if elem.value else f"⚡ {elem.designator or elem.component_type}"
                elif isinstance(elem, WireElement):
                    conn_str = "connected" if (elem.start_ref or elem.end_ref) else "floating"
                    elem_text = f"🔌 Wire ({conn_str})"
                else:
                    elem_text = f"🎨 {elem.type.title()}"

                elem_item = QTreeWidgetItem([elem_text])
                elem_item.setData(0, Qt.UserRole, {"type": "element", "id": elem.id, "layer_id": layer.id})
                layer_item.addChild(elem_item)

            self.tree_widget.addTopLevelItem(layer_item)

        self.del_btn.setEnabled(len(self.sketch.layers) > 1 or self._has_selected_element())
        self.tree_widget.blockSignals(False)

    def _has_selected_element(self) -> bool:
        selected = self.tree_widget.selectedItems()
        if not selected:
            return False
        data = selected[0].data(0, Qt.UserRole)
        return isinstance(data, dict) and data.get("type") == "element"

    def _on_item_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, dict):
            return

        if data.get("type") == "layer":
            self.sketch.active_layer_id = data["id"]
            self.refresh_layer_list()
            self.layer_changed.emit()
        elif data.get("type") == "element":
            elem_id = data["id"]
            g_item = self.canvas.item_map.get(elem_id)
            if g_item:
                self.canvas.scene().clearSelection()
                g_item.setSelected(True)

    def _on_item_double_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict) and data.get("type") == "layer":
            layer = self.sketch.get_layer(data["id"])
            if layer:
                layer.visible = not layer.visible
                self.canvas.rebuild_scene()
                self.refresh_layer_list()
                self.layer_changed.emit()

    def _add_layer(self) -> None:
        new_layer = SketchLayer(name=f"Layer {len(self.sketch.layers) + 1}")
        self.sketch.layers.append(new_layer)
        self.sketch.active_layer_id = new_layer.id
        self.canvas.rebuild_scene()
        self.refresh_layer_list()
        self.layer_changed.emit()

    def _delete_selected(self) -> None:
        selected = self.tree_widget.selectedItems()
        if not selected:
            return

        data = selected[0].data(0, Qt.UserRole)
        if not isinstance(data, dict):
            return

        if data.get("type") == "element":
            self.canvas.delete_selected_elements()
            self.refresh_layer_list()
        elif data.get("type") == "layer":
            self._delete_layer()

    def _delete_layer(self) -> None:
        if len(self.sketch.layers) <= 1:
            return
        active_layer = self.sketch.get_active_layer()
        if active_layer:
            self.sketch.layers.remove(active_layer)
            self.sketch.active_layer_id = self.sketch.layers[-1].id
            self.canvas.rebuild_scene()
            self.refresh_layer_list()
            self.layer_changed.emit()

    def _move_up(self) -> None:
        active_layer = self.sketch.get_active_layer()
        if not active_layer:
            return
        idx = self.sketch.layers.index(active_layer)
        if idx < len(self.sketch.layers) - 1:
            self.sketch.layers[idx], self.sketch.layers[idx + 1] = (
                self.sketch.layers[idx + 1],
                self.sketch.layers[idx],
            )
            self.canvas.rebuild_scene()
            self.refresh_layer_list()
            self.layer_changed.emit()

    def _move_down(self) -> None:
        active_layer = self.sketch.get_active_layer()
        if not active_layer:
            return
        idx = self.sketch.layers.index(active_layer)
        if idx > 0:
            self.sketch.layers[idx], self.sketch.layers[idx - 1] = (
                self.sketch.layers[idx - 1],
                self.sketch.layers[idx],
            )
            self.canvas.rebuild_scene()
            self.refresh_layer_list()
            self.layer_changed.emit()
