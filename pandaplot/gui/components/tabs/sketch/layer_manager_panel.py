from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.models.project.items.sketch import Sketch, SketchLayer


class LayerManagerPanel(QWidget):
    """Sidebar widget for managing sketch layers (add, delete, reorder, visibility, lock)."""

    layer_changed = Signal()

    def __init__(self, sketch: Sketch, canvas: SketchCanvas, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sketch: Sketch = sketch
        self.canvas: SketchCanvas = canvas

        layout = QVBoxLayout(self)

        title_label = QLabel("Layer Manager")
        title_label.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title_label)

        self.layer_list = QListWidget()
        self.layer_list.itemClicked.connect(self._on_item_clicked)
        self.layer_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.layer_list)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.add_btn.clicked.connect(self._add_layer)
        self.del_btn = QPushButton("- Delete")
        self.del_btn.clicked.connect(self._delete_layer)
        self.up_btn = QPushButton("▲")
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn = QPushButton("▼")
        self.down_btn.clicked.connect(self._move_down)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        layout.addLayout(btn_layout)

        self.refresh_layer_list()

    def refresh_layer_list(self) -> None:
        self.layer_list.clear()
        for layer in reversed(self.sketch.layers):
            vis_str = "👁" if layer.visible else "🙈"
            lock_str = "🔒" if layer.locked else "🔓"
            active_str = " ★" if layer.id == self.sketch.active_layer_id else ""
            item_text = f"{vis_str} {lock_str} {layer.name}{active_str}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, layer.id)
            if layer.id == self.sketch.active_layer_id:
                item.setSelected(True)
            self.layer_list.addItem(item)

        self.del_btn.setEnabled(len(self.sketch.layers) > 1)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.UserRole)
        self.sketch.active_layer_id = layer_id
        self.refresh_layer_list()
        self.layer_changed.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.UserRole)
        layer = self.sketch.get_layer(layer_id)
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
