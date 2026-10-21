"""Tests for the selection-box resize maths."""
import pytest
from PySide6.QtCore import QPointF, QRectF

from pandaplot.gui.components.tabs.sketch.geometry import Handle, resized_box, scale_changes
from pandaplot.models.project.items.sketch import FreehandElement, LineElement, TextElement

BOX = QRectF(100.0, 100.0, 100.0, 50.0)


def test_dragging_past_the_opposite_side_stops_at_the_minimum_size():
    box = resized_box(BOX, Handle.E, QPointF(20.0, 0.0), keep_aspect=False, min_size=4.0)

    assert box == QRectF(100.0, 100.0, 4.0, 50.0)


def test_a_corner_with_keep_aspect_scales_both_sides_equally():
    box = resized_box(BOX, Handle.NW, QPointF(50.0, 90.0), keep_aspect=True, min_size=1.0)

    assert box.bottomRight() == BOX.bottomRight()
    assert box.width() / box.height() == pytest.approx(2.0)
    assert box.width() == pytest.approx(150.0)


def test_an_axis_without_extent_is_left_alone():
    flat = QRectF(10.0, 20.0, 100.0, 0.0)

    box = resized_box(flat, Handle.SE, QPointF(210.0, 80.0), keep_aspect=False, min_size=1.0)

    assert box == QRectF(10.0, 20.0, 200.0, 0.0)


def test_scaling_a_horizontal_line_keeps_it_horizontal():
    line = LineElement(x=10.0, y=20.0, dx=100.0, dy=0.0)

    changes = scale_changes(line, QRectF(10.0, 20.0, 100.0, 0.0), QRectF(10.0, 20.0, 200.0, 0.0))

    assert changes == {"x": 10.0, "y": 20.0, "dx": 200.0, "dy": 0.0}


def test_freehand_points_scale_about_the_anchor():
    stroke = FreehandElement(x=0.0, y=0.0, points=[(0.0, 0.0), (10.0, 20.0)])

    changes = scale_changes(stroke, QRectF(0.0, 0.0, 10.0, 20.0), QRectF(0.0, 0.0, 30.0, 10.0))

    assert changes["points"] == [(0.0, 0.0), (30.0, 10.0)]


def test_text_grows_with_its_height_and_never_vanishes():
    label = TextElement(x=0.0, y=0.0, font_size=10)

    assert scale_changes(label, QRectF(0, 0, 50, 20), QRectF(0, 0, 50, 40))["font_size"] == 20
    assert scale_changes(label, QRectF(0, 0, 50, 20), QRectF(0, 0, 50, 0.5))["font_size"] == 1
