"""
Interactive crop-selection canvas.

Displays a QImage scaled to fit the widget's current size, with an
always-present crop rectangle (in image-coordinate space, not widget/screen
space) that the user drags to move and resizes via 8 corner/edge handles.
There is no "draw a new rectangle from scratch" mode -- the rectangle always
exists, starting at the full image bounds.
"""
from typing import Dict, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QResizeEvent
from PySide6.QtWidgets import QWidget

_HANDLE_SIZE = 8
_HIT_MARGIN = 6
_HANDLE_NAMES = ("tl", "tm", "tr", "ml", "mr", "bl", "bm", "br")


def clamp_rect_to_bounds(rect: QRect, width: int, height: int) -> QRect:
    """Intersects rect with a 0,0,width,height box, normalizing first.
    Shared by CropCanvas and ImageEditorDialog so both clamp crop rects the
    same way against their own image-size source.

    If the normalized rect has no overlap with the bounds at all (e.g. a
    drag that pushed a handle exactly onto or past the opposite edge),
    falls back to a minimum 1x1 rect anchored at whichever edge the rect
    was pushed against, rather than always jumping to a fixed (0,0,1,1)
    origin -- which would visually teleport the crop rect to the top-left
    corner regardless of where the user was actually dragging.
    """
    bounds = QRect(0, 0, width, height)
    normalized = rect.normalized()
    clamped = normalized.intersected(bounds)
    if not clamped.isEmpty():
        return clamped
    x = min(max(normalized.left(), 0), max(0, width - 1))
    y = min(max(normalized.top(), 0), max(0, height - 1))
    return QRect(x, y, 1, 1)


class CropCanvas(QWidget):
    """Fit-to-widget image display with a draggable/resizable crop rectangle."""

    cropRectChanged = Signal(QRect)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._image = QImage()
        self._crop_rect = QRect()
        self._aspect_lock: Optional[float] = None
        self._active_handle: Optional[str] = None
        self._drag_start_widget_pos: Optional[QPoint] = None
        self._drag_start_rect: QRect = QRect()

    # ---- public API -------------------------------------------------

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._crop_rect = QRect(0, 0, image.width(), image.height())
        # A new image invalidates any in-flight drag: its start rect was
        # computed against the previous image's coordinate space, so a
        # stale mouseMoveEvent arriving after e.g. an undo swaps the image
        # out from under an active drag must not apply that stale rect
        # (mirrors the reset mouseReleaseEvent already does).
        self._active_handle = None
        self._drag_start_widget_pos = None
        self.update()

    def crop_rect(self) -> QRect:
        return QRect(self._crop_rect)

    def aspect_lock(self) -> Optional[float]:
        return self._aspect_lock

    def set_crop_rect(self, rect: QRect) -> None:
        self._crop_rect = self._clamp_to_image(rect)
        self.update()

    def set_aspect_lock(self, ratio: Optional[float], preserve: str = "width") -> None:
        """Applies (or clears, for ratio=None) an aspect lock to the current
        crop rect.

        `preserve` says which of the rect's current dimensions is
        authoritative and should be kept as-is, with the other derived from
        it to satisfy `ratio` -- "width" (the default, used when the lock
        selection itself changes, or a commit resets the rect to full
        bounds) or "height" (used when the user just edited the height
        spinbox specifically, so *that* edit must survive the reflow rather
        than being overwritten back to whatever height matches the
        unchanged width)."""
        self._aspect_lock = ratio
        if ratio is not None and not self._crop_rect.isEmpty():
            reflowed = self._reflow_to_aspect(self._crop_rect, ratio, preserve=preserve)
            # Same class of bug as resize_rect_from_handle (finding #2): a
            # plain intersection of the ratio-correct reflowed rect against
            # the image bounds can produce a rect that no longer satisfies
            # the lock (e.g. selecting a 1:1 lock on a wide rect whose full
            # width doesn't fit as a square within the image height). The
            # anchor here is always the rect's original top-left corner,
            # since _reflow_to_aspect keeps that fixed and only derives the
            # other dimension.
            self._crop_rect = self._clamp_aspect_locked_rect(reflowed, reflowed.topLeft(), ratio)
            self.update()
            self.cropRectChanged.emit(self.crop_rect())

    # ---- coordinate mapping ------------------------------------------

    def _display_rect(self) -> QRect:
        if self._image.isNull():
            return QRect()
        scaled = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _scale_x(self) -> float:
        display = self._display_rect()
        if display.isEmpty() or self._image.width() == 0:
            return 1.0
        return display.width() / self._image.width()

    def _scale_y(self) -> float:
        display = self._display_rect()
        if display.isEmpty() or self._image.height() == 0:
            return 1.0
        return display.height() / self._image.height()

    def _image_to_widget(self, point: QPoint) -> QPoint:
        # QSize.scaled(..., KeepAspectRatio) picks one scale factor but then
        # rounds width and height to integers independently, so the fitted
        # display size isn't always exactly proportional to the image (most
        # visible for narrow/tall images) -- using a single width-derived
        # scale for both axes would drift image-space Y coordinates outside
        # the painted display. X and Y need their own scale factors.
        display = self._display_rect()
        return QPoint(
            display.x() + round(point.x() * self._scale_x()),
            display.y() + round(point.y() * self._scale_y()),
        )

    def _widget_to_image(self, point: QPoint) -> QPoint:
        display = self._display_rect()
        scale_x, scale_y = self._scale_x(), self._scale_y()
        if scale_x == 0 or scale_y == 0:
            return QPoint(0, 0)
        raw = QPoint(
            round((point.x() - display.x()) / scale_x),
            round((point.y() - display.y()) / scale_y),
        )
        return self._clamp_point_to_image(raw)

    def _clamp_point_to_image(self, point: QPoint) -> QPoint:
        x = max(0, min(point.x(), self._image.width()))
        y = max(0, min(point.y(), self._image.height()))
        return QPoint(x, y)

    def _clamp_to_image(self, rect: QRect) -> QRect:
        return clamp_rect_to_bounds(rect, self._image.width(), self._image.height())

    # ---- hit testing & pure geometry (unit-tested directly) -----------

    def _image_bottom_right_exclusive(self) -> QPoint:
        """The crop rect's bottom-right corner using the same exclusive
        convention (left+width, top+height) that resize_rect_from_handle
        uses, rather than QRect.bottomRight()'s inclusive
        (left+width-1, top+height-1). Using the inclusive corner here while
        the resize math treats right/bottom as exclusive made the painted
        br handle (and the hit-test rect built from it) sit about one
        image-pixel inside the true edge."""
        return QPoint(
            self._crop_rect.left() + self._crop_rect.width(),
            self._crop_rect.top() + self._crop_rect.height(),
        )

    def _handle_widget_rects(self) -> Dict[str, QRect]:
        top_left = self._image_to_widget(self._crop_rect.topLeft())
        bottom_right = self._image_to_widget(self._image_bottom_right_exclusive())
        mid_x = (top_left.x() + bottom_right.x()) // 2
        mid_y = (top_left.y() + bottom_right.y()) // 2
        centers = {
            "tl": QPoint(top_left.x(), top_left.y()), "tm": QPoint(mid_x, top_left.y()),
            "tr": QPoint(bottom_right.x(), top_left.y()),
            "ml": QPoint(top_left.x(), mid_y), "mr": QPoint(bottom_right.x(), mid_y),
            "bl": QPoint(top_left.x(), bottom_right.y()), "bm": QPoint(mid_x, bottom_right.y()),
            "br": QPoint(bottom_right.x(), bottom_right.y()),
        }
        half = _HANDLE_SIZE // 2 + _HIT_MARGIN
        return {name: QRect(c.x() - half, c.y() - half, half * 2, half * 2) for name, c in centers.items()}

    def _crop_widget_rect(self) -> QRect:
        """The crop rect in widget coordinates, built from an explicit
        (left, top, width, height) rather than the two-QPoint QRect
        constructor. That constructor treats its second point as an
        *inclusive* corner (Qt's normal QRect semantics), so feeding it the
        exclusive bottom-right point from _image_bottom_right_exclusive()
        would reintroduce a 1px inconsistency at the boundary -- using the
        width/height difference directly keeps the exclusive convention
        used throughout this file."""
        top_left = self._image_to_widget(self._crop_rect.topLeft())
        bottom_right = self._image_to_widget(self._image_bottom_right_exclusive())
        return QRect(top_left, QSize(bottom_right.x() - top_left.x(), bottom_right.y() - top_left.y()))

    def hit_test(self, widget_pos: QPoint) -> Optional[str]:
        """Returns a handle name, "body", or None. Exposed directly so tests
        don't need to synthesize QMouseEvents to check hit-testing alone."""
        handle_rects = self._handle_widget_rects()
        for name in _HANDLE_NAMES:
            if handle_rects[name].contains(widget_pos):
                return name
        if self._crop_widget_rect().contains(widget_pos):
            return "body"
        return None

    def resize_rect_from_handle(self, rect: QRect, handle: str, new_point: QPoint) -> QRect:
        """Pure function: returns rect with `handle` dragged to new_point
        (image coordinates), honoring the current aspect lock if any.

        Builds the new rect from continuous (exclusive) left/top/right/
        bottom bounds -- right = left + width, bottom = top + height --
        rather than via QRect.setRight()/setBottom(). Those Qt methods use
        the inclusive convention right() == left() + width() - 1, which
        would add a spurious +1 to width/height whenever the right or
        bottom edge is the one being dragged.
        """
        left, top = rect.left(), rect.top()
        right, bottom = rect.left() + rect.width(), rect.top() + rect.height()
        if "l" in handle:
            left = new_point.x()
        if "r" in handle:
            right = new_point.x()
        if "t" in handle:
            top = new_point.y()
        if "b" in handle:
            bottom = new_point.y()
        r = QRect(left, top, right - left, bottom - top).normalized()
        if self._aspect_lock:
            anchor = self._aspect_anchor(rect, handle)
            r = self._apply_aspect_lock(rect, r, handle, self._aspect_lock)
            return self._clamp_aspect_locked_rect(r, anchor, self._aspect_lock)
        return self._clamp_to_image(r)

    def _aspect_anchor(self, old_rect: QRect, handle: str) -> QPoint:
        """The point that stays fixed while `handle` is dragged with an
        aspect lock active -- the opposite corner for a corner handle, or
        the untouched edge intersected with the fixed axis for an edge-mid
        handle (e.g. "tm" fixes the left edge and the bottom edge, so its
        anchor is the old bottom-left corner). Shared by `_apply_aspect_lock`
        (to derive the locked rect) and `_clamp_aspect_locked_rect` (to keep
        that same point fixed when the locked rect has to shrink to fit the
        image bounds)."""
        anchor_x = old_rect.left() + old_rect.width() if "l" in handle else old_rect.left()
        anchor_y = old_rect.top() + old_rect.height() if "t" in handle else old_rect.top()
        return QPoint(anchor_x, anchor_y)

    def _apply_aspect_lock(self, old_rect: QRect, new_rect: QRect, handle: str, ratio: float) -> QRect:
        anchor = self._aspect_anchor(old_rect, handle)

        if handle in ("tm", "bm"):
            # Only the top/bottom edge is dragged; derive width from the
            # resulting height, anchored at the old left edge.
            height = max(1, new_rect.height())
            width = max(1, round(height * ratio))
        elif handle in ("ml", "mr"):
            # Only the left/right edge is dragged; derive height from the
            # resulting width, anchored at the old top edge.
            width = max(1, new_rect.width())
            height = max(1, round(width / ratio))
        else:
            # Corner handle: derive height from the dragged width, anchored
            # at the opposite corner so that corner stays fixed on screen.
            width = max(1, new_rect.width())
            height = max(1, round(width / ratio))

        left = anchor.x() - width if "l" in handle else anchor.x()
        top = anchor.y() - height if "t" in handle else anchor.y()
        return QRect(left, top, width, height)

    def _clamp_aspect_locked_rect(self, rect: QRect, anchor: QPoint, ratio: float) -> QRect:
        """Shrinks `rect` proportionally (preserving `ratio` exactly, up to
        rounding) so it fits within the image bounds, keeping `anchor` fixed
        on whichever side of the rect it lies.

        A plain intersection with the image bounds (as a free-form/unlocked
        drag uses) can turn an aspect-correct rect into an aspect-incorrect
        one whenever the locked rect extends past an edge -- e.g. locking to
        2:1 near the bottom-right corner of the image and dragging past it
        would otherwise silently produce a rect that no longer satisfies the
        lock. Scaling both dimensions down together instead preserves the
        ratio at the cost of a smaller (but still correctly-shaped) rect.
        """
        bounds_w = max(1, self._image.width())
        bounds_h = max(1, self._image.height())
        width = max(1, rect.width())
        height = max(1, rect.height())

        grows_right = rect.left() >= anchor.x()
        grows_down = rect.top() >= anchor.y()
        max_w = max(1, bounds_w - anchor.x() if grows_right else anchor.x())
        max_h = max(1, bounds_h - anchor.y() if grows_down else anchor.y())

        scale = min(1.0, max_w / width, max_h / height)
        new_width = max(1, round(width * scale))
        new_height = max(1, round(new_width / ratio))
        if new_height > max_h:
            new_height = max_h
            new_width = max(1, round(new_height * ratio))

        left = anchor.x() if grows_right else anchor.x() - new_width
        top = anchor.y() if grows_down else anchor.y() - new_height
        result = QRect(left, top, new_width, new_height)
        # Final unconditional bounds clamp: the math above derives a rect
        # that fits the image *given an in-bounds anchor*, but this is a
        # pure function exposed directly for tests (per the docstring
        # above), so it must hold the "stays within image bounds"
        # invariant even if ever called with an anchor that isn't
        # in-bounds, rather than relying on every caller to only ever pass
        # an anchor derived from an already-in-bounds rect.
        return self._clamp_to_image(result)

    def move_rect(self, rect: QRect, delta: QPoint) -> QRect:
        """Pure function: translates rect by delta (image coordinates),
        clamped so it stays fully within the image bounds."""
        moved = rect.translated(delta)
        bounds = QRect(0, 0, self._image.width(), self._image.height())
        if moved.left() < bounds.left():
            moved.moveLeft(bounds.left())
        if moved.top() < bounds.top():
            moved.moveTop(bounds.top())
        if moved.right() > bounds.right():
            moved.moveRight(bounds.right())
        if moved.bottom() > bounds.bottom():
            moved.moveBottom(bounds.bottom())
        return moved

    def _reflow_to_aspect(self, rect: QRect, ratio: float, preserve: str = "width") -> QRect:
        """Used when the aspect lock changes (or is re-applied after a
        spinbox edit): keeps the rect's top-left fixed, and keeps whichever
        of width/height `preserve` names fixed too, deriving the other
        dimension from the new ratio."""
        if preserve == "height":
            height = max(1, rect.height())
            width = max(1, round(height * ratio))
        else:
            width = max(1, rect.width())
            height = max(1, round(width / ratio))
        return QRect(rect.left(), rect.top(), width, height)

    # ---- Qt event handlers -------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        self._active_handle = self.hit_test(pos)
        if self._active_handle is not None:
            self._drag_start_widget_pos = pos
            self._drag_start_rect = QRect(self._crop_rect)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._active_handle is None or self._drag_start_widget_pos is None:
            return
        pos = event.position().toPoint()
        if self._active_handle == "body":
            start_img = self._widget_to_image(self._drag_start_widget_pos)
            current_img = self._widget_to_image(pos)
            delta = QPoint(current_img.x() - start_img.x(), current_img.y() - start_img.y())
            new_rect = self.move_rect(self._drag_start_rect, delta)
        else:
            new_point = self._widget_to_image(pos)
            new_rect = self.resize_rect_from_handle(self._drag_start_rect, self._active_handle, new_point)
        self._crop_rect = new_rect
        self.update()
        self.cropRectChanged.emit(self.crop_rect())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._active_handle = None
        self._drag_start_widget_pos = None

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()

    def _overlay_strip_rects(self, display: QRect, crop_widget_rect: QRect) -> tuple[QRect, QRect, QRect, QRect]:
        """The four dimming-overlay strips (top/bottom/left/right) that
        surround crop_widget_rect within display, in widget coordinates.

        crop_widget_rect follows this file's exclusive right/bottom
        convention (right = left + width, bottom = top + height), but
        QRect.right()/.bottom() are always Qt's *inclusive* accessors
        (left+width-1, top+height-1) regardless of how the rect was
        constructed -- using those directly here would darken the crop
        rect's own last row/column and leave the display's actual last
        row/column uncovered. Computes the true exclusive edges explicitly
        instead, and pulled out as its own pure method (rather than inlined
        in paintEvent) so this geometry is unit-testable without rendering."""
        crop_right = crop_widget_rect.left() + crop_widget_rect.width()
        crop_bottom = crop_widget_rect.top() + crop_widget_rect.height()

        top = QRect(display.left(), display.top(), display.width(), crop_widget_rect.top() - display.top())
        bottom = QRect(display.left(), crop_bottom, display.width(), display.bottom() - crop_bottom + 1)
        left = QRect(display.left(), crop_widget_rect.top(), crop_widget_rect.left() - display.left(), crop_widget_rect.height())
        right = QRect(crop_right, crop_widget_rect.top(), display.right() - crop_right + 1, crop_widget_rect.height())
        return top, bottom, left, right

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202020"))
        if self._image.isNull():
            return

        display = self._display_rect()
        painter.drawImage(display, self._image)

        crop_widget_rect = self._crop_widget_rect()

        overlay = QColor(0, 0, 0, 140)
        for strip in self._overlay_strip_rects(display, crop_widget_rect):
            painter.fillRect(strip, overlay)

        painter.setPen(QPen(QColor("white"), 1))
        painter.drawRect(crop_widget_rect)

        painter.setBrush(QBrush(QColor("white")))
        for handle_rect in self._handle_widget_rects().values():
            half = _HANDLE_SIZE // 2
            center = handle_rect.center()
            painter.drawRect(QRect(center.x() - half, center.y() - half, _HANDLE_SIZE, _HANDLE_SIZE))
