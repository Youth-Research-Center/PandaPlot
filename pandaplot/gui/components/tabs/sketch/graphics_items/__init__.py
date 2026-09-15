from typing import Optional, Type

from pandaplot.gui.components.tabs.sketch.graphics_items.base_graphics_item import BaseGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.circuit_component_item import CircuitComponentGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.freehand_item import FreehandGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.line_item import LineGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.shape_items import (
    EllipseGraphicsItem,
    RectangleGraphicsItem,
)
from pandaplot.gui.components.tabs.sketch.graphics_items.text_item import TextGraphicsItem
from pandaplot.gui.components.tabs.sketch.graphics_items.wire_item import WireGraphicsItem
from pandaplot.models.project.items.sketch import (
    CircuitComponentElement,
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    SketchElement,
    TextElement,
    WireElement,
)

GRAPHICS_ITEM_MAPPING: dict[Type[SketchElement], Type[BaseGraphicsItem]] = {
    FreehandElement: FreehandGraphicsItem,
    LineElement: LineGraphicsItem,
    RectangleElement: RectangleGraphicsItem,
    EllipseElement: EllipseGraphicsItem,
    TextElement: TextGraphicsItem,
    CircuitComponentElement: CircuitComponentGraphicsItem,
    WireElement: WireGraphicsItem,
}


def create_graphics_item_for_element(element: SketchElement) -> Optional[BaseGraphicsItem]:
    cls = GRAPHICS_ITEM_MAPPING.get(type(element))
    if cls:
        return cls(element)
    return None


__all__ = [
    "BaseGraphicsItem",
    "CircuitComponentGraphicsItem",
    "FreehandGraphicsItem",
    "LineGraphicsItem",
    "RectangleGraphicsItem",
    "EllipseGraphicsItem",
    "TextGraphicsItem",
    "WireGraphicsItem",
    "create_graphics_item_for_element",
]
