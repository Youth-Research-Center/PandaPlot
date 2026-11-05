"""Side panel listing a sketch's layers, with controls to manage them."""
from collections.abc import Callable
from typing import override

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.base_command import Command
from pandaplot.commands.project.sketch import (
    AddSketchLayerCommand,
    DeleteSketchLayerCommand,
    RenameSketchLayerCommand,
    ReorderSketchLayerCommand,
    SetActiveSketchLayerCommand,
    SetSketchLayerPropertiesCommand,
)
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import SketchEvents
from pandaplot.models.project.items.sketch import Sketch, SketchLayer
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

_ICON_SIZE = 16
_DIMMED_ALPHA = 110
LAYER_ID_ROLE = Qt.ItemDataRole.UserRole


def _draw_eye(painter: QPainter, *, crossed: bool) -> None:
    outline = QPainterPath(QPointF(1.5, 8.0))
    outline.quadTo(8.0, 1.5, 14.5, 8.0)
    outline.quadTo(8.0, 14.5, 1.5, 8.0)
    painter.drawPath(outline)
    painter.drawEllipse(QPointF(8.0, 8.0), 2.0, 2.0)
    if crossed:
        painter.drawLine(QPointF(2.5, 13.5), QPointF(13.5, 2.5))


def _draw_lock(painter: QPainter, *, locked: bool) -> None:
    painter.drawRoundedRect(QRectF(3.0, 7.5, 10.0, 7.0), 1.5, 1.5)
    shackle = QPainterPath(QPointF(5.5, 7.5))
    # An open lock has its shackle lifted, free on the right.
    lift = 0.0 if locked else 2.0
    shackle.lineTo(5.5, 5.0 - lift)
    shackle.arcTo(QRectF(5.5, 1.5 - lift, 5.0, 7.0), 180.0, -180.0)
    shackle.lineTo(10.5, 7.5 if locked else 4.5 - lift)
    painter.drawPath(shackle)


def _icon_pixmap(color: QColor, draw: Callable[[QPainter], None]) -> QPixmap:
    scale = 2
    pixmap = QPixmap(_ICON_SIZE * scale, _ICON_SIZE * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    draw(painter)
    painter.end()
    return pixmap


def toggle_icon(color: QColor, *, on: Callable[[QPainter], None], off: Callable[[QPainter], None]) -> QIcon:
    """An icon for a checkable button: `on` drawn in `color` when checked,
    `off` dimmed when not."""
    dimmed = QColor(color)
    dimmed.setAlpha(_DIMMED_ALPHA)
    icon = QIcon()
    icon.addPixmap(_icon_pixmap(color, on), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_icon_pixmap(dimmed, off), QIcon.Mode.Normal, QIcon.State.Off)
    return icon


class LayerRow(QWidget):
    """One row of the layer list: visibility and lock toggles and the name."""

    visibility_toggled = Signal(str, bool)
    lock_toggled = Signal(str, bool)

    def __init__(self, layer: SketchLayer, parent: QWidget | None = None):
        super().__init__(parent)
        self.layer_id = layer.id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        self.visible_button = self._toggle_button()
        self.lock_button = self._toggle_button()
        self.name_label = QLabel(self)
        layout.addWidget(self.visible_button)
        layout.addWidget(self.lock_button)
        layout.addWidget(self.name_label, stretch=1)
        self.visible_button.toggled.connect(lambda checked: self.visibility_toggled.emit(self.layer_id, checked))
        self.lock_button.toggled.connect(lambda checked: self.lock_toggled.emit(self.layer_id, checked))
        self.update_from(layer)

    def _toggle_button(self) -> QToolButton:
        button = QToolButton(self)
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return button

    def update_from(self, layer: SketchLayer) -> None:
        """Show `layer`'s current name, visibility and lock state."""
        for button, checked in ((self.visible_button, layer.visible), (self.lock_button, layer.locked)):
            button.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
            button.setChecked(checked)
            button.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
        self.name_label.setText(layer.name)
        self.visible_button.setToolTip("Hide layer" if layer.visible else "Show layer")
        self.visible_button.setAccessibleName(f"Visible: {layer.name}")
        self.lock_button.setToolTip("Unlock layer" if layer.locked else "Lock layer")
        self.lock_button.setAccessibleName(f"Locked: {layer.name}")

    def set_icon_color(self, color: QColor) -> None:
        self.visible_button.setIcon(toggle_icon(
            color, on=lambda painter: _draw_eye(painter, crossed=False), off=lambda painter: _draw_eye(painter, crossed=True),
        ))
        self.lock_button.setIcon(toggle_icon(
            color, on=lambda painter: _draw_lock(painter, locked=True), off=lambda painter: _draw_lock(painter, locked=False),
        ))


class _LayerList(QListWidget):
    """The layer list; F2 or Enter renames the current layer."""

    rename_requested = Signal()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_F2, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.rename_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class LayerManagerPanel(PWidget):
    """Lists a sketch's layers, top layer first, and changes them through
    undoable commands.

    The selected row is the active layer, the one new elements are drawn
    on. Each row toggles its layer's visibility and lock; double-click, F2
    or Enter renames. The buttons below add a layer above the active one,
    delete it, or move it up or down, and the slider sets its opacity.
    Dragging the slider only previews the opacity (`opacity_previewed`);
    releasing it applies the change as one undo step.
    """

    opacity_previewed = Signal(str, float)

    def __init__(self, app_context: AppContext, sketch: Sketch, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self.sketch = sketch
        self.rows: dict[str, LayerRow] = {}
        self._icon_color = QColor("#4B5563")
        self._initialize()

    @override
    def _init_ui(self):
        # Lets the stylesheet paint this plain QWidget subclass's background.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAccessibleName("Layers")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.header = SectionHeader("Layers", self)
        layout.addWidget(self.header)

        self.layer_list = _LayerList(self)
        self.layer_list.setAccessibleName("Layer list")
        self.layer_list.setAccessibleDescription(
            "Layers from top to bottom. The selected layer is the one you draw on. Double-click, F2 or Enter renames it.",
        )
        self.layer_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.layer_list.currentItemChanged.connect(self._on_current_item_changed)
        self.layer_list.itemDoubleClicked.connect(lambda _item: self.rename_active_layer())
        self.layer_list.rename_requested.connect(self.rename_active_layer)
        layout.addWidget(self.layer_list, stretch=1)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.add_button = self._button("+", "Add layer", "Add a layer above the selected one", self.add_layer)
        self.delete_button = self._button("−", "Delete layer", "Delete the selected layer", self.delete_active_layer)
        self.up_button = self._button("▲", "Move layer up", "Move the selected layer up", lambda: self.move_active_layer(1))
        self.down_button = self._button("▼", "Move layer down", "Move the selected layer down", lambda: self.move_active_layer(-1))
        for button in (self.add_button, self.delete_button, self.up_button, self.down_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(6)
        self.opacity_caption = QLabel("Opacity", self)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setPageStep(10)
        self.opacity_slider.setAccessibleName("Layer opacity")
        self.opacity_slider.setAccessibleDescription("Opacity of the selected layer, in percent")
        self.opacity_caption.setBuddy(self.opacity_slider)
        self.opacity_value = QLabel(self)
        self.opacity_value.setMinimumWidth(36)
        self.opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.opacity_slider.valueChanged.connect(self._on_opacity_value_changed)
        self.opacity_slider.sliderReleased.connect(self._commit_opacity)
        opacity_row.addWidget(self.opacity_caption)
        opacity_row.addWidget(self.opacity_slider, stretch=1)
        opacity_row.addWidget(self.opacity_value)
        layout.addLayout(opacity_row)

        self.refresh()

    def _button(self, text: str, name: str, tooltip: str, on_click: Callable[[], object]) -> PButton:
        button = PButton(text, icon=True, on_click=lambda _checked=False: on_click(), parent=self)
        button.setAccessibleName(name)
        button.setToolTip(tooltip)
        return button

    @override
    def _apply_theme(self):
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        self.header.set_tokens(tokens)
        self._icon_color = QColor(tokens["text_secondary"])
        for row in self.rows.values():
            row.set_icon_color(self._icon_color)
        self.setStyleSheet(f"""
            LayerManagerPanel {{
                background-color: {tokens["surface_white"]};
                border-left: 1px solid {tokens["border_panel"]};
            }}
            LayerRow QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {tokens["radius_control"]}px;
                padding: 2px;
            }}
            LayerRow QToolButton:hover {{
                background-color: {tokens["surface_inset"]};
            }}
            LayerRow QToolButton:focus {{
                border-color: {tokens["accent"]};
            }}
            QListWidget {{
                background-color: {tokens["surface_white"]};
                border: 1px solid {tokens["border_panel"]};
                border-radius: {tokens["radius_control"]}px;
            }}
            QListWidget::item:selected {{
                background-color: {tokens["accent_selected_bg"]};
            }}
            QLabel {{
                color: {tokens["text_primary"]};
            }}
        """)

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(SketchEvents.SKETCH_CHANGED, self._on_sketch_changed)

    def _on_sketch_changed(self, event_data: dict):
        if event_data.get("sketch_id") == self.sketch.id:
            self.refresh()

    # -- showing the model -------------------------------------------------

    def refresh(self) -> None:
        """Show the sketch's current layers and active layer.

        Rows are rebuilt only when layers were added, removed or reordered,
        so a toggle that changes its own layer is never deleted while its
        click is being handled.
        """
        top_down = list(reversed(self.sketch.layers))
        if [layer.id for layer in top_down] != list(self.rows):
            self._rebuild_rows(top_down)
        else:
            for layer in top_down:
                self.rows[layer.id].update_from(layer)
        self.layer_list.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
        for row_index, layer in enumerate(top_down):
            item = self.layer_list.item(row_index)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, self._accessible_text(layer))
            if layer.id == self.sketch.active_layer_id:
                self.layer_list.setCurrentItem(item)
        self.layer_list.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
        self._update_controls()

    def _rebuild_rows(self, top_down: list[SketchLayer]) -> None:
        self.layer_list.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
        self.layer_list.clear()
        self.rows = {}
        for layer in top_down:
            item = QListWidgetItem()
            item.setData(LAYER_ID_ROLE, layer.id)
            row = LayerRow(layer)
            row.set_icon_color(self._icon_color)
            row.visibility_toggled.connect(lambda layer_id, visible: self._set_properties(layer_id, visible=visible))
            row.lock_toggled.connect(lambda layer_id, locked: self._set_properties(layer_id, locked=locked))
            item.setSizeHint(row.sizeHint())
            self.layer_list.addItem(item)
            self.layer_list.setItemWidget(item, row)
            self.rows[layer.id] = row
        self.layer_list.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args

    @staticmethod
    def _accessible_text(layer: SketchLayer) -> str:
        states = [] if layer.visible else ["hidden"]
        if layer.locked:
            states.append("locked")
        if layer.opacity < 1.0:
            states.append(f"opacity {round(layer.opacity * 100)}%")
        return ", ".join([layer.name, *states])

    def _update_controls(self) -> None:
        layer = self.sketch.active_layer
        index = self.sketch.layer_index(layer.id)
        can_delete = len(self.sketch.layers) > 1 and not layer.locked
        self.delete_button.setEnabled(can_delete)
        self.delete_button.setToolTip(
            "Delete the selected layer" if can_delete
            else "Unlock the layer to delete it" if layer.locked
            else "A sketch needs at least one layer",
        )
        self.up_button.setEnabled(index is not None and index < len(self.sketch.layers) - 1)
        self.down_button.setEnabled(index is not None and index > 0)
        if not self.opacity_slider.isSliderDown():
            self.opacity_slider.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
            self.opacity_slider.setValue(round(layer.opacity * 100))
            self.opacity_slider.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
            self._show_opacity(self.opacity_slider.value())

    def _show_opacity(self, percent: int) -> None:
        self.opacity_value.setText(f"{percent}%")

    # -- user actions ------------------------------------------------------

    def _execute(self, command: Command) -> bool:
        changed = self.app_context.get_command_executor().execute_command(command)
        if not changed:
            # Undo any toggle or slider state the refused change left behind.
            self.refresh()
        return changed

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is not None:
            self._execute(SetActiveSketchLayerCommand(self.app_context, self.sketch, current.data(LAYER_ID_ROLE)))

    def _set_properties(
        self, layer_id: str, *, visible: bool | None = None, locked: bool | None = None, opacity: float | None = None,
    ) -> None:
        self._execute(SetSketchLayerPropertiesCommand(
            self.app_context, self.sketch, layer_id, visible=visible, locked=locked, opacity=opacity,
        ))

    def add_layer(self) -> None:
        """Add a layer above the active one and make it active."""
        self._execute(AddSketchLayerCommand(self.app_context, self.sketch))

    def delete_active_layer(self) -> None:
        self._execute(DeleteSketchLayerCommand(self.app_context, self.sketch, self.sketch.active_layer_id))

    def move_active_layer(self, steps: int) -> None:
        """Move the active layer `steps` places up (positive) or down."""
        index = self.sketch.layer_index(self.sketch.active_layer_id)
        if index is not None:
            self._execute(ReorderSketchLayerCommand(self.app_context, self.sketch, self.sketch.active_layer_id, index + steps))

    def rename_active_layer(self) -> None:
        layer = self.sketch.active_layer
        name = self.app_context.get_ui_controller().get_text_input("Rename Layer", "Layer name:", layer.name)
        if name is not None:
            self._execute(RenameSketchLayerCommand(self.app_context, self.sketch, layer.id, name))

    def _on_opacity_value_changed(self, percent: int) -> None:
        self._show_opacity(percent)
        if self.opacity_slider.isSliderDown():
            self.opacity_previewed.emit(self.sketch.active_layer_id, percent / 100)
        else:
            # Keyboard steps and clicks on the groove change it at once.
            self._commit_opacity()

    def _commit_opacity(self) -> None:
        self._set_properties(self.sketch.active_layer_id, opacity=self.opacity_slider.value() / 100)
