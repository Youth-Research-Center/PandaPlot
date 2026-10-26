"""Text tool: click to place a text label."""
from typing import override

from PySide6.QtCore import QPointF, Qt

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool
from pandaplot.models.project.items.sketch import TextElement


class TextTool(BaseTool):
    """Click where the label's top-left corner goes, then type its text.

    Editing the text of an existing label is not supported yet.
    """

    cursor = Qt.CursorShape.IBeamCursor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._anchor: QPointF | None = None

    @override
    def press(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        if self.manager.report_if_drawing_blocked():
            return
        self._anchor = pos

    @override
    def release(self, pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        anchor, self._anchor = self._anchor, None
        if anchor is None:
            return
        text = self.manager.app_context.get_ui_controller().get_text_input("Add Text", "Text:")
        if text is None or not text.strip():
            return
        self.manager.add_element(TextElement(x=anchor.x(), y=anchor.y(), text=text, **self.manager.style.text_kwargs()))

    @override
    def cancel(self) -> bool:
        was_placing = self._anchor is not None
        self._anchor = None
        return was_placing
