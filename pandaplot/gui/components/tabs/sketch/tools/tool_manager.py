from typing import TYPE_CHECKING, Dict

from PySide6.QtGui import QKeyEvent, QMouseEvent

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.gui.components.tabs.sketch.tools.freehand_tool import FreehandTool
from pandaplot.gui.components.tabs.sketch.tools.line_tool import LineTool
from pandaplot.gui.components.tabs.sketch.tools.select_tool import SelectTool
from pandaplot.gui.components.tabs.sketch.tools.shape_tools import EllipseTool, RectangleTool
from pandaplot.gui.components.tabs.sketch.tools.text_tool import TextTool

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class ToolManager:
    """Manages active tool state and routes user input events to active tool."""

    def __init__(self, canvas: "SketchCanvas"):
        self.canvas: "SketchCanvas" = canvas
        self.tools: Dict[ToolMode, BaseTool] = {
            ToolMode.SELECT: SelectTool(canvas),
            ToolMode.FREEHAND: FreehandTool(canvas),
            ToolMode.LINE: LineTool(canvas),
            ToolMode.RECTANGLE: RectangleTool(canvas),
            ToolMode.ELLIPSE: EllipseTool(canvas),
            ToolMode.TEXT: TextTool(canvas),
        }
        self.active_mode: ToolMode = ToolMode.SELECT

    @property
    def active_tool(self) -> BaseTool:
        return self.tools[self.active_mode]

    def set_mode(self, mode: ToolMode) -> None:
        self.active_mode = mode

    def mouse_press(self, event: QMouseEvent) -> None:
        self.active_tool.mouse_press(event)

    def mouse_move(self, event: QMouseEvent) -> None:
        self.active_tool.mouse_move(event)

    def mouse_release(self, event: QMouseEvent) -> None:
        self.active_tool.mouse_release(event)

    def key_press(self, event: QKeyEvent) -> None:
        self.active_tool.key_press(event)
