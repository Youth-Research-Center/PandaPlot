from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget

_TRACK_WIDTH = 26
_TRACK_HEIGHT = 15
_KNOB_DIAMETER = 11
_MARGIN = 2


def knob_x_for_state(*, checked: bool, track_width: int, knob_diameter: int, margin: int) -> int:
    """Left-edge x of the knob for a given on/off state."""
    if checked:
        return track_width - knob_diameter - margin
    return margin


class ToggleSwitch(QAbstractButton):
    """26x15px pill toggle. On = accent bg + knob right; off = gray bg + knob left.

    A checkable QAbstractButton, so it is keyboard-focusable, toggles on
    Space, and is exposed to assistive technology as a check/toggle button
    with its checked state. Callers should set an accessible name.
    """

    def __init__(self, parent: QWidget | None = None, *, checked: bool = False):
        super().__init__(parent)
        self.setCheckable(True)
        super().setChecked(checked)
        self._tokens: dict = {}
        self.setFixedSize(_TRACK_WIDTH, _TRACK_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setChecked(self, *, checked: bool):  # type: ignore[override]
        """Keyword-only to satisfy the FBT rules for callers; emits `toggled` on a change."""
        super().setChecked(checked)

    def set_tokens(self, tokens: dict):
        self._tokens = tokens
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        # QAbstractButton activates on Space; also accept Enter/Return.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        on_color = QColor(self._tokens.get("accent", "#4A56C6"))
        off_color = QColor(self._tokens.get("border_panel", "#E5E6EA"))
        track_color = on_color if self.isChecked() else off_color

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(
            QRectF(0, 0, _TRACK_WIDTH, _TRACK_HEIGHT), _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2
        )

        knob_x = knob_x_for_state(
            checked=self.isChecked(),
            track_width=_TRACK_WIDTH,
            knob_diameter=_KNOB_DIAMETER,
            margin=_MARGIN,
        )
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(
            QRectF(knob_x, (_TRACK_HEIGHT - _KNOB_DIAMETER) / 2, _KNOB_DIAMETER, _KNOB_DIAMETER)
        )
        if self.hasFocus():
            # The checked track is already the accent color, so the ring
            # needs a contrasting color there to stay visible.
            focus_key = "accent_active_text" if self.isChecked() else "accent"
            painter.setPen(QColor(self._tokens.get(focus_key, "#4A56C6")))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(0.5, 0.5, _TRACK_WIDTH - 1, _TRACK_HEIGHT - 1), _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2
            )
