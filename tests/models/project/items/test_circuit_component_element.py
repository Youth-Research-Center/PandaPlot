import io
import math
from zipfile import ZipFile

from pandaplot.models.project.items.sketch import (
    SKETCH_ELEMENT_TYPES,
    CircuitComponentElement,
    Sketch,
    SketchElement,
)
from pandaplot.storage.sketch_data_manager import SketchDataManager


def test_circuit_component_element_defaults_and_serialization():
    comp_types = ["resistor", "capacitor", "inductor", "diode", "voltage_source", "ground"]
    for c_type in comp_types:
        elem = CircuitComponentElement(
            component_type=c_type,
            designator="R1",
            value="10k",
            flip_horizontal=True,
            flip_vertical=False,
        )
        data = elem.to_dict()
        assert data["type"] == "circuit_component"
        assert data["component_type"] == c_type
        assert data["designator"] == "R1"
        assert data["value"] == "10k"
        assert data["flip_horizontal"] is True
        assert data["flip_vertical"] is False

        deserialized = SketchElement.from_dict(data)
        assert isinstance(deserialized, CircuitComponentElement)
        assert deserialized.component_type == c_type
        assert deserialized.designator == "R1"
        assert deserialized.value == "10k"
        assert deserialized.flip_horizontal is True
        assert deserialized.flip_vertical is False
        assert len(deserialized.terminals) == len(elem.terminals)


def test_terminal_world_pos_rotation_and_flip():
    elem = CircuitComponentElement(
        x=100.0,
        y=50.0,
        rotation=90.0,
        flip_horizontal=True,
        flip_vertical=False,
        component_type="resistor",
    )
    t1_pos = elem.terminal_world_pos("t1")
    t2_pos = elem.terminal_world_pos("t2")

    assert math.isclose(t1_pos[0], 100.0, abs_tol=1e-5)
    assert math.isclose(t1_pos[1], 70.0, abs_tol=1e-5)
    assert math.isclose(t2_pos[0], 100.0, abs_tol=1e-5)
    assert math.isclose(t2_pos[1], 30.0, abs_tol=1e-5)


def test_circuit_component_seam_registration():
    assert "circuit_component" in SKETCH_ELEMENT_TYPES
    assert SKETCH_ELEMENT_TYPES["circuit_component"] is CircuitComponentElement


def test_sketch_data_manager_zip_round_trip_circuit_component():
    sketch = Sketch(name="Circuit Test Sketch")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(
        x=200, y=300, rotation=45, component_type="resistor", designator="R10", value="4.7k"
    )
    layer.elements.append(comp)

    buffer = io.BytesIO()
    manager = SketchDataManager()
    with ZipFile(buffer, "w") as zf:
        manager.save(sketch, zf, "sketch_data")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded_sketch = manager.load(Sketch, zf, "sketch_data", schema_version=1)

    assert loaded_sketch is not None
    assert loaded_sketch.name == "Circuit Test Sketch"
    loaded_layer = loaded_sketch.get_active_layer()
    assert len(loaded_layer.elements) == 1
    loaded_comp = loaded_layer.elements[0]
    assert isinstance(loaded_comp, CircuitComponentElement)
    assert loaded_comp.component_type == "resistor"
    assert loaded_comp.designator == "R10"
    assert loaded_comp.value == "4.7k"
    assert math.isclose(loaded_comp.x, 200)
    assert math.isclose(loaded_comp.y, 300)
    assert math.isclose(loaded_comp.rotation, 45)
