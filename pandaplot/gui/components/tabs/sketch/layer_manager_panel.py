from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch import (
    AddLayerCommand,
    DeleteLayerCommand,
    ReorderLayersCommand,
    UpdateLayerPropertiesCommand,
)
from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.models.project.items.sketch import Sketch, SketchLayer
from pandaplot.models.state.app_context import AppContext


class LayerManagerPanel(QWidget):
    """Sidebar widget for managing sketch layers (add, delete, reorder, visibility, lock, opacity, rename)."""

    layer_changed = Signal()

    def __init__(
        self,
        sketch: Sketch,
        canvas: SketchCanvas,
        command_executor: Optional[CommandExecutor] = None,
        app_context: Optional[AppContext] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.sketch: Sketch = sketch
        self.canvas: SketchCanvas = canvas
        self.command_executor: Optional[CommandExecutor] = command_executor
        self.app_context: Optional[AppContext] = app_context

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

        toggles_layout = QHBoxLayout()
        self.lock_btn = QPushButton("🔒 Toggle Lock")
        self.lock_btn.clicked.connect(self._toggle_lock)
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self._rename_layer)
        toggles_layout.addWidget(self.lock_btn)
        toggles_layout.addWidget(self.rename_btn)
        layout.addLayout(toggles_layout)

        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("Opacity:")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        layout.addLayout(opacity_layout)

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
                self.opacity_slider.blockSignals(True)  # noqa: FBT003
                self.opacity_slider.setValue(int(layer.opacity * 100))
                self.opacity_slider.blockSignals(False)  # noqa: FBT003
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
            self._update_layer_props(layer_id, {"visible": not layer.visible})

    def _toggle_lock(self) -> None:
        active_layer = self.sketch.get_active_layer()
        if active_layer:
            self._update_layer_props(active_layer.id, {"locked": not active_layer.locked})

    def _rename_layer(self) -> None:
        active_layer = self.sketch.get_active_layer()
        if not active_layer:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Layer", "New layer name:", text=active_layer.name)
        if ok and new_name:
            self._update_layer_props(active_layer.id, {"name": new_name})

    def _on_opacity_changed(self, val: int) -> None:
        active_layer = self.sketch.get_active_layer()
        if active_layer:
            self._update_layer_props(active_layer.id, {"opacity": val / 100.0})

    def _update_layer_props(self, layer_id: str, props: dict) -> None:
        if self.command_executor:
            cmd = UpdateLayerPropertiesCommand(self.sketch, layer_id, props, app_context=self.app_context)
            self.command_executor.execute_command(cmd)
        else:
            layer = self.sketch.get_layer(layer_id)
            if layer:
                for k, v in props.items():
                    if hasattr(layer, k):
                        setattr(layer, k, v)

        self.canvas.rebuild_scene()
        self.refresh_layer_list()
        self.layer_changed.emit()

    def _add_layer(self) -> None:
        new_layer = SketchLayer(name=f"Layer {len(self.sketch.layers) + 1}")
        if self.command_executor:
            cmd = AddLayerCommand(self.sketch, new_layer, app_context=self.app_context)
            self.command_executor.execute_command(cmd)
        else:
            self.sketch.layers.append(new_layer)
            self.sketch.active_layer_id = new_layer.id

        self.canvas.rebuild_scene()
        self.refresh_layer_list()
        self.layer_changed.emit()

    def _delete_layer(self) -> None:
        if len(self.sketch.layers) <= 1:
            return
        active_layer = self.sketch.get_active_layer()
        if not active_layer:
            return

        if self.command_executor:
            cmd = DeleteLayerCommand(self.sketch, active_layer.id, app_context=self.app_context)
            self.command_executor.execute_command(cmd)
        else:
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
            new_layers = list(self.sketch.layers)
            new_layers[idx], new_layers[idx + 1] = new_layers[idx + 1], new_layers[idx]
            if self.command_executor:
                cmd = ReorderLayersCommand(self.sketch, new_layers, app_context=self.app_context)
                self.command_executor.execute_command(cmd)
            else:
                self.sketch.layers = new_layers

            self.canvas.rebuild_scene()
            self.refresh_layer_list()
            self.layer_changed.emit()

    def _move_down(self) -> None:
        active_layer = self.sketch.get_active_layer()
        if not active_layer:
            return
        idx = self.sketch.layers.index(active_layer)
        if idx > 0:
            new_layers = list(self.sketch.layers)
            new_layers[idx], new_layers[idx - 1] = new_layers[idx - 1], new_layers[idx]
            if self.command_executor:
                cmd = ReorderLayersCommand(self.sketch, new_layers, app_context=self.app_context)
                self.command_executor.execute_command(cmd)
            else:
                self.sketch.layers = new_layers

            self.canvas.rebuild_scene()
            self.refresh_layer_list()
            self.layer_changed.emit()
