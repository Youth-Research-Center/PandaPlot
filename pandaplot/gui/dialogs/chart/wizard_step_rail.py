"""Shared step-rail widget for the chart creation wizard: a numbered-circle
row with connecting lines, showing the current step, completed steps (with
a clickable summary of what was chosen), and upcoming steps.

Each `ChartWizard` page owns its own `WizardStepRail` instance -- `QWizard`
swaps whole page widgets on navigation, so there's no single persistent
chrome region to share one instance through. `ChartWizard._on_page_changed`
keeps every page's rail in sync by calling `set_state` on whichever page is
current.
"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from pandaplot.gui.resources.icon_library import build_icon

_CIRCLE_SIZE = 17
_CHECK_SIZE = 10


def _circle_icon(state: str, number: int, tokens: dict) -> QIcon:
    """Paint a `_CIRCLE_SIZE`x`_CIRCLE_SIZE` circle for `state` ("current",
    "completed", or "upcoming"), matching the mockup's three treatments:
    indigo-filled + white number, light-indigo-bg + checkmark, or
    outlined + muted number. The completed checkmark is the bundled `check` icon.
    """
    accent = tokens.get("accent", "#4A56C6")
    muted = tokens.get("text_muted", "#9AA0AB")
    border = tokens.get("border_control", "#DCDEE4")
    completed_bg = tokens.get("accent_selected_bg", "#EEF0FB")
    completed_fg = tokens.get("accent_active_text", accent)

    pixmap = QPixmap(_CIRCLE_SIZE, _CIRCLE_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(0.5, 0.5, _CIRCLE_SIZE - 1, _CIRCLE_SIZE - 1)
    font = QFont()
    if state == "current":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(accent)))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#FFFFFF")))
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.Bold)
        text = str(number)
    elif state == "completed":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(completed_bg)))
        painter.drawEllipse(rect)
        check = build_icon("check", completed_fg, size=_CHECK_SIZE).pixmap(QSize(_CHECK_SIZE, _CHECK_SIZE))
        offset = (_CIRCLE_SIZE - _CHECK_SIZE) // 2
        painter.drawPixmap(offset, offset, check)
        text = ""
    else:
        painter.setPen(QPen(QColor(border)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(muted)))
        font.setPixelSize(10)
        text = str(number)

    if text:
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()

    # Register the painted pixmap for both Normal and Disabled modes: the
    # current and upcoming step buttons are (correctly) disabled to preserve
    # click-gating, but Qt's default icon engine auto-desaturates a
    # Normal-only QIcon for its Disabled rendering, which would grey out the
    # indigo-filled/outlined-muted colors this function just painted.
    icon = QIcon()
    icon.addPixmap(pixmap, QIcon.Mode.Normal)
    icon.addPixmap(pixmap, QIcon.Mode.Disabled)
    return icon


class WizardStepRail(QWidget):
    """Numbered-circle step row. `steps[i]` is the label for step `i`."""

    stepClicked = Signal(int)

    def __init__(self, steps: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        if not steps:
            raise ValueError("WizardStepRail requires at least one step")
        self._steps = steps
        self._tokens: dict = {}
        self._step_widgets: list[QPushButton] = []
        self._connectors: list[QFrame] = []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        for i, label in enumerate(steps):
            button = QPushButton(label, self)
            button.setFlat(True)
            button.setIconSize(QSize(_CIRCLE_SIZE, _CIRCLE_SIZE))
            button.clicked.connect(lambda _checked=False, idx=i: self._on_step_clicked(idx))
            self._layout.addWidget(button)
            self._step_widgets.append(button)
            if i < len(steps) - 1:
                connector = QFrame(self)
                connector.setFrameShape(QFrame.Shape.HLine)
                self._layout.addWidget(connector, 1)
                self._connectors.append(connector)

        self.set_state(current_index=0, summaries={})

    def _on_step_clicked(self, index: int):
        if index < self._current_index:
            self.stepClicked.emit(index)

    def set_state(self, current_index: int, summaries: dict[int, str]) -> None:
        """`summaries` maps a *completed* step's index (< current_index) to
        the "Label · chosen value" text its button should show. Steps with no
        entry keep their plain label."""
        self._current_index = current_index
        for i, button in enumerate(self._step_widgets):
            if i < current_index:
                button.setText(summaries.get(i, self._steps[i]))
                button.setEnabled(True)
                button.setProperty("stepState", "completed")
            elif i == current_index:
                button.setText(self._steps[i])
                button.setEnabled(False)
                button.setProperty("stepState", "current")
            else:
                button.setText(self._steps[i])
                button.setEnabled(False)
                button.setProperty("stepState", "upcoming")
            button.style().unpolish(button)
            button.style().polish(button)
        self._apply_styles()

    def set_tokens(self, tokens: dict) -> None:
        self._tokens = tokens
        self._apply_styles()

    def _apply_styles(self) -> None:
        border = self._tokens.get("border_control", "#DCDEE4")
        for i, button in enumerate(self._step_widgets):
            state = button.property("stepState")
            button.setIcon(_circle_icon(state, i + 1, self._tokens))
        for connector in self._connectors:
            connector.setStyleSheet(f"background-color: {border};")
