"""Holds the canvas's tools, the active one, and the style for new elements."""
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

from pandaplot.commands.base_command import Command
from pandaplot.commands.project.sketch import AddSketchElementCommand
from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool
from pandaplot.gui.components.tabs.sketch.tools.freehand_tool import FreehandTool
from pandaplot.gui.components.tabs.sketch.tools.select_tool import SelectTool
from pandaplot.gui.components.tabs.sketch.tools.shape_tools import EllipseTool, LineTool, RectangleTool
from pandaplot.gui.components.tabs.sketch.tools.text_tool import TextTool
from pandaplot.models.project.items.sketch import SketchElement, StrokeStyle
from pandaplot.models.project.items.sketch.elements import DEFAULT_FONT_FAMILY
from pandaplot.models.state.app_context import AppContext

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class ToolMode(StrEnum):
    SELECT = "select"
    FREEHAND = "freehand"
    LINE = "line"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    TEXT = "text"


TOOL_CLASSES: dict[ToolMode, type[BaseTool]] = {
    ToolMode.SELECT: SelectTool,
    ToolMode.FREEHAND: FreehandTool,
    ToolMode.LINE: LineTool,
    ToolMode.RECTANGLE: RectangleTool,
    ToolMode.ELLIPSE: EllipseTool,
    ToolMode.TEXT: TextTool,
}


@dataclass
class NewElementStyle:
    """Style given to newly drawn elements."""

    stroke_color: str = "#000000"
    stroke_width: float = 2.0
    stroke_style: StrokeStyle = StrokeStyle.SOLID
    fill_color: str | None = None
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = 18

    def shape_kwargs(self) -> dict[str, Any]:
        """Constructor arguments for a drawn shape or stroke."""
        return {
            "stroke_color": self.stroke_color, "stroke_width": self.stroke_width,
            "stroke_style": self.stroke_style, "fill_color": self.fill_color,
        }

    def text_kwargs(self) -> dict[str, Any]:
        """Constructor arguments for a text label, coloured by the stroke colour."""
        return {"stroke_color": self.stroke_color, "font_family": self.font_family, "font_size": self.font_size}


class ToolManager(QObject):
    """Routes canvas input to the active tool and lets tools change the
    model through the command executor."""

    tool_changed = Signal(object)

    def __init__(self, canvas: "SketchCanvas", app_context: AppContext):
        super().__init__(canvas)
        self.canvas = canvas
        self.app_context = app_context
        self.style = NewElementStyle()
        self._tools: dict[ToolMode, BaseTool] = {mode: tool_class(canvas, self) for mode, tool_class in TOOL_CLASSES.items()}
        self._mode = ToolMode.SELECT

    @property
    def mode(self) -> ToolMode:
        return self._mode

    @property
    def tool(self) -> BaseTool:
        return self._tools[self._mode]

    def set_tool(self, mode: ToolMode) -> None:
        """Make `mode` the active tool, abandoning any gesture in progress.
        The selection is cleared when leaving the selection tool."""
        if mode == self._mode:
            return
        self.tool.cancel()
        self._mode = mode
        if mode is not ToolMode.SELECT:
            self.canvas.clear_selection()
        self.canvas.viewport().setCursor(self.tool.cursor)
        self.tool_changed.emit(mode)

    def execute(self, command: Command) -> bool:
        """Run `command` through the executor; True if it changed the model."""
        return self.app_context.get_command_executor().execute_command(command)

    def drawing_blocked_reason(self) -> str | None:
        """Why new elements can't be drawn on the active layer, or None."""
        layer = self.canvas.sketch.active_layer
        if layer.locked:
            return f"Layer '{layer.name}' is locked. Unlock it to draw on it."
        if not layer.visible:
            return f"Layer '{layer.name}' is hidden. Show it to draw on it."
        return None

    def report_if_drawing_blocked(self) -> bool:
        """Tell the user, and return True, if the active layer can't be drawn on."""
        reason = self.drawing_blocked_reason()
        if reason is not None:
            self.canvas.status_message.emit(reason)
        return reason is not None

    def add_element(self, element: SketchElement) -> bool:
        """Add a newly drawn element to the active layer as one undo step."""
        sketch = self.canvas.sketch
        return self.execute(AddSketchElementCommand(self.app_context, sketch, sketch.active_layer_id, element))
