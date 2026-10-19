"""The five built-in sketch element types."""
from dataclasses import dataclass, field
from typing import Any, ClassVar, override

from pandaplot.models.project.items.sketch.sketch_element import (
    ELEMENT_TYPES,
    SketchElement,
    TextAlignment,
    finite_float,
    parse_enum,
    parse_float,
    parse_str,
)


@dataclass(kw_only=True)
class FreehandElement(SketchElement):
    """A pen stroke: a polyline through `points`, each relative to (`x`, `y`)."""

    TYPE: ClassVar[str] = "freehand"

    points: list[tuple[float, float]] = field(default_factory=list)

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {"points": [[px, py] for px, py in self.points]}

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        points = []
        raw_points = data.get("points")
        for point in raw_points if isinstance(raw_points, list) else []:
            if isinstance(point, list | tuple) and len(point) == 2:
                px, py = finite_float(point[0]), finite_float(point[1])
                if px is not None and py is not None:
                    points.append((px, py))
        return {"points": points}


@dataclass(kw_only=True)
class LineElement(SketchElement):
    """A straight line from (`x`, `y`) to (`x + dx`, `y + dy`)."""

    TYPE: ClassVar[str] = "line"

    dx: float = 0.0
    dy: float = 0.0

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {"dx": self.dx, "dy": self.dy}

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {"dx": parse_float(data, "dx", 0.0), "dy": parse_float(data, "dy", 0.0)}


@dataclass(kw_only=True)
class RectangleElement(SketchElement):
    """A rectangle with its top-left corner at (`x`, `y`)."""

    TYPE: ClassVar[str] = "rectangle"

    width: float = 0.0
    height: float = 0.0
    corner_radius: float = 0.0

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.width < 0 or self.height < 0 or self.corner_radius < 0:
            raise ValueError(f"width, height and corner_radius must be >= 0, got {self.width}, {self.height}, {self.corner_radius}")

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {"width": self.width, "height": self.height, "corner_radius": self.corner_radius}

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "width": parse_float(data, "width", 0.0, minimum=0.0),
            "height": parse_float(data, "height", 0.0, minimum=0.0),
            "corner_radius": parse_float(data, "corner_radius", 0.0, minimum=0.0),
        }


@dataclass(kw_only=True)
class EllipseElement(SketchElement):
    """An ellipse centred on (`x`, `y`) with radii `rx` and `ry`."""

    TYPE: ClassVar[str] = "ellipse"

    rx: float = 0.0
    ry: float = 0.0

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.rx < 0 or self.ry < 0:
            raise ValueError(f"rx and ry must be >= 0, got {self.rx}, {self.ry}")

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {"rx": self.rx, "ry": self.ry}

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {"rx": parse_float(data, "rx", 0.0, minimum=0.0), "ry": parse_float(data, "ry", 0.0, minimum=0.0)}


@dataclass(kw_only=True)
class TextElement(SketchElement):
    """A text label with its top-left corner at (`x`, `y`)."""

    TYPE: ClassVar[str] = "text"

    text: str = ""
    font_family: str = "Sans Serif"
    font_size: int = 14
    is_bold: bool = False
    is_italic: bool = False
    alignment: TextAlignment = TextAlignment.LEFT

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        self.alignment = TextAlignment(self.alignment)
        if self.font_size <= 0:
            raise ValueError(f"font_size must be > 0, got {self.font_size}")

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "alignment": self.alignment.value,
        }

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        font_size = data.get("font_size")
        return {
            "text": parse_str(data, "text", ""),
            "font_family": parse_str(data, "font_family", "Sans Serif"),
            "font_size": font_size if isinstance(font_size, int) and not isinstance(font_size, bool) and font_size > 0 else 14,
            "is_bold": data.get("is_bold") is True,
            "is_italic": data.get("is_italic") is True,
            "alignment": parse_enum(TextAlignment, data.get("alignment"), TextAlignment.LEFT),
        }


ELEMENT_TYPES.update({
    element_class.TYPE: element_class
    for element_class in (FreehandElement, LineElement, RectangleElement, EllipseElement, TextElement)
})
