"""Qt Graphics View canvas that draws a Sketch."""
import logging
from typing import override

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items import build_graphics_item
from pandaplot.models.project.items.sketch import Sketch


class _LayerItem(QGraphicsItem):
    """Invisible parent of one layer's element items.

    Children stack by z-value among their siblings only, so the layer's own
    z-value orders whole layers while each element's z-value orders it
    within its layer. Visibility and opacity set here apply to every child.
    """

    def __init__(self, layer_id: str):
        super().__init__()
        self.layer_id = layer_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)

    @override
    def boundingRect(self) -> QRectF:
        return QRectF()

    @override
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        pass


class SketchCanvas(QGraphicsView):
    """Draws a Sketch: a paper rectangle of the canvas size with the
    sketch's layers stacked on it, bottom layer first.

    The scene is rebuilt from the model by `rebuild()`; the canvas never
    changes the model itself.
    """

    PAPER_Z = -1.0

    def __init__(self, sketch: Sketch, parent: QWidget | None = None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._sketch = sketch
        self._layer_items: dict[str, _LayerItem] = {}
        self._element_items: dict[str, QGraphicsItem] = {}
        self._paper: QGraphicsRectItem | None = None
        # Theme colours for the area around the paper and the paper's edge;
        # until set_frame_colors() is called, the palette is used.
        self._surround_color: QColor | None = None
        self._paper_border_color: QColor | None = None

        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Scroll bars that appear and vanish as the zoom changes resize the
        # viewport mid-fit and shift the canvas off-centre; navigation is by
        # wheel scroll, pan and zoom instead.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName("Sketch canvas")
        self.setAccessibleDescription(f"Drawing canvas for sketch '{sketch.name}'")
        self.rebuild()

    @property
    def sketch(self) -> Sketch:
        return self._sketch

    def rebuild(self) -> None:
        """Replace every scene item with a fresh drawing of the sketch."""
        scene = self.scene()
        scene.clear()
        self._layer_items.clear()
        self._element_items.clear()

        canvas_rect = QRectF(0.0, 0.0, self._sketch.canvas_width, self._sketch.canvas_height)
        paper = QGraphicsRectItem(canvas_rect)
        background = QColor(self._sketch.background_color)
        paper.setBrush(QBrush(background if background.isValid() else QColor(Qt.GlobalColor.white)))
        paper.setPen(self._paper_pen())
        paper.setZValue(self.PAPER_Z)
        scene.addItem(paper)
        self._paper = paper
        scene.setSceneRect(canvas_rect)

        for layer_index, layer in enumerate(self._sketch.layers):
            layer_item = _LayerItem(layer.id)
            layer_item.setZValue(layer_index)
            layer_item.setVisible(layer.visible)
            layer_item.setOpacity(layer.opacity)
            scene.addItem(layer_item)
            self._layer_items[layer.id] = layer_item
            for element_index, element in enumerate(layer.elements):
                item = build_graphics_item(element)
                if item is None:
                    continue
                item.setParentItem(layer_item)
                item.setZValue(element_index)
                self._element_items[element.id] = item

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

    def fit_to_canvas(self) -> None:
        """Scale the view so the whole canvas is visible."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    @override
    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        surround = self._surround_color or self.palette().color(QPalette.ColorRole.Window)
        painter.fillRect(rect, surround)
