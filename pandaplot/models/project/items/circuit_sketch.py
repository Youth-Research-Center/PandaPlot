from typing import Any, Dict, List, Optional

from pandaplot.models.project.items.sketch import Sketch, SketchLayer


class CircuitSketch(Sketch):
    """Circuit Sketch item representing an electronics schematic canvas with components and wires."""

    def __init__(
        self,
        id: Optional[str] = None,
        name: str = "Circuit Schematic",
        canvas_width: float = 1920.0,
        canvas_height: float = 1080.0,
        background_color: str = "#FFFFFF",
        active_layer_id: Optional[str] = None,
        layers: Optional[List[SketchLayer]] = None,
    ):
        super().__init__(
            id=id,
            name=name,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            background_color=background_color,
            active_layer_id=active_layer_id,
            layers=layers,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitSketch":
        item = cls(
            id=data.get("id"),
            name=data.get("name", "Circuit Schematic"),
            canvas_width=data.get("canvas_width", 1920.0),
            canvas_height=data.get("canvas_height", 1080.0),
            background_color=data.get("background_color", "#FFFFFF"),
            active_layer_id=data.get("active_layer_id"),
            layers=[SketchLayer.from_dict(layer_data) for layer_data in data.get("layers", [])],
        )
        item.parent_id = data.get("parent_id")
        item.created_at = data.get("created_at", item.created_at)
        item.modified_at = data.get("modified_at", item.modified_at)
        item.metadata = data.get("metadata", {})
        return item
