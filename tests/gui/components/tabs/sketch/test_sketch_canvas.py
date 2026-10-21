"""Tests for SketchCanvas and the graphics items that draw sketch elements."""
from dataclasses import dataclass
from typing import ClassVar

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from pytestqt.qtbot import QtBot

from pandaplot.gui.components.tabs.sketch.graphics_items import ELEMENT_ID_KEY, build_graphics_item
from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    SketchElement,
    SketchLayer,
    StrokeStyle,
    TextAlignment,
    TextElement,
)

# Fonts and text items need a QApplication even when no widget is shown.
pytestmark = pytest.mark.usefixtures("qapp")


def _canvas(qtbot: QtBot, sketch: Sketch) -> SketchCanvas:
    canvas = SketchCanvas(sketch)
    qtbot.addWidget(canvas)
    return canvas


def _element_ids_at(canvas: SketchCanvas, point: QPointF) -> list[str]:
    """Ids of the element items under `point`, topmost first."""
    return [item.data(ELEMENT_ID_KEY) for item in canvas.scene().items(point) if item.data(ELEMENT_ID_KEY) is not None]


def _square(element_id: str) -> RectangleElement:
    return RectangleElement(id=element_id, width=100.0, height=100.0, fill_color="#FF0000")


class TestGraphicsItems:
    def test_freehand_draws_a_path_through_its_relative_points(self):
        item = build_graphics_item(FreehandElement(id="f", x=10.0, y=20.0, points=[(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]))

        assert isinstance(item, QGraphicsPathItem)
        path = item.path()
        assert [(path.elementAt(i).x, path.elementAt(i).y) for i in range(path.elementCount())] == [(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]
        assert item.pos() == QPointF(10.0, 20.0)

    def test_line_ends_at_its_offset_from_the_anchor(self):
        item = build_graphics_item(LineElement(id="l", x=10.0, y=20.0, dx=30.0, dy=-5.0))

        assert isinstance(item, QGraphicsLineItem)
        assert item.mapToScene(item.line().p2()) == QPointF(40.0, 15.0)

    def test_rectangle_has_its_size_and_corner_radius(self):
        item = build_graphics_item(RectangleElement(id="r", x=1.0, y=2.0, width=200.0, height=100.0, corner_radius=10.0))

        assert isinstance(item, QGraphicsPathItem)
        assert item.path().boundingRect() == QRectF(0.0, 0.0, 200.0, 100.0)
        assert not item.path().contains(QPointF(0.5, 0.5))
        assert item.pos() == QPointF(1.0, 2.0)

    def test_ellipse_is_centred_on_its_anchor(self):
        item = build_graphics_item(EllipseElement(id="e", x=50.0, y=60.0, rx=40.0, ry=20.0))

        assert isinstance(item, QGraphicsEllipseItem)
        assert item.mapRectToScene(item.rect()) == QRectF(10.0, 40.0, 80.0, 40.0)

    def test_text_uses_its_font_colour_and_alignment(self):
        item = build_graphics_item(TextElement(
            id="t", x=5.0, y=6.0, text="Hello\nwide line", stroke_color="#123456", font_family="Arial",
            font_size=24, is_bold=True, is_italic=True, alignment=TextAlignment.RIGHT,
        ))

        assert isinstance(item, QGraphicsTextItem)
        assert item.toPlainText() == "Hello\nwide line"
        font = item.font()
        assert (font.family(), font.pixelSize(), font.bold(), font.italic()) == ("Arial", 24, True, True)
        assert item.defaultTextColor() == QColor("#123456")
        assert item.document().defaultTextOption().alignment() == Qt.AlignmentFlag.AlignRight
        assert item.textWidth() > 0

    def test_pen_and_brush_follow_the_element_style(self):
        item = build_graphics_item(RectangleElement(
            width=10.0, height=10.0, stroke_color="#00FF00", stroke_width=4.0, stroke_style=StrokeStyle.DASHED, fill_color="#0000FF80",
        ))

        assert isinstance(item, QGraphicsPathItem)
        assert item.pen().color() == QColor("#00FF00")
        assert item.pen().widthF() == 4.0
        assert item.pen().style() == Qt.PenStyle.DashLine
        assert item.brush().color() == QColor("#0000FF80")

    def test_zero_stroke_and_no_fill_draw_nothing(self):
        item = build_graphics_item(EllipseElement(rx=5.0, ry=5.0, stroke_width=0.0, fill_color=None))

        assert isinstance(item, QGraphicsEllipseItem)
        assert item.pen().style() == Qt.PenStyle.NoPen
        assert item.brush().style() == Qt.BrushStyle.NoBrush

    def test_invalid_stroke_colour_falls_back_to_black(self):
        item = build_graphics_item(LineElement(dx=1.0, stroke_color="not a colour"))

        assert isinstance(item, QGraphicsLineItem)
        assert item.pen().color() == QColor(Qt.GlobalColor.black)

    def test_rotation_and_element_id_are_applied(self):
        item = build_graphics_item(RectangleElement(id="r", width=1.0, height=1.0, rotation=30.0))

        assert item is not None
        assert item.rotation() == 30.0
        assert item.data(ELEMENT_ID_KEY) == "r"

    def test_element_type_without_a_builder_returns_none(self):
        @dataclass(kw_only=True)
        class UnregisteredElement(SketchElement):
            TYPE: ClassVar[str] = "unregistered"

        assert build_graphics_item(UnregisteredElement()) is None


class TestSketchCanvas:
    def test_paper_matches_the_canvas_size_and_background(self, qtbot):
        canvas = _canvas(qtbot, Sketch(canvas_width=800.0, canvas_height=600.0, background_color="#FFEEDD"))

        assert canvas.sceneRect() == QRectF(0.0, 0.0, 800.0, 600.0)
        paper = canvas.scene().items(QPointF(400.0, 300.0))[-1]
        assert isinstance(paper, QGraphicsRectItem)
        assert paper.brush().color() == QColor("#FFEEDD")

    def test_every_element_gets_an_item_under_its_layer(self, qtbot):
        sketch = Sketch(layers=[SketchLayer(id="a", elements=[_square("1"), LineElement(id="2", dx=5.0)])])

        canvas = _canvas(qtbot, sketch)

        layer_item = canvas.layer_item("a")
        assert layer_item is not None
        for element_id in ("1", "2"):
            item = canvas.element_item(element_id)
            assert item is not None
            assert item.parentItem() is layer_item

    def test_higher_layers_draw_over_lower_ones(self, qtbot):
        sketch = Sketch(layers=[SketchLayer(id="bottom", elements=[_square("b")]), SketchLayer(id="top", elements=[_square("t")])])
        canvas = _canvas(qtbot, sketch)

        assert _element_ids_at(canvas, QPointF(50.0, 50.0)) == ["t", "b"]

        sketch.move_layer("bottom", 1)
        canvas.rebuild()

        assert _element_ids_at(canvas, QPointF(50.0, 50.0)) == ["b", "t"]

    def test_later_elements_draw_over_earlier_ones_within_a_layer(self, qtbot):
        canvas = _canvas(qtbot, Sketch(layers=[SketchLayer(elements=[_square("first"), _square("second"), _square("third")])]))

        assert _element_ids_at(canvas, QPointF(50.0, 50.0)) == ["third", "second", "first"]

    def test_a_lower_layer_stays_below_however_many_elements_it_has(self, qtbot):
        crowded = SketchLayer(elements=[_square(f"low-{i}") for i in range(1500)])
        canvas = _canvas(qtbot, Sketch(layers=[crowded, SketchLayer(elements=[_square("high")])]))

        assert _element_ids_at(canvas, QPointF(50.0, 50.0))[0] == "high"

    def test_hidden_layer_hides_its_elements(self, qtbot):
        canvas = _canvas(qtbot, Sketch(layers=[SketchLayer(visible=False, elements=[_square("hidden")])]))

        item = canvas.element_item("hidden")
        assert item is not None
        assert not item.isVisible()

    def test_layer_opacity_applies_to_its_elements(self, qtbot):
        canvas = _canvas(qtbot, Sketch(layers=[SketchLayer(opacity=0.25, elements=[_square("faded")])]))

        item = canvas.element_item("faded")
        assert item is not None
        assert item.effectiveOpacity() == pytest.approx(0.25)

    def test_rebuild_reflects_model_changes(self, qtbot):
        sketch = Sketch(layers=[SketchLayer(id="a", elements=[_square("old")])])
        canvas = _canvas(qtbot, sketch)

        sketch.remove_element("old")
        sketch.add_element("a", _square("new"))
        canvas.rebuild()

        assert canvas.element_item("old") is None
        assert canvas.element_item("new") is not None
        assert _element_ids_at(canvas, QPointF(50.0, 50.0)) == ["new"]

    def test_elements_without_a_builder_are_skipped(self, qtbot):
        @dataclass(kw_only=True)
        class UnregisteredElement(SketchElement):
            TYPE: ClassVar[str] = "unregistered"

        sketch = Sketch(layers=[SketchLayer(elements=[UnregisteredElement(id="x"), _square("kept")])])

        canvas = _canvas(qtbot, sketch)

        assert canvas.element_item("x") is None
        assert canvas.element_item("kept") is not None

    def test_fit_to_canvas_shows_the_whole_canvas(self, qtbot):
        canvas = _canvas(qtbot, Sketch(canvas_width=2000.0, canvas_height=1000.0))
        canvas.resize(400, 300)
        canvas.show()
        qtbot.waitExposed(canvas)

        canvas.fit_to_canvas()

        visible = canvas.mapToScene(canvas.viewport().rect()).boundingRect()
        assert visible.contains(canvas.sceneRect().adjusted(1.0, 1.0, -1.0, -1.0))
        assert visible.center().x() == pytest.approx(canvas.sceneRect().center().x(), abs=5.0)
        assert visible.center().y() == pytest.approx(canvas.sceneRect().center().y(), abs=5.0)

    def test_mouse_drag_reaches_scene_items_headless(self, qtbot):
        """Interaction spike: a real mouse drag on the viewport moves a
        movable item under the offscreen platform the GUI suite runs on."""
        canvas = _canvas(qtbot, Sketch(layers=[SketchLayer(elements=[RectangleElement(id="r", x=20.0, y=20.0, width=50.0, height=50.0)])]))
        item = canvas.element_item("r")
        assert item is not None
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        canvas.resize(800, 600)
        canvas.show()
        qtbot.waitExposed(canvas)

        start = canvas.mapFromScene(QPointF(45.0, 45.0))
        qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=start)
        qtbot.mouseMove(canvas.viewport(), pos=start + QPoint(10, 5))
        qtbot.mouseMove(canvas.viewport(), pos=start + QPoint(60, 30))
        qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=start + QPoint(60, 30))

        assert item.pos() == QPointF(80.0, 50.0)

    def test_canvas_is_accessible(self, qtbot):
        canvas = _canvas(qtbot, Sketch(name="Diagram"))

        assert canvas.accessibleName() == "Sketch canvas"
        assert "Diagram" in canvas.accessibleDescription()
