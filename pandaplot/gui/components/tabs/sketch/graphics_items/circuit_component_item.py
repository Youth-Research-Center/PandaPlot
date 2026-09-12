from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.models.project.items.sketch import CircuitComponentElement


class CircuitComponentGraphicsItem(BaseGraphicsItem):
    """QGraphicsItem representing a circuit component schematic symbol."""

    def __init__(self, element: CircuitComponentElement, parent: Optional[QGraphicsItem] = None):
        self.element: CircuitComponentElement = element
        super().__init__(element, parent)

    def boundingRect(self) -> QRectF:
        pen_w = self.element.stroke_width
        return QRectF(-30, -30, 60, 60).adjusted(-pen_w, -pen_w, pen_w, pen_w)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(QRectF(-20, -15, 40, 30))
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.save()
        pen = self.get_pen()
        painter.setPen(pen)
        painter.setBrush(self.get_brush())

        sx = -1.0 if self.element.flip_horizontal else 1.0
        sy = -1.0 if self.element.flip_vertical else 1.0
        if sx != 1.0 or sy != 1.0:
            painter.scale(sx, sy)

        comp_type = self.element.component_type

        if comp_type == "resistor":
            self._paint_resistor(painter)
        elif comp_type == "capacitor":
            self._paint_capacitor(painter)
        elif comp_type == "inductor":
            self._paint_inductor(painter)
        elif comp_type == "diode":
            self._paint_diode(painter)
        elif comp_type == "voltage_source":
            self._paint_voltage_source(painter)
        elif comp_type == "ground":
            self._paint_ground(painter)
        elif comp_type == "transformer":
            self._paint_transformer(painter)
        elif comp_type in ("voltmeter", "ammeter"):
            self._paint_meter(painter, "V" if comp_type == "voltmeter" else "A")
        else:
            self._paint_resistor(painter)

        painter.restore()

        if self.element.label_visible:
            self._paint_labels(painter)

    def _paint_resistor(self, painter: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(-20, 0)
        path.lineTo(-12, 0)
        pts = [
            (-9, -6), (-5, 6), (-1, -6), (3, 6), (7, -6), (11, 6), (12, 0)
        ]
        for px, py in pts:
            path.lineTo(px, py)
        path.lineTo(20, 0)
        painter.drawPath(path)

    def _paint_capacitor(self, painter: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(-20, 0)
        path.lineTo(-4, 0)
        path.moveTo(4, 0)
        path.lineTo(20, 0)
        painter.drawPath(path)

        painter.drawLine(-4, -10, -4, 10)
        painter.drawLine(4, -10, 4, 10)

    def _paint_inductor(self, painter: QPainter) -> None:
        path = QPainterPath()
        path.moveTo(-20, 0)
        path.lineTo(-15, 0)

        start_x = -15.0
        arc_w = 7.5
        for i in range(4):
            x1 = start_x + i * arc_w
            rect = QRectF(x1, -6, arc_w, 12)
            path.arcTo(rect, 180, -180)

        path.lineTo(20, 0)
        painter.drawPath(path)

    def _paint_diode(self, painter: QPainter) -> None:
        painter.drawLine(-20, 0, -10, 0)
        painter.drawLine(10, 0, 20, 0)

        tri = QPainterPath()
        tri.moveTo(-10, -8)
        tri.lineTo(10, 0)
        tri.lineTo(-10, 8)
        tri.closeSubpath()
        painter.drawPath(tri)

        painter.drawLine(10, -8, 10, 8)

    def _paint_voltage_source(self, painter: QPainter) -> None:
        painter.drawLine(-20, 0, -10, 0)
        painter.drawLine(10, 0, 20, 0)
        painter.drawEllipse(QRectF(-10, -10, 20, 20))

        font = QFont("Sans-Serif", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(-8, -8, 8, 16), Qt.AlignCenter, "+")
        painter.drawText(QRectF(0, -8, 8, 16), Qt.AlignCenter, "-")

    def _paint_ground(self, painter: QPainter) -> None:
        painter.drawLine(0, -10, 0, 0)
        painter.drawLine(-10, 0, 10, 0)
        painter.drawLine(-6, 4, 6, 4)
        painter.drawLine(-2, 8, 2, 8)

    def _paint_transformer(self, painter: QPainter) -> None:
        painter.drawLine(-20, -10, -10, -10)
        painter.drawLine(-20, 10, -10, 10)

        path_p = QPainterPath()
        path_p.moveTo(-10, -10)
        for i in range(3):
            y1 = -10.0 + i * 6.66
            rect = QRectF(-14, y1, 8, 6.66)
            path_p.arcTo(rect, 90, -180)
        path_p.lineTo(-10, 10)
        painter.drawPath(path_p)

        painter.drawLine(20, -10, 10, -10)
        painter.drawLine(20, 10, 10, 10)

        path_s = QPainterPath()
        path_s.moveTo(10, -10)
        for i in range(3):
            y1 = -10.0 + i * 6.66
            rect = QRectF(6, y1, 8, 6.66)
            path_s.arcTo(rect, 90, 180)
        path_s.lineTo(10, 10)
        painter.drawPath(path_s)

        painter.drawLine(-2, -12, -2, 12)
        painter.drawLine(2, -12, 2, 12)

        painter.setBrush(QBrush(QColor(self.element.stroke_color)))
        painter.drawEllipse(QRectF(-14, -14, 3, 3))
        painter.drawEllipse(QRectF(11, -14, 3, 3))

    def _paint_meter(self, painter: QPainter, letter: str) -> None:
        painter.drawLine(-20, 0, -10, 0)
        painter.drawLine(10, 0, 20, 0)
        painter.drawEllipse(QRectF(-10, -10, 20, 20))
        font = QFont("Sans-Serif", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(-10, -10, 20, 20), Qt.AlignCenter, letter)

    def _paint_labels(self, painter: QPainter) -> None:
        font = QFont("Sans-Serif", 8)
        color = QColor(self.element.stroke_color)

        desig = self.element.designator
        val = self.element.value

        if not desig and not val:
            return

        rot = self.element.rotation
        flip_h = self.element.flip_horizontal
        flip_v = self.element.flip_vertical

        if desig:
            self._draw_upright_text(painter, desig, QPointF(0, -16), font, color, rot, flip_h, flip_v)
        if val:
            self._draw_upright_text(painter, val, QPointF(0, 16), font, color, rot, flip_h, flip_v)

    def _draw_upright_text(
        self,
        painter: QPainter,
        text: str,
        pos: QPointF,
        font: QFont,
        color: QColor,
        rotation: float,
        flip_h: bool,
        flip_v: bool,
    ) -> None:
        painter.save()
        painter.translate(pos)
        if flip_h:
            painter.scale(-1, 1)
        if flip_v:
            painter.scale(1, -1)
        painter.rotate(-rotation)
        painter.setFont(font)
        painter.setPen(color)
        fm = painter.fontMetrics()
        rect = fm.boundingRect(text)
        painter.drawText(QPointF(-rect.width() / 2, rect.height() / 4), text)
        painter.restore()
