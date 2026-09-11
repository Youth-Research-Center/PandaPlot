import math
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

from pandaplot.models.project.items.item import Item


class SketchElement(ABC):
    """Abstract base class for elements within a sketch layer."""

    type: str = ""

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
    ):
        self.id: str = id if id else str(uuid.uuid4())
        self.x: float = float(x)
        self.y: float = float(y)
        self.rotation: float = float(rotation)
        self.stroke_color: str = stroke_color
        self.stroke_width: float = float(stroke_width)
        self.stroke_style: str = stroke_style
        self.fill_color: str = fill_color

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "stroke_style": self.stroke_style,
            "fill_color": self.fill_color,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SketchElement":
        elem_type = data.get("type")
        elem_cls = SKETCH_ELEMENT_TYPES.get(elem_type)
        if elem_cls is None:
            raise ValueError(f"Unknown SketchElement type: {elem_type}")
        return elem_cls._from_dict_concrete(data)

    @classmethod
    @abstractmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "SketchElement":
        pass


class FreehandElement(SketchElement):
    type = "freehand"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        points: Optional[List[Tuple[float, float]]] = None,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.points: List[Tuple[float, float]] = [
            (float(p[0]), float(p[1])) for p in (points or [])
        ]

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["points"] = [list(p) for p in self.points]
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "FreehandElement":
        points_raw = data.get("points", [])
        points = [(float(p[0]), float(p[1])) for p in points_raw]
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            points=points,
        )


class LineElement(SketchElement):
    type = "line"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 0.0,
        y2: float = 0.0,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.x1: float = float(x1)
        self.y1: float = float(y1)
        self.x2: float = float(x2)
        self.y2: float = float(y2)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2})
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "LineElement":
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            x1=data.get("x1", 0.0),
            y1=data.get("y1", 0.0),
            x2=data.get("x2", 0.0),
            y2=data.get("y2", 0.0),
        )


class RectangleElement(SketchElement):
    type = "rectangle"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        width: float = 100.0,
        height: float = 100.0,
        corner_radius: float = 0.0,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.width: float = float(width)
        self.height: float = float(height)
        self.corner_radius: float = float(corner_radius)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "width": self.width,
            "height": self.height,
            "corner_radius": self.corner_radius,
        })
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "RectangleElement":
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            width=data.get("width", 100.0),
            height=data.get("height", 100.0),
            corner_radius=data.get("corner_radius", 0.0),
        )


class EllipseElement(SketchElement):
    type = "ellipse"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        rx: float = 50.0,
        ry: float = 50.0,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.rx: float = float(rx)
        self.ry: float = float(ry)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"rx": self.rx, "ry": self.ry})
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "EllipseElement":
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            rx=data.get("rx", 50.0),
            ry=data.get("ry", 50.0),
        )


class TextElement(SketchElement):
    type = "text"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        text: str = "",
        font_family: str = "Sans-Serif",
        font_size: int = 14,
        is_bold: bool = False,
        is_italic: bool = False,
        alignment: str = "left",
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.text: str = text
        self.font_family: str = font_family
        self.font_size: int = int(font_size)
        self.is_bold: bool = bool(is_bold)
        self.is_italic: bool = bool(is_italic)
        self.alignment: str = alignment

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "text": self.text,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "alignment": self.alignment,
        })
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "TextElement":
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            text=data.get("text", ""),
            font_family=data.get("font_family", "Sans-Serif"),
            font_size=data.get("font_size", 14),
            is_bold=data.get("is_bold", False),
            is_italic=data.get("is_italic", False),
            alignment=data.get("alignment", "left"),
        )


class Terminal:
    """Terminal connection point for a circuit component."""

    def __init__(self, id: str, dx: float, dy: float):
        self.id: str = id
        self.dx: float = float(dx)
        self.dy: float = float(dy)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "dx": self.dx, "dy": self.dy}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Terminal":
        return cls(id=data["id"], dx=float(data["dx"]), dy=float(data["dy"]))


def get_default_terminals_for_type(component_type: str) -> List[Terminal]:
    if component_type == "ground":
        return [Terminal("t1", 0.0, -10.0)]
    return [Terminal("t1", -20.0, 0.0), Terminal("t2", 20.0, 0.0)]


class CircuitComponentElement(SketchElement):
    type = "circuit_component"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        component_type: str = "resistor",
        terminals: Optional[List[Terminal]] = None,
        flip_horizontal: bool = False,
        flip_vertical: bool = False,
        designator: str = "",
        value: str = "",
        label_visible: bool = True,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.component_type: str = component_type
        if terminals is None:
            self.terminals: List[Terminal] = get_default_terminals_for_type(component_type)
        else:
            self.terminals = terminals
        self.flip_horizontal: bool = bool(flip_horizontal)
        self.flip_vertical: bool = bool(flip_vertical)
        self.designator: str = designator
        self.value: str = value
        self.label_visible: bool = bool(label_visible)

    def terminal_world_pos(self, terminal_id: str) -> Tuple[float, float]:
        term = next((t for t in self.terminals if t.id == terminal_id), None)
        if term is None:
            raise ValueError(f"Terminal '{terminal_id}' not found on component '{self.id}'")

        dx_flipped = -term.dx if self.flip_horizontal else term.dx
        dy_flipped = -term.dy if self.flip_vertical else term.dy

        rad = math.radians(self.rotation)
        x_rot = dx_flipped * math.cos(rad) - dy_flipped * math.sin(rad)
        y_rot = dx_flipped * math.sin(rad) + dy_flipped * math.cos(rad)

        return (self.x + x_rot, self.y + y_rot)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "component_type": self.component_type,
            "terminals": [t.to_dict() for t in self.terminals],
            "flip_horizontal": self.flip_horizontal,
            "flip_vertical": self.flip_vertical,
            "designator": self.designator,
            "value": self.value,
            "label_visible": self.label_visible,
        })
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "CircuitComponentElement":
        terminals_raw = data.get("terminals")
        terminals = [Terminal.from_dict(t) for t in terminals_raw] if terminals_raw is not None else None
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            component_type=data.get("component_type", "resistor"),
            terminals=terminals,
            flip_horizontal=data.get("flip_horizontal", False),
            flip_vertical=data.get("flip_vertical", False),
            designator=data.get("designator", ""),
            value=data.get("value", ""),
            label_visible=data.get("label_visible", True),
        )


class WireElement(SketchElement):
    type = "wire"

    def __init__(
        self,
        id: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        stroke_style: str = "solid",
        fill_color: str = "none",
        waypoints: Optional[List[Tuple[float, float]]] = None,
        start_ref: Optional[Tuple[str, str]] = None,
        end_ref: Optional[Tuple[str, str]] = None,
    ):
        super().__init__(id, x, y, rotation, stroke_color, stroke_width, stroke_style, fill_color)
        self.waypoints: List[Tuple[float, float]] = [
            (float(p[0]), float(p[1])) for p in (waypoints or [])
        ]
        self.start_ref: Optional[Tuple[str, str]] = (
            (str(start_ref[0]), str(start_ref[1])) if start_ref else None
        )
        self.end_ref: Optional[Tuple[str, str]] = (
            (str(end_ref[0]), str(end_ref[1])) if end_ref else None
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "waypoints": [list(p) for p in self.waypoints],
            "start_ref": list(self.start_ref) if self.start_ref else None,
            "end_ref": list(self.end_ref) if self.end_ref else None,
        })
        return d

    @classmethod
    def _from_dict_concrete(cls, data: Dict[str, Any]) -> "WireElement":
        waypoints_raw = data.get("waypoints", [])
        waypoints = [(float(p[0]), float(p[1])) for p in waypoints_raw]
        start_raw = data.get("start_ref")
        start_ref = (str(start_raw[0]), str(start_raw[1])) if start_raw else None
        end_raw = data.get("end_ref")
        end_ref = (str(end_raw[0]), str(end_raw[1])) if end_raw else None
        return cls(
            id=data.get("id"),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            stroke_color=data.get("stroke_color", "#000000"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_style=data.get("stroke_style", "solid"),
            fill_color=data.get("fill_color", "none"),
            waypoints=waypoints,
            start_ref=start_ref,
            end_ref=end_ref,
        )


SKETCH_ELEMENT_TYPES: Dict[str, Type[SketchElement]] = {
    "freehand": FreehandElement,
    "line": LineElement,
    "rectangle": RectangleElement,
    "ellipse": EllipseElement,
    "text": TextElement,
    "circuit_component": CircuitComponentElement,
    "wire": WireElement,
}


class SketchLayer:
    """Layer within a Sketch containing elements."""

    def __init__(
        self,
        id: Optional[str] = None,
        name: str = "Layer 1",
        visible: bool = True,
        locked: bool = False,
        opacity: float = 1.0,
        elements: Optional[List[SketchElement]] = None,
    ):
        self.id: str = id if id else str(uuid.uuid4())
        self.name: str = name
        self.visible: bool = bool(visible)
        self.locked: bool = bool(locked)
        self.opacity: float = float(opacity)
        self.elements: List[SketchElement] = elements if elements is not None else []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "elements": [elem.to_dict() for elem in self.elements],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SketchLayer":
        elements_data = data.get("elements", [])
        elements = [SketchElement.from_dict(elem_data) for elem_data in elements_data]
        return cls(
            id=data.get("id"),
            name=data.get("name", "Layer 1"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            elements=elements,
        )


class Sketch(Item):
    """Sketch item representing a vector drawing canvas with layers."""

    def __init__(
        self,
        id: Optional[str] = None,
        name: str = "Sketch",
        canvas_width: float = 1920.0,
        canvas_height: float = 1080.0,
        background_color: str = "#FFFFFF",
        active_layer_id: Optional[str] = None,
        layers: Optional[List[SketchLayer]] = None,
    ):
        super().__init__(id, name)
        self.canvas_width: float = float(canvas_width)
        self.canvas_height: float = float(canvas_height)
        self.background_color: str = background_color

        if layers is None:
            default_layer = SketchLayer(name="Layer 1")
            self.layers: List[SketchLayer] = [default_layer]
            self.active_layer_id: str = default_layer.id
        else:
            self.layers = layers
            if active_layer_id:
                self.active_layer_id = active_layer_id
            elif self.layers:
                self.active_layer_id = self.layers[0].id
            else:
                self.active_layer_id = ""

    def get_layer(self, layer_id: str) -> Optional[SketchLayer]:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_active_layer(self) -> Optional[SketchLayer]:
        return self.get_layer(self.active_layer_id)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "background_color": self.background_color,
            "active_layer_id": self.active_layer_id,
            "layers": [layer.to_dict() for layer in self.layers],
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sketch":
        item = cls(
            id=data.get("id"),
            name=data.get("name", "Sketch"),
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
