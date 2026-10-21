"""Base class of the sketch canvas tools."""
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
    from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolManager


class BaseTool:
    """One way of interacting with the canvas.

    The canvas sends a left-button press, the moves after it and the release
    to the active tool, in scene coordinates. A tool shows its work in
    progress through canvas previews and only changes the model on release,
    through a command, so each gesture is one undo step.
    """

    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas: "SketchCanvas", manager: "ToolManager"):
        self.canvas = canvas
        self.manager = manager

    def press(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        """The left button went down at `pos`."""

    def move(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        """The pointer moved to `pos` (with or without a button down)."""

    def release(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        """The left button went up at `pos`."""

    def key_press(self, event: QKeyEvent) -> bool:
        """Handle a key; return whether it was used."""
        return False

    def cancel(self) -> bool:
        """Abandon a gesture in progress, leaving the model unchanged.

        Returns:
            Whether a gesture was in progress.
        """
        return False
