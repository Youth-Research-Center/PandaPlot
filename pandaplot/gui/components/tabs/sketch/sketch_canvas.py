"""Qt Graphics View canvas that draws a Sketch and routes input to its tools."""
from typing import override

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFocusEvent, QKeyEvent, QMouseEvent, QPainter, QPalette, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QWidget,
)

from pandaplot.gui.components.tabs.sketch.geometry import Handle, hits, shape_rect
from pandaplot.gui.components.tabs.sketch.graphics_items import LayerItem, add_layer_items, build_graphics_item
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolManager
from pandaplot.gui.core.widget_extension import PGraphicsView
from pandaplot.models.events import SketchEvents
from pandaplot.models.project.items.sketch import Sketch, SketchElement, SketchLayer
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

DEFAULT_ACCENT = "#4A56C6"


def is_interactive(layer: SketchLayer) -> bool:
    """Whether elements on `layer` can be picked, selected or drawn on."""
    return layer.visible and not layer.locked


class SketchCanvas(PGraphicsView):
    """Draws a Sketch and lets the user draw on and edit it.

    The scene shows a paper rectangle of the canvas size with the sketch's
    layers stacked on it, bottom layer first. It is rebuilt from the model
    by `rebuild()`, which runs whenever the sketch announces a change, so
    the canvas never changes the model itself: tools do that through
    commands.

    The canvas also holds the selection (by element id, so it survives a
    rebuild), draws the selection box with its resize handles, shows tool
    previews, and handles pan (space+drag or middle-drag) and zoom
    (Ctrl+wheel).
    """

    selection_changed = Signal()
    zoom_changed = Signal(float)
    status_message = Signal(str)

    PAPER_Z = -1.0
    PREVIEW_Z = 1e6
    OVERLAY_Z = 2e6
    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0
    WHEEL_ZOOM_STEP = 1.15
    HIT_TOLERANCE_PX = 5.0
    HANDLE_SIZE_PX = 8.0

    def __init__(self, sketch: Sketch, parent: QWidget | None = None, *, app_context: AppContext):
        super().__init__(app_context=app_context, parent=parent)
        self._sketch = sketch
        self._layer_items: dict[str, LayerItem] = {}
        self._element_items: dict[str, QGraphicsItem] = {}
        self._selected_ids: list[str] = []
        self._paper: QGraphicsRectItem | None = None
        self._preview: QGraphicsItem | None = None
        self._rubber_band: QGraphicsRectItem | None = None
        self._selection_box: QGraphicsRectItem | None = None
        self._handles: dict[Handle, QGraphicsRectItem] = {}
        # Theme colours; until _apply_theme() runs, the palette is used.
        self._surround_color: QColor | None = None
        self._paper_border_color: QColor | None = None
        self._accent = QColor(DEFAULT_ACCENT)
        self._pan_last: QPoint | None = None
        self._space_down = False
        self.tool_manager = ToolManager(self, app_context)
        self._initialize()

    @property
    def sketch(self) -> Sketch:
        return self._sketch

    @override
    def _init_ui(self):
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Scroll bars that appear and vanish as the zoom changes resize the
        # viewport mid-fit and shift the canvas off-centre; navigation is by
        # wheel scroll, pan and zoom instead.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Sketch canvas")
        self.setAccessibleDescription(
            f"Drawing canvas for sketch '{self._sketch.name}'. Choose a tool from the toolbar; "
            "Delete removes the selection, Escape cancels, space or middle-drag pans, Ctrl+wheel zooms.",
        )
        self.viewport().setCursor(self.tool_manager.tool.cursor)
        self.rebuild()

    @override
    def _apply_theme(self):
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        self._accent = QColor(tokens["accent"])
        # A neutral grey around the paper and a hairline edge, so a white
        # sketch stays distinguishable from a white window in the light theme.
        self.set_frame_colors(surround=QColor(tokens["border_panel"]), paper_border=QColor(tokens["border_control"]))
        self._style_overlay()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(SketchEvents.SKETCH_CHANGED, self._on_sketch_changed)

    def _on_sketch_changed(self, event_data: dict):
        if event_data.get("sketch_id") == self._sketch.id:
            self.rebuild()

    # -- drawing the model ---------------------------------------------

    def rebuild(self) -> None:
        """Replace every scene item with a fresh drawing of the sketch,
        keeping the selected elements that can still be selected."""
        scene = self.scene()
        scene.clear()
        self._layer_items.clear()
        self._element_items.clear()
        self._preview = None
        self._rubber_band = None

        canvas_rect = QRectF(0.0, 0.0, self._sketch.canvas_width, self._sketch.canvas_height)
        paper = QGraphicsRectItem(canvas_rect)
        background = QColor(self._sketch.background_color)
        paper.setBrush(QBrush(background if background.isValid() else QColor(Qt.GlobalColor.white)))
        paper.setPen(self._paper_pen())
        paper.setZValue(self.PAPER_Z)
        scene.addItem(paper)
        scene.setSceneRect(canvas_rect)
        self._paper = paper

        layer_items, element_items = add_layer_items(scene, self._sketch.layers)
        self._layer_items.update(layer_items)
        self._element_items.update(element_items)

        self._build_overlay()
        selectable = [element_id for element_id in self._selected_ids if self._is_selectable(element_id)]
        if selectable != self._selected_ids:
            self._selected_ids = selectable
            self.selection_changed.emit()
        self._update_overlay()

    def layer_item(self, layer_id: str) -> QGraphicsItem | None:
        """The parent item drawing the layer with `layer_id`, or None."""
        return self._layer_items.get(layer_id)

    def element_item(self, element_id: str) -> QGraphicsItem | None:
        """The item drawing the element with `element_id`, or None."""
        return self._element_items.get(element_id)

    def set_frame_colors(self, *, surround: QColor, paper_border: QColor) -> None:
        """Set the colour around the paper and of the paper's edge.

        The theme sets these: the window background colour can match a
        white paper exactly, which would hide where the canvas ends.
        """
        self._surround_color = surround
        self._paper_border_color = paper_border
        if self._paper is not None:
            self._paper.setPen(self._paper_pen())
        self.viewport().update()

    def _paper_pen(self) -> QPen:
        if self._paper_border_color is None:
            return QPen(Qt.PenStyle.NoPen)
        pen = QPen(self._paper_border_color, 1.0)
        # One screen pixel at any zoom.
        pen.setCosmetic(True)
        return pen

    @override
    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        surround = self._surround_color or self.palette().color(QPalette.ColorRole.Window)
        painter.fillRect(rect, surround)

    # -- previews --------------------------------------------------------

    def show_preview(self, element: SketchElement | None) -> None:
        """Draw `element`, which is not in the model, above every layer;
        None removes the preview."""
        if self._preview is not None:
            self.scene().removeItem(self._preview)
            self._preview = None
        if element is None:
            return
        item = build_graphics_item(element)
        if item is not None:
            item.setZValue(self.PREVIEW_Z)
            self.scene().addItem(item)
            self._preview = item

    def preview_elements(self, elements: dict[str, SketchElement]) -> None:
        """Draw changed copies of model elements in place of the originals,
        without changing the model. `rebuild()` restores the originals."""
        for element_id, element in elements.items():
            old = self._element_items.get(element_id)
            item = build_graphics_item(element)
            if old is None or item is None:
                continue
            item.setParentItem(old.parentItem())
            item.setZValue(old.zValue())
            self.scene().removeItem(old)
            self._element_items[element_id] = item
        self._update_overlay()

    def preview_layer_opacity(self, layer_id: str, opacity: float) -> None:
        """Draw a layer at `opacity` without changing the model.
        `rebuild()` restores the model's opacity."""
        layer_item = self._layer_items.get(layer_id)
        if layer_item is not None:
            layer_item.setOpacity(opacity)

    def show_rubber_band(self, rect: QRectF | None) -> None:
        """Show the rubber-band selection rectangle, or hide it with None."""
        if rect is None:
            if self._rubber_band is not None:
                self._rubber_band.hide()
            return
        if self._rubber_band is None:
            self._rubber_band = QGraphicsRectItem()
            self._rubber_band.setZValue(self.OVERLAY_Z)
            self.scene().addItem(self._rubber_band)
            self._style_overlay()
        self._rubber_band.setRect(rect.normalized())
        self._rubber_band.show()

    # -- picking and selection -------------------------------------------

    @property
    def zoom(self) -> float:
        """Current scale of the view (1.0 is 100%)."""
        return self.transform().m11()

    def hit_tolerance(self) -> float:
        """How far from a stroke a click still picks it, in scene units."""
        return self.HIT_TOLERANCE_PX / self.zoom

    def min_drag_distance(self) -> float:
        """Shortest drag, in scene units, that counts as a drag, not a click."""
        return QApplication.startDragDistance() / self.zoom

    def _interactive_elements_top_down(self) -> list[SketchElement]:
        elements = []
        for layer in reversed(self._sketch.layers):
            if is_interactive(layer):
                elements.extend(reversed(layer.elements))
        return elements

    def _is_selectable(self, element_id: str) -> bool:
        found = self._sketch.find_element(element_id)
        return found is not None and is_interactive(found[0]) and element_id in self._element_items

    def element_at(self, scene_pos: QPointF) -> str | None:
        """Id of the topmost element under `scene_pos` on a visible,
        unlocked layer, or None."""
        tolerance = self.hit_tolerance()
        for element in self._interactive_elements_top_down():
            item = self._element_items.get(element.id)
            if item is not None and hits(element, item, scene_pos, tolerance):
                return element.id
        return None

    def elements_in(self, rect: QRectF) -> list[str]:
        """Ids of elements on visible, unlocked layers that `rect` touches,
        bottom-most first."""
        rect = rect.normalized()
        found = []
        for element in reversed(self._interactive_elements_top_down()):
            item = self._element_items.get(element.id)
            if item is not None and rect.intersects(shape_rect(item).adjusted(-0.5, -0.5, 0.5, 0.5)):
                found.append(element.id)
        return found

    @property
    def selected_ids(self) -> tuple[str, ...]:
        """Ids of the selected elements, in the order they were selected."""
        return tuple(self._selected_ids)

    def set_selection(self, element_ids: list[str]) -> None:
        """Select exactly the selectable elements among `element_ids`."""
        selection = [element_id for element_id in dict.fromkeys(element_ids) if self._is_selectable(element_id)]
        if selection == self._selected_ids:
            return
        self._selected_ids = selection
        self._update_overlay()
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        self.set_selection([])

    def selection_rect(self) -> QRectF | None:
        """Scene bounds of the selected elements' geometry, or None."""
        rect: QRectF | None = None
        for element_id in self._selected_ids:
            item = self._element_items.get(element_id)
            if item is not None:
                bounds = shape_rect(item)
                rect = bounds if rect is None else rect.united(bounds)
        return rect

    def can_resize_selection(self) -> bool:
        """Resizing maps geometry between unrotated boxes, so it is only
        offered when no selected element is rotated."""
        if not self._selected_ids:
            return False
        for element_id in self._selected_ids:
            found = self._sketch.find_element(element_id)
            if found is None or found[1].rotation != 0.0:
                return False
        return True

    def handle_at(self, scene_pos: QPointF) -> Handle | None:
        """The resize handle under `scene_pos`, or None."""
        if not self.can_resize_selection():
            return None
        box = self.selection_rect()
        if box is None:
            return None
        point = self.mapFromScene(scene_pos)
        reach = self.HANDLE_SIZE_PX / 2 + 2
        for handle in Handle:
            centre = self.mapFromScene(handle.position(box))
            if abs(point.x() - centre.x()) <= reach and abs(point.y() - centre.y()) <= reach:
                return handle
        return None

    def _build_overlay(self) -> None:
        self._selection_box = QGraphicsRectItem()
        self._selection_box.setZValue(self.OVERLAY_Z)
        self.scene().addItem(self._selection_box)
        self._handles = {}
        half = self.HANDLE_SIZE_PX / 2
        for handle in Handle:
            item = QGraphicsRectItem(-half, -half, self.HANDLE_SIZE_PX, self.HANDLE_SIZE_PX)
            # Same size on screen at every zoom.
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            item.setZValue(self.OVERLAY_Z + 1)
            self.scene().addItem(item)
            self._handles[handle] = item
        self._style_overlay()

    def _style_overlay(self) -> None:
        dashed = QPen(self._accent, 1.0, Qt.PenStyle.DashLine)
        dashed.setCosmetic(True)
        solid = QPen(self._accent, 1.0)
        solid.setCosmetic(True)
        if self._selection_box is not None:
            self._selection_box.setPen(dashed)
            self._selection_box.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        if self._rubber_band is not None:
            self._rubber_band.setPen(dashed)
            fill = QColor(self._accent)
            fill.setAlpha(30)
            self._rubber_band.setBrush(QBrush(fill))
        for item in self._handles.values():
            item.setPen(solid)
            item.setBrush(QBrush(Qt.GlobalColor.white))

    def _update_overlay(self) -> None:
        box = self.selection_rect()
        if self._selection_box is None:
            return
        if box is None:
            self._selection_box.hide()
            for item in self._handles.values():
                item.hide()
            return
        self._selection_box.setRect(box)
        self._selection_box.show()
        show_handles = self.can_resize_selection()
        for handle, item in self._handles.items():
            item.setPos(handle.position(box))
            item.setVisible(show_handles)

    # -- zoom and pan ----------------------------------------------------

    def fit_to_canvas(self) -> None:
        """Scale the view so the whole canvas is visible."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_changed.emit(self.zoom)

    def zoom_by(self, factor: float, *, anchor: QPoint | None = None) -> None:
        """Zoom by `factor`, keeping the scene point under `anchor` (a
        viewport position; default the centre) in place. Zoom stays between
        MIN_ZOOM and MAX_ZOOM, except that a fit beyond those limits is
        never pushed further out of range."""
        current = self.zoom
        if factor > 1.0:
            target = min(current * factor, max(self.MAX_ZOOM, current))
        else:
            target = max(current * factor, min(self.MIN_ZOOM, current))
        if target == current:
            return
        anchor = anchor if anchor is not None else self.viewport().rect().center()
        before = self.mapToScene(anchor)
        self.scale(target / current, target / current)
        after = self.mapToScene(anchor)
        self._scroll_by_scene(before - after)
        self._update_overlay()
        self.zoom_changed.emit(self.zoom)

    def _scroll_by_scene(self, delta: QPointF) -> None:
        horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
        horizontal.setValue(horizontal.value() + round(delta.x() * self.zoom))
        vertical.setValue(vertical.value() + round(delta.y() * self.zoom))

    def _pan_by(self, delta: QPoint) -> None:
        horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
        horizontal.setValue(horizontal.value() - delta.x())
        vertical.setValue(vertical.value() - delta.y())

    # -- input -----------------------------------------------------------

    def _scene_pos(self, event: QMouseEvent) -> QPointF:
        return self.mapToScene(event.position().toPoint())

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        starts_pan = event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self._space_down)
        if starts_pan:
            self._pan_last = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.LeftButton:
            self.tool_manager.tool.press(self._scene_pos(event), event.modifiers())
        event.accept()

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # The second click of a double-click starts a gesture like any other.
        self.mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_last is not None:
            position = event.position().toPoint()
            self._pan_by(position - self._pan_last)
            self._pan_last = position
        else:
            self.tool_manager.tool.move(self._scene_pos(event), event.modifiers())
        event.accept()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_last is not None:
            if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
                self._pan_last = None
                self._restore_cursor()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.tool_manager.tool.release(self._scene_pos(event), event.modifiers())
        event.accept()

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.zoom_by(self.WHEEL_ZOOM_STEP ** steps, anchor=event.position().toPoint())
            event.accept()
            return
        super().wheelEvent(event)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self._space_down = True
                if self._pan_last is None:
                    self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if not self.tool_manager.tool.cancel():
                self.clear_selection()
            event.accept()
            return
        if self.tool_manager.tool.key_press(event):
            event.accept()
            return
        super().keyPressEvent(event)

    @override
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            if self._pan_last is None:
                self._restore_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        # A space released while another widget had focus never reaches us.
        self._space_down = False
        self._restore_cursor()
        super().focusOutEvent(event)

    def _restore_cursor(self) -> None:
        self.viewport().setCursor(self.tool_manager.tool.cursor)
