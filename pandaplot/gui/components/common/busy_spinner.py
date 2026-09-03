"""BusySpinner: a small indeterminate activity indicator -- a rotating arc
drawn with QPainter, driven by an internal QTimer.

Used by panels that dispatch a long-running computation to TaskScheduler (see
AnalysisCommand/SignalAnalysisCommand/PerformFitCommand) to show "work is
happening" without a real percentage to report against -- those scipy calls
run as a single opaque step with no meaningful sub-progress. Hidden until
`.start()` is called so it takes no layout space while idle.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAccessible, QAccessibleEvent, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_TICK_INTERVAL_MS = 80
_DEGREES_PER_TICK = 30
_ARC_SPAN_DEGREES = 100
_ACCESSIBLE_NAME = "Busy indicator"
_ACCESSIBLE_DESCRIPTION_RUNNING = "Operation in progress"


class BusySpinner(QWidget):
    def __init__(self, color: str = "#4A90E2", diameter: int = 20, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color)
        self._diameter = diameter
        self._angle = 0
        self._running = False

        self.setFixedSize(diameter, diameter)
        self.setAccessibleName(_ACCESSIBLE_NAME)
        self.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def start(self) -> None:
        self._running = True
        self.setAccessibleDescription(_ACCESSIBLE_DESCRIPTION_RUNNING)
        self.setToolTip(_ACCESSIBLE_DESCRIPTION_RUNNING)
        self.show()
        self._timer.start()
        self._notify_accessibility_state_changed()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.hide()
        self.setAccessibleDescription("")
        self.setToolTip("")
        self._notify_accessibility_state_changed()

    def _notify_accessibility_state_changed(self) -> None:
        """Tell assistive technology the busy state changed -- the spinner
        is purely custom-painted (no built-in Qt widget conveys "working"),
        so screen readers get no equivalent feedback without this when
        surrounding controls become disabled during a background task."""
        QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Event.StateChanged))

    def _advance(self) -> None:
        self._angle = (self._angle + _DEGREES_PER_TICK) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ARG002 (Qt override signature)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_width = max(2, self._diameter // 8)
        pen = QPen(self._color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        rect = self.rect().adjusted(pen_width, pen_width, -pen_width, -pen_width)
        # QPainter angles are in 1/16th-degree units, measured counter-clockwise from 3 o'clock.
        painter.drawArc(rect, -self._angle * 16, _ARC_SPAN_DEGREES * 16)
        painter.end()
