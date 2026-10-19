"""Base class, enums and type registry for the drawable elements of a Sketch.

Every element is positioned by an anchor (`x`, `y`) in canvas coordinates;
each concrete type stores the rest of its geometry relative to that anchor,
so moving an element only ever changes `x`/`y`.
"""
import logging
import math
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class StrokeStyle(StrEnum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DASH_DOT = "dash_dot"


class TextAlignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


def finite_float(value: Any) -> float | None:
    """Return `value` as a float if it is a finite real number, else None."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def parse_float(data: dict[str, Any], key: str, default: float, *, minimum: float | None = None) -> float:
    """Read a finite float from `data[key]`, falling back to `default` for a
    missing, non-numeric or non-finite value and clamping to `minimum`."""
    value = finite_float(data.get(key))
    if value is None:
        value = default
    if minimum is not None:
        value = max(value, minimum)
    return value


def parse_enum[E: StrEnum](enum_class: type[E], value: Any, default: E) -> E:
    """Convert `value` to `enum_class`, falling back to `default` for an
    unknown or invalid value."""
    try:
        return enum_class(value)
    except ValueError:
        return default


def parse_str(data: dict[str, Any], key: str, default: str) -> str:
    """Read a string from `data[key]`, falling back to `default`."""
    value = data.get(key, default)
    return value if isinstance(value, str) else default


@dataclass(kw_only=True)
class SketchElement:
    """A drawable element on a sketch layer.

    Concrete subclasses set `TYPE` (the persisted discriminator) and are
    registered in `ELEMENT_TYPES` so `from_dict()` can rebuild them.
    """

    TYPE: ClassVar[str] = ""
    # Fields that place and size the element (changed by move, resize and
    # rotate), as opposed to its style.
    GEOMETRY_FIELDS: ClassVar[frozenset[str]] = frozenset({"x", "y", "rotation"})

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    stroke_color: str = "#000000"
    stroke_width: float = 2.0
    stroke_style: StrokeStyle = StrokeStyle.SOLID
    fill_color: str | None = None

    def __post_init__(self) -> None:
        self.stroke_style = StrokeStyle(self.stroke_style)
        if self.stroke_width < 0:
            raise ValueError(f"stroke_width must be >= 0, got {self.stroke_width}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the element, including its `type` discriminator."""
        return {
            "id": self.id,
            "type": self.TYPE,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "stroke_style": self.stroke_style.value,
            "fill_color": self.fill_color,
            **self._geometry_to_dict(),
        }

    def _geometry_to_dict(self) -> dict[str, Any]:
        """Type-specific fields, merged into `to_dict()`."""
        return {}

    @classmethod
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Constructor kwargs for the type-specific fields in `data`."""
        return {}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SketchElement | None":
        """Rebuild an element from `to_dict()` output.

        Args:
            data: Serialized element.

        Returns:
            The concrete element, or None if `data` has an unknown `type`.
        """
        element_class = ELEMENT_TYPES.get(data.get("type"))
        if element_class is None:
            logger.warning("Skipping sketch element with unknown type %r", data.get("type"))
            return None
        fill_color = data.get("fill_color")
        kwargs: dict[str, Any] = {
            "x": parse_float(data, "x", 0.0),
            "y": parse_float(data, "y", 0.0),
            "rotation": parse_float(data, "rotation", 0.0),
            "stroke_color": parse_str(data, "stroke_color", "#000000"),
            "stroke_width": parse_float(data, "stroke_width", 2.0, minimum=0.0),
            "stroke_style": parse_enum(StrokeStyle, data.get("stroke_style"), StrokeStyle.SOLID),
            "fill_color": fill_color if isinstance(fill_color, str) else None,
            **element_class._geometry_from_dict(data),
        }
        if isinstance(data.get("id"), str):
            kwargs["id"] = data["id"]
        return element_class(**kwargs)


# Persisted `type` string -> element class. Concrete element modules add
# themselves here; a later element type registers by updating this dict.
ELEMENT_TYPES: dict[str, type[SketchElement]] = {}
