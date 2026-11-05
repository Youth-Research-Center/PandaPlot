"""Sketch item: a vector drawing canvas made of ordered layers of elements."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, override

from pandaplot.models.project.items.item import Item
from pandaplot.models.project.items.sketch.sketch_element import SketchElement, parse_float, parse_str

DEFAULT_CANVAS_WIDTH = 1920.0
DEFAULT_CANVAS_HEIGHT = 1080.0
DEFAULT_BACKGROUND_COLOR = "#FFFFFF"
DEFAULT_LAYER_NAME = "Layer 1"


@dataclass(kw_only=True)
class SketchLayer:
    """An ordered stack of elements; index 0 is drawn first (bottom-most)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = DEFAULT_LAYER_NAME
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    elements: list[SketchElement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError(f"opacity must be between 0 and 1, got {self.opacity}")

    def get_element(self, element_id: str) -> SketchElement | None:
        """Return the element with `element_id`, or None."""
        return next((element for element in self.elements if element.id == element_id), None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the layer and its elements."""
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "elements": [element.to_dict() for element in self.elements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SketchLayer":
        """Rebuild a layer from `to_dict()` output, skipping unknown element types."""
        elements = []
        raw_elements = data.get("elements")
        for raw_element in raw_elements if isinstance(raw_elements, list) else []:
            element = SketchElement.from_dict(raw_element) if isinstance(raw_element, dict) else None
            if element is not None:
                elements.append(element)
        kwargs: dict[str, Any] = {
            "name": parse_str(data, "name", DEFAULT_LAYER_NAME),
            "visible": data.get("visible") is not False,
            "locked": data.get("locked") is True,
            "opacity": min(parse_float(data, "opacity", 1.0, minimum=0.0), 1.0),
            "elements": elements,
        }
        if isinstance(data.get("id"), str):
            kwargs["id"] = data["id"]
        return cls(**kwargs)


class Sketch(Item):
    """A drawing canvas holding ordered layers of vector elements.

    Layers are value data of the sketch (not project-tree items). Index 0
    of `layers` is the bottom-most layer. A sketch always has at least one
    layer, and `active_layer_id` always names one of them.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str = "",
        *,
        layers: list[SketchLayer] | None = None,
        active_layer_id: str | None = None,
        canvas_width: float = DEFAULT_CANVAS_WIDTH,
        canvas_height: float = DEFAULT_CANVAS_HEIGHT,
        background_color: str = DEFAULT_BACKGROUND_COLOR,
    ):
        super().__init__(id, name)
        if canvas_width <= 0 or canvas_height <= 0:
            raise ValueError(f"canvas size must be positive, got {canvas_width}x{canvas_height}")
        self.layers: list[SketchLayer] = list(layers) if layers else [SketchLayer()]
        self.active_layer_id: str = self.layers[-1].id
        if active_layer_id is not None and self.get_layer(active_layer_id) is not None:
            self.active_layer_id = active_layer_id
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.background_color = background_color

    @property
    def active_layer(self) -> SketchLayer:
        """The layer new elements are drawn on."""
        layer = self.get_layer(self.active_layer_id)
        assert layer is not None, "active_layer_id must always name an existing layer"
        return layer

    def get_layer(self, layer_id: str) -> SketchLayer | None:
        """Return the layer with `layer_id`, or None."""
        return next((layer for layer in self.layers if layer.id == layer_id), None)

    def layer_index(self, layer_id: str) -> int | None:
        """Return the stacking index of the layer with `layer_id`, or None."""
        return next((index for index, layer in enumerate(self.layers) if layer.id == layer_id), None)

    def add_layer(self, layer: SketchLayer, index: int | None = None) -> int:
        """Insert `layer` at `index` (default: on top) and return its index.

        Raises:
            ValueError: If a layer with the same id is already present.
        """
        if self.get_layer(layer.id) is not None:
            raise ValueError(f"Layer {layer.id!r} is already in sketch {self.id!r}")
        if index is None or index >= len(self.layers):
            index = len(self.layers)
        self.layers.insert(max(index, 0), layer)
        self.update_modified_time()
        return max(index, 0)

    def remove_layer(self, layer_id: str) -> tuple[SketchLayer, int]:
        """Remove a layer and return it with the index it held.

        If it was the active layer, the layer now at its position (or the
        new top layer) becomes active.

        Raises:
            KeyError: If no layer has `layer_id`.
            ValueError: If it is the only layer.
        """
        index = self.layer_index(layer_id)
        if index is None:
            raise KeyError(layer_id)
        if len(self.layers) == 1:
            raise ValueError("A sketch must keep at least one layer")
        layer = self.layers.pop(index)
        if self.active_layer_id == layer_id:
            self.active_layer_id = self.layers[min(index, len(self.layers) - 1)].id
        self.update_modified_time()
        return layer, index

    def move_layer(self, layer_id: str, new_index: int) -> int:
        """Move a layer to `new_index` (clamped to the valid range) and return
        the index it previously held.

        Raises:
            KeyError: If no layer has `layer_id`.
        """
        old_index = self.layer_index(layer_id)
        if old_index is None:
            raise KeyError(layer_id)
        new_index = min(max(new_index, 0), len(self.layers) - 1)
        if new_index != old_index:
            self.layers.insert(new_index, self.layers.pop(old_index))
            self.update_modified_time()
        return old_index

    def find_element(self, element_id: str) -> tuple[SketchLayer, SketchElement] | None:
        """Return the (layer, element) holding `element_id`, or None."""
        for layer in self.layers:
            element = layer.get_element(element_id)
            if element is not None:
                return layer, element
        return None

    def add_element(self, layer_id: str, element: SketchElement, index: int | None = None) -> int:
        """Insert `element` into a layer at `index` (default: on top) and
        return its index.

        Raises:
            KeyError: If no layer has `layer_id`.
            ValueError: If an element with the same id is already in the sketch.
        """
        layer = self.get_layer(layer_id)
        if layer is None:
            raise KeyError(layer_id)
        if self.find_element(element.id) is not None:
            raise ValueError(f"Element {element.id!r} is already in sketch {self.id!r}")
        if index is None or index >= len(layer.elements):
            index = len(layer.elements)
        index = max(index, 0)
        layer.elements.insert(index, element)
        self.update_modified_time()
        return index

    def remove_element(self, element_id: str) -> tuple[SketchLayer, SketchElement, int]:
        """Remove an element and return its layer, the element and the index
        it held, so it can be restored in place with `add_element()`.

        Raises:
            KeyError: If no element has `element_id`.
        """
        for layer in self.layers:
            for index, element in enumerate(layer.elements):
                if element.id == element_id:
                    del layer.elements[index]
                    self.update_modified_time()
                    return layer, element, index
        raise KeyError(element_id)

    @override
    def to_dict(self) -> dict[str, Any]:
        """Convert the sketch to a JSON-safe dictionary."""
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
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Sketch":
        """Create a sketch from `to_dict()` output.

        Missing or invalid fields fall back to their defaults, unknown
        element types are skipped, and a sketch with no layers gets a
        default one.
        """
        raw_layers = data.get("layers")
        layers = [SketchLayer.from_dict(raw) for raw in raw_layers if isinstance(raw, dict)] if isinstance(raw_layers, list) else []
        active_layer_id = data.get("active_layer_id")
        canvas_width = parse_float(data, "canvas_width", DEFAULT_CANVAS_WIDTH)
        canvas_height = parse_float(data, "canvas_height", DEFAULT_CANVAS_HEIGHT)
        sketch = cls(
            id=data.get("id"),
            name=data.get("name", ""),
            layers=layers,
            active_layer_id=active_layer_id if isinstance(active_layer_id, str) else None,
            canvas_width=canvas_width if canvas_width > 0 else DEFAULT_CANVAS_WIDTH,
            canvas_height=canvas_height if canvas_height > 0 else DEFAULT_CANVAS_HEIGHT,
            background_color=parse_str(data, "background_color", DEFAULT_BACKGROUND_COLOR),
        )
        sketch.parent_id = data.get("parent_id")
        sketch.created_at = data.get("created_at", datetime.now().isoformat())  # noqa: DTZ005 -- local-time display bookkeeping, never compared across timezones
        sketch.modified_at = data.get("modified_at", sketch.created_at)
        sketch.metadata = data.get("metadata", {})
        return sketch
