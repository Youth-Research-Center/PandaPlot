"""The element-type registry is the extension seam for new element types (#364).

A future module (e.g. circuit components) adds its element class to
ELEMENT_TYPES; loading and saving then handle it without any change to the
built-in element modules.
"""
from dataclasses import dataclass
from typing import Any, ClassVar, override

import pytest

from pandaplot.models.project.items.sketch import ELEMENT_TYPES, Sketch, SketchElement, SketchLayer
from pandaplot.models.project.items.sketch.sketch_element import parse_float


@dataclass(kw_only=True)
class ResistorElement(SketchElement):
    """A made-up element type, as a domain module would define it."""

    TYPE: ClassVar[str] = "test_resistor"
    GEOMETRY_FIELDS: ClassVar[frozenset[str]] = SketchElement.GEOMETRY_FIELDS | {"length"}

    length: float = 40.0

    @override
    def _geometry_to_dict(self) -> dict[str, Any]:
        return {"length": self.length}

    @classmethod
    @override
    def _geometry_from_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {"length": parse_float(data, "length", 40.0, minimum=0.0)}


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setitem(ELEMENT_TYPES, ResistorElement.TYPE, ResistorElement)


def test_a_registered_type_loads_from_its_dict(registered):
    element = SketchElement.from_dict({"type": "test_resistor", "id": "r1", "x": 5.0, "length": 60.0, "stroke_color": "#123456"})

    assert element == ResistorElement(id="r1", x=5.0, length=60.0, stroke_color="#123456")


def test_a_sketch_with_a_registered_type_round_trips(registered):
    sketch = Sketch(layers=[SketchLayer(elements=[ResistorElement(id="r1", length=25.0)])])

    restored = Sketch.from_dict(sketch.to_dict())

    assert restored.layers[0].elements == [ResistorElement(id="r1", length=25.0)]


def test_without_registration_the_type_is_skipped():
    assert "test_resistor" not in ELEMENT_TYPES
    assert SketchElement.from_dict({"type": "test_resistor", "length": 60.0}) is None
