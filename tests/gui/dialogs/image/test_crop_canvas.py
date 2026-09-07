import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.image.crop_canvas import CropCanvas


def _mouse_event(event_type: QEvent.Type, pos: QPoint) -> QMouseEvent:
    # Uses the (local, global) overload rather than the 5-positional-arg one
    # (type, localPos, button, buttons, modifiers) -- the latter is flagged
    # deprecated by PySide6 even when a device is supplied explicitly.
    from PySide6.QtCore import Qt as _Qt
    point = QPointF(pos)
    return QMouseEvent(event_type, point, point, _Qt.MouseButton.LeftButton,
                        _Qt.MouseButton.LeftButton, _Qt.KeyboardModifier.NoModifier)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_canvas(widget_size=(200, 200), image_size=(100, 100)) -> CropCanvas:
    canvas = CropCanvas()
    canvas.resize(*widget_size)
    canvas.set_image(QImage(*image_size, QImage.Format.Format_RGB32))
    return canvas


class TestCropCanvasInit:
    def test_set_image_initializes_crop_rect_to_full_bounds(self):
        canvas = _make_canvas(image_size=(80, 60))
        assert canvas.crop_rect() == QRect(0, 0, 80, 60)

    def test_set_crop_rect_clamps_out_of_bounds_rect(self):
        canvas = _make_canvas(image_size=(80, 60))
        canvas.set_crop_rect(QRect(-10, -10, 1000, 1000))
        assert canvas.crop_rect() == QRect(0, 0, 80, 60)


class TestCropCanvasHitTest:
    def test_hit_test_detects_top_left_handle(self):
        # 200x200 widget, 100x100 image -> displayed at 2x scale, filling
        # the widget exactly (both square), so image (0,0) maps to widget (0,0).
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        assert canvas.hit_test(QPoint(1, 1)) == "tl"

    def test_hit_test_detects_bottom_right_handle(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        assert canvas.hit_test(QPoint(199, 199)) == "br"

    def test_hit_test_detects_body_away_from_handles(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        assert canvas.hit_test(QPoint(100, 100)) == "body"

    def test_hit_test_returns_none_outside_rect(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))  # widget-space (40,40)-(120,120)
        assert canvas.hit_test(QPoint(5, 5)) is None


class TestCropCanvasIndependentXYScale:
    # CropCanvas enforces a 200x200 minimum size (see __init__), so the
    # widget's actual size stays 200x200 regardless of resize() -- these
    # cases use that as the effective widget size.
    #
    # QSize.scaled(..., KeepAspectRatio) picks one scale factor but rounds
    # width/height to integers independently, so the fitted display size
    # isn't always exactly proportional to the image -- verified
    # empirically: a 1x7 image fit into a 200x200 widget displays at
    # 28x200 (scale_x=28/1=28.0, scale_y=200/7=28.571, genuinely
    # different). Using a single width-derived scale for both axes would
    # place image row 7 (the bottom edge) at widget y=round(7*28)=196,
    # four pixels short of the true bottom (y=200).

    def test_narrow_tall_image_uses_separate_x_and_y_scale_factors(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(1, 7))

        bottom_right = canvas._image_to_widget(QPoint(1, 7))

        # display is centered: x-offset (200-28)//2=86, y-offset (200-200)//2=0
        assert bottom_right == QPoint(86 + 28, 200)

    def test_widget_to_image_round_trips_through_independent_scales(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(1, 7))

        # The widget point exactly at the display's bottom-right corner
        # must map back to the image's bottom-right corner (1, 7), not an
        # off-by-a-few-pixels value from a single shared scale factor.
        assert canvas._widget_to_image(QPoint(86 + 28, 200)) == QPoint(1, 7)


class TestCropCanvasResizeFromHandle:
    def test_br_handle_no_aspect_lock_resizes_freely(self):
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(0, 0, 50, 50)
        result = canvas.resize_rect_from_handle(rect, "br", QPoint(80, 40))
        assert result == QRect(0, 0, 80, 40)

    def test_tl_handle_moves_top_left_corner(self):
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(10, 10, 50, 50)  # (10,10)-(60,60)
        result = canvas.resize_rect_from_handle(rect, "tl", QPoint(20, 30))
        assert result == QRect(20, 30, 40, 30)  # right/bottom (60,60) stay fixed

    def test_resize_clamps_to_image_bounds(self):
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(0, 0, 50, 50)
        result = canvas.resize_rect_from_handle(rect, "br", QPoint(500, 500))
        assert result == QRect(0, 0, 100, 100)

    def test_br_handle_with_aspect_lock_derives_height_from_width(self):
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_aspect_lock(2.0)  # width:height == 2:1
        rect = QRect(0, 0, 50, 50)
        result = canvas.resize_rect_from_handle(rect, "br", QPoint(80, 999))
        assert result.width() == 80
        assert result.height() == 40  # 80 / 2.0
        assert result.topLeft() == QPoint(0, 0)  # tl anchor unaffected by drag y

    def test_tl_handle_with_aspect_lock_keeps_opposite_corner_fixed(self):
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_aspect_lock(2.0)  # width:height == 2:1
        rect = QRect(10, 10, 60, 60)  # exclusive bottom-right at (70, 70)
        result = canvas.resize_rect_from_handle(rect, "tl", QPoint(20, 20))
        assert (result.left() + result.width(), result.top() + result.height()) == (70, 70)

    def test_tm_handle_with_aspect_lock_derives_width_anchored_at_left(self):
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_aspect_lock(2.0)
        rect = QRect(10, 10, 60, 60)  # (10,10)-(70,70)
        result = canvas.resize_rect_from_handle(rect, "tm", QPoint(999, 40))
        assert result.top() == 40
        assert result.height() == 30  # bottom (70) - top (40)
        assert result.width() == 60  # 30 * 2.0
        assert result.left() == 10  # anchored

    def test_ml_handle_with_aspect_lock_derives_height_anchored_at_top(self):
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_aspect_lock(2.0)
        rect = QRect(10, 10, 60, 60)  # (10,10)-(70,70)
        result = canvas.resize_rect_from_handle(rect, "ml", QPoint(40, 999))
        assert result.left() == 40
        assert result.width() == 30  # right (70) - left (40)
        assert result.height() == 15  # 30 / 2.0
        assert result.top() == 10  # anchored


class TestCropCanvasAspectLockBoundaryClamping:
    def test_locked_drag_past_boundary_preserves_ratio_and_stays_in_bounds(self):
        """Reproduction from review finding #2: locking to 2.0 and dragging
        the "br" handle past the image's bottom edge used to plain-intersect
        the aspect-correct rect with the image bounds, producing a rect that
        no longer satisfied the lock (4.0 instead of 2.0)."""
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_aspect_lock(2.0)
        rect = QRect(0, 150, 50, 25)

        result = canvas.resize_rect_from_handle(rect, "br", QPoint(200, 200))

        assert result.width() / result.height() == pytest.approx(2.0, rel=1e-6)
        assert result.left() >= 0 and result.top() >= 0
        assert result.left() + result.width() <= 200
        assert result.top() + result.height() <= 200
        # This specific scenario is only interesting if the naive
        # intersection (which would produce QRect(0,150,200,50), ratio 4.0)
        # would actually have violated bounds without the fix.
        assert not QRect(0, 150, 200, 50) == result


class TestCropCanvasClampAspectLockedRectFinalBoundsClamp:
    def test_out_of_bounds_anchor_still_clamps_result_within_bounds(self):
        """Finding #3 (re-review): _clamp_aspect_locked_rect's own docstring
        calls it out as "a pure function exposed directly for tests", so it
        must hold the "result stays within image bounds" invariant
        unconditionally -- not just for anchors derived from an
        already-in-bounds rect (the only way the UI ever calls it).

        Without a final clamp against image bounds, an out-of-bounds anchor
        makes every one of the function's internal derivations land
        out-of-bounds too (max_w/max_h are computed relative to the
        anchor), producing e.g. QRect(500, 500, 1, 1) against a 100x100
        image."""
        canvas = _make_canvas(image_size=(100, 100))

        result = canvas._clamp_aspect_locked_rect(QRect(500, 500, 20, 10), QPoint(500, 500), 2.0)

        assert result.left() >= 0 and result.top() >= 0
        assert result.left() + result.width() <= 100
        assert result.top() + result.height() <= 100

    def test_in_bounds_anchor_result_unchanged_by_final_clamp(self):
        """The final clamp added for the above must be a no-op for the
        existing in-bounds scenarios (e.g. finding #2's boundary-clamping
        test) -- reproduced here directly to pin that down."""
        canvas = _make_canvas(image_size=(200, 200))
        rect = QRect(0, 150, 50, 25)

        result = canvas._clamp_aspect_locked_rect(rect, rect.topLeft(), 2.0)

        assert result.width() / result.height() == pytest.approx(2.0, rel=1e-6)
        assert result.left() >= 0 and result.top() >= 0
        assert result.left() + result.width() <= 200
        assert result.top() + result.height() <= 200


class TestCropCanvasWidgetRectExclusiveConvention:
    def test_hit_test_excludes_pixel_at_exclusive_bottom_right_boundary(self):
        """Finding #4 (re-review): hit_test's body-rect (and paintEvent's
        overlay, same construction) used to build the widget-space crop
        rect via the two-QPoint QRect(topLeft, bottomRight) constructor,
        which reinterprets the *exclusive* bottom-right point as an
        *inclusive* corner -- adding a spurious 1px. Building it from an
        explicit width/height instead means the body rect's right/bottom
        edge sits exactly at the exclusive boundary, not one widget pixel
        beyond it.

        100x100 image in a 200x200 widget -> 2x scale, filling the widget
        exactly. A crop rect of (20,20)-(60,60) in image space maps to
        (40,40)-(120,120) in widget space (exclusive), so the body rect's
        right edge is at widget x=119 (the last pixel still inside), not
        x=120 (the exclusive boundary, one pixel outside). Widget point
        (120, 55) sits right on that boundary and clear of every handle's
        hit-margin (checked against each handle's rect below), so it's
        "body" under the old buggy inclusive reinterpretation but None
        (out past the crop rect entirely) with the fix."""
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))

        assert canvas._crop_widget_rect() == QRect(40, 40, 80, 80)
        for handle_rect in canvas._handle_widget_rects().values():
            assert not handle_rect.contains(QPoint(120, 55))
        assert canvas.hit_test(QPoint(120, 55)) is None

    def test_overlay_strips_cover_up_to_the_true_display_edge(self):
        """The bottom/right overlay strips used to be built from
        crop_widget_rect.bottom()/.right() -- Qt's *inclusive* accessors
        (left+width-1, top+height-1) -- even though crop_widget_rect
        itself follows this file's exclusive convention. That darkened the
        crop rect's own last row/column and left the display's actual
        last row/column uncovered by any overlay.

        100x100 image in a 200x200 widget -> 2x scale, filling the widget
        exactly (display = (0,0,200,200), so its true bottom/right edge is
        at the exclusive y=200/x=200). A crop rect of (20,20)-(60,60) in
        image space maps to widget rect (40,40,80,80) -- exclusive
        bottom-right at (120,120). The bottom strip must start exactly at
        y=120 (not 119) and reach all the way to y=199 inclusive (the
        display's last row); the right strip must start exactly at
        x=120 (not 119) and reach x=199 inclusive."""
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))

        display = canvas._display_rect()
        crop_widget_rect = canvas._crop_widget_rect()
        top, bottom, left, right = canvas._overlay_strip_rects(display, crop_widget_rect)

        assert bottom.top() == 120
        assert bottom.top() + bottom.height() - 1 == display.bottom()  # reaches the true last row
        assert right.left() == 120
        assert right.left() + right.width() - 1 == display.right()  # reaches the true last column


class TestCropCanvasDegenerateClamp:
    def test_resize_to_opposite_edge_does_not_teleport_to_origin(self):
        """Reproduction from review finding #4: dragging a handle exactly
        onto the opposite edge collapses the rect to zero size with no
        overlap with the image bounds; the old fallback jumped this all the
        way to QRect(0,0,1,1) instead of staying near the drag position."""
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(100, 100, 50, 50)

        result = canvas.resize_rect_from_handle(rect, "br", QPoint(100, 100))

        assert result != QRect(0, 0, 1, 1)
        assert result.width() == 1
        assert result.height() == 1
        assert result.left() >= 90  # stayed near (100, 100), not the origin
        assert result.top() >= 90


class TestCropCanvasMousePressButtonGuard:
    def test_right_click_does_not_start_a_drag(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))
        original = canvas.crop_rect()

        from PySide6.QtCore import Qt as _Qt

        press = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(QPoint(60, 60)), QPointF(QPoint(60, 60)),
            _Qt.MouseButton.RightButton, _Qt.MouseButton.RightButton, _Qt.KeyboardModifier.NoModifier,
        )
        canvas.mousePressEvent(press)
        canvas.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPoint(90, 90)))

        assert canvas.crop_rect() == original


class TestCropCanvasSetImageResetsDragState:
    def test_set_image_clears_in_flight_drag(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))
        canvas.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPoint(60, 60)))
        assert canvas._active_handle is not None

        canvas.set_image(QImage(50, 50, QImage.Format.Format_RGB32))

        assert canvas._active_handle is None
        assert canvas._drag_start_widget_pos is None

        # A stale mouseMoveEvent arriving after the image swap must not
        # apply a drag against the new image (nothing should happen, since
        # there's no active handle anymore).
        before = canvas.crop_rect()
        canvas.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPoint(90, 90)))
        assert canvas.crop_rect() == before


class TestCropCanvasMove:
    def test_move_rect_translates(self):
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(10, 10, 20, 20)
        result = canvas.move_rect(rect, QPoint(5, -5))
        assert result == QRect(15, 5, 20, 20)

    def test_move_rect_clamps_to_bounds(self):
        canvas = _make_canvas(image_size=(100, 100))
        rect = QRect(90, 90, 20, 20)  # already partly out of bounds on the right/bottom
        result = canvas.move_rect(rect, QPoint(50, 50))
        assert result.right() <= 99
        assert result.bottom() <= 99
        assert result.width() == 20
        assert result.height() == 20


class TestCropCanvasAspectLock:
    def test_set_aspect_lock_reflows_current_rect_and_emits_signal(self, qtbot=None):
        canvas = _make_canvas(image_size=(200, 200))
        canvas.set_crop_rect(QRect(0, 0, 100, 100))
        received = []
        canvas.cropRectChanged.connect(received.append)

        canvas.set_aspect_lock(2.0)

        assert len(received) == 1
        assert received[0].width() == 100
        assert received[0].height() == 50


class TestCropCanvasMouseDrag:
    def test_dragging_body_moves_rect_and_emits_signal(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))  # widget-space (40,40)-(120,120)
        received = []
        canvas.cropRectChanged.connect(received.append)

        canvas.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPoint(60, 60)))
        canvas.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPoint(70, 60)))
        canvas.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, QPoint(70, 60)))

        assert len(received) == 1
        # 10 widget px at 2x scale (200 widget / 100 image) == 5 image px
        assert canvas.crop_rect().left() == 25

    def test_dragging_outside_rect_does_nothing(self):
        canvas = _make_canvas(widget_size=(200, 200), image_size=(100, 100))
        canvas.set_crop_rect(QRect(20, 20, 40, 40))
        original = canvas.crop_rect()

        canvas.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, QPoint(5, 5)))
        canvas.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, QPoint(50, 50)))

        assert canvas.crop_rect() == original

    def test_paint_event_does_not_raise_on_null_image(self):
        canvas = CropCanvas()
        canvas.resize(100, 100)
        canvas.repaint()  # must not raise even with no image loaded
