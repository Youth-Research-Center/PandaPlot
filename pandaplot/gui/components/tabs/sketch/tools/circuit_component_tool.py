from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import CircuitComponentElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class CircuitComponentTool(BaseTool):
    """Tool for placing circuit components onto the sketch canvas."""

    def __init__(self, canvas: "SketchCanvas", component_type: str = "resistor"):
        super().__init__(ToolMode.CIRCUIT_COMPONENT, canvas)
        self.component_type: str = component_type

    def set_component_type(self, component_type: str) -> None:
        self.component_type = component_type

    def _generate_designator(self, comp_type: str) -> str:
        prefix_map = {
            "resistor": "R",
            "capacitor": "C",
            "inductor": "L",
            "diode": "D",
            "voltage_source": "V",
            "ground": "GND",
            "voltmeter": "VM",
            "ammeter": "AM",
        }
        prefix = prefix_map.get(comp_type, "K")
        if comp_type == "ground":
            return "GND"

        existing_indices = set()
        for layer in self.canvas.sketch.layers:
            for elem in layer.elements:
                if isinstance(elem, CircuitComponentElement) and elem.designator.startswith(prefix):
                    suffix = elem.designator[len(prefix):]
                    if suffix.isdigit():
                        existing_indices.add(int(suffix))

        idx = 1
        while idx in existing_indices:
            idx += 1
        return f"{prefix}{idx}"

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            layer = self.canvas.sketch.get_active_layer()
            if not layer or not layer.visible or layer.locked:
                return

            scene_pos = self.canvas.mapToScene(event.position().toPoint())
            designator = self._generate_designator(self.component_type)
            default_value_map = {
                "resistor": "10k",
                "capacitor": "100n",
                "inductor": "1m",
                "diode": "",
                "voltage_source": "5V",
                "ground": "",
                "voltmeter": "",
                "ammeter": "",
            }
            val = default_value_map.get(self.component_type, "")

            elem = CircuitComponentElement(
                x=scene_pos.x(),
                y=scene_pos.y(),
                stroke_color=self.canvas.active_stroke_color,
                stroke_width=self.canvas.active_stroke_width,
                stroke_style=self.canvas.active_stroke_style,
                fill_color=self.canvas.active_fill_color,
                component_type=self.component_type,
                designator=designator,
                value=val,
            )
            self.canvas.add_element_to_active_layer(elem)
