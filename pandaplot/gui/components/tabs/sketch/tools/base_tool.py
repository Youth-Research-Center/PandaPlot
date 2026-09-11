from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtGui import QKeyEvent, QMouseEvent

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class ToolMode(Enum):
    SELECT = auto()
    FREEHAND = auto()
    LINE = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    TEXT = auto()


class BaseTool(ABC):
    """Abstract base class for drawing tools."""

    def __init__(self, mode: ToolMode, canvas: "SketchCanvas"):
        self.mode: ToolMode = mode
        self.canvas: "SketchCanvas" = canvas

    @abstractmethod
    def mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press event."""
        pass

    def mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move event."""
        pass

    def mouse_release(self, event: QMouseEvent) -> None:
        """Handle mouse release event."""
        pass

    def key_press(self, event: QKeyEvent) -> None:
        """Handle key press event."""
        pass
