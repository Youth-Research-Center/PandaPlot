from typing import Optional, Type

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.freehand_item import FreehandGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.line_item import LineGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.shape_items import (
    EllipseGraphicsItem,
    RectangleGraphicsItem,
)
from pandaplot.gui.components.tabs.sketch.graphics_items.text_item import TextGraphicsItem
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    SketchElement,
    TextElement,
)

GRAPHICS_ITEM_MAPPING: dict[Type[SketchElement], Type[BaseGraphicsItem]] = {
    FreehandElement: FreehandGraphicsItem,
    LineElement: LineGraphicsItem,
    RectangleElement: RectangleGraphicsItem,
    EllipseElement: EllipseGraphicsItem,
    TextElement: TextGraphicsItem,
}


def create_graphics_item_for_element(element: SketchElement) -> Optional[BaseGraphicsItem]:
    cls = GRAPHICS_ITEM_MAPPING.get(type(element))
    if cls:
        return cls(element)
    return None


__all__ = [
    "BaseGraphicsItem",
    "FreehandGraphicsItem",
    "LineGraphicsItem",
    "RectangleGraphicsItem",
    "EllipseGraphicsItem",
    "TextGraphicsItem",
    "create_graphics_item_for_element",
]
