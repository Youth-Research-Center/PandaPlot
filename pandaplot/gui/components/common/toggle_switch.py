from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

_TRACK_WIDTH = 26
_TRACK_HEIGHT = 15
_KNOB_DIAMETER = 11
_MARGIN = 2


def knob_x_for_state(*, checked: bool, track_width: int, knob_diameter: int, margin: int) -> int:
    """Left-edge x of the knob for a given on/off state."""
    if checked:
        return track_width - knob_diameter - margin
    return margin


class ToggleSwitch(QWidget):
    """26x15px pill toggle. On = accent bg + knob right; off = gray bg + knob left."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, *, checked: bool = False):
        super().__init__(parent)
        self._checked = checked
        self._tokens: dict = {}
        self.setFixedSize(_TRACK_WIDTH, _TRACK_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:  # noqa: N802 (Qt naming convention)
        return self._checked

    def setChecked(self, *, checked: bool):  # noqa: N802
        if checked == self._checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def set_tokens(self, tokens: dict):
        self._tokens = tokens
        self.update()

    def mousePressEvent(self, event: QMouseEvent):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(checked=not self._checked)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        on_color = QColor(self._tokens.get("accent", "#4A56C6"))
        off_color = QColor(self._tokens.get("border_panel", "#E5E6EA"))
        track_color = on_color if self._checked else off_color

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(
            QRectF(0, 0, _TRACK_WIDTH, _TRACK_HEIGHT), _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2
        )

        knob_x = knob_x_for_state(
            checked=self._checked,
            track_width=_TRACK_WIDTH,
            knob_diameter=_KNOB_DIAMETER,
            margin=_MARGIN,
        )
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(
            QRectF(knob_x, (_TRACK_HEIGHT - _KNOB_DIAMETER) / 2, _KNOB_DIAMETER, _KNOB_DIAMETER)
        )
