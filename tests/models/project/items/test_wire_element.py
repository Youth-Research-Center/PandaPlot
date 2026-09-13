import io
import math
from zipfile import ZipFile

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.sketch.sketch_commands import (
    ConnectWireCommand,
    MoveElementCommand,
    UpdateWireWaypointsCommand,
)
from pandaplot.models.project.items.sketch import (
    SKETCH_ELEMENT_TYPES,
    CircuitComponentElement,
    Sketch,
    SketchElement,
    WireElement,
)
from pandaplot.storage.sketch_data_manager import SketchDataManager


def test_wire_element_serialization_and_floating_endpoints():
    wire = WireElement(
        waypoints=[(0, 0), (100, 0), (100, 100)],
        start_ref=("c1", "t1"),
        end_ref=None,
    )
    data = wire.to_dict()
    assert data["type"] == "wire"
    assert data["waypoints"] == [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0]]
    assert data["start_ref"] == ["c1", "t1"]
    assert data["end_ref"] is None

    deserialized = SketchElement.from_dict(data)
    assert isinstance(deserialized, WireElement)
    assert deserialized.waypoints == [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
    assert deserialized.start_ref == ("c1", "t1")
    assert deserialized.end_ref is None


def test_wire_seam_registration():
    assert "wire" in SKETCH_ELEMENT_TYPES
    assert SKETCH_ELEMENT_TYPES["wire"] is WireElement


def test_wire_zip_round_trip():
    sketch = Sketch(name="Wire Test Sketch")
    layer = sketch.get_active_layer()
    wire = WireElement(
        waypoints=[(10, 20), (50, 20)],
        start_ref=("c1", "t1"),
        end_ref=("c2", "t2"),
    )
    layer.elements.append(wire)

    buffer = io.BytesIO()
    manager = SketchDataManager()
    with ZipFile(buffer, "w") as zf:
        manager.save(sketch, zf, "sketch_data")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded_sketch = manager.load(Sketch, zf, "sketch_data", schema_version=1)

    loaded_wire = loaded_sketch.get_active_layer().elements[0]
    assert isinstance(loaded_wire, WireElement)
    assert loaded_wire.start_ref == ("c1", "t1")
    assert loaded_wire.end_ref == ("c2", "t2")


def test_connect_and_disconnect_wire_commands():
    sketch = Sketch(name="Connect Wire Test")
    layer = sketch.get_active_layer()
    wire = WireElement(waypoints=[(0, 0), (100, 0)])
    layer.elements.append(wire)

    cmd = ConnectWireCommand(sketch, wire.id, "start", ("c1", "t1"))
    cmd.execute()
    assert wire.start_ref == ("c1", "t1")

    cmd.undo()
    assert wire.start_ref is None


def test_composite_move_component_with_wire_update():
    sketch = Sketch(name="Move Component with Wire Test")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(x=100, y=100, component_type="resistor")
    wire = WireElement(waypoints=[(80, 100), (0, 0)], start_ref=(comp.id, "t1"))
    layer.elements.extend([comp, wire])

    move_cmd = MoveElementCommand(sketch, comp.id, 200, 100)
    wire_cmd = UpdateWireWaypointsCommand(sketch, wire.id, [(180, 100), (0, 0)])

    composite = CompositeCommand([move_cmd, wire_cmd])
    executor = CommandExecutor()
    executor.execute_command(composite)

    assert math.isclose(comp.x, 200)
    assert wire.waypoints[0] == (180, 100)

    executor.undo()
    assert math.isclose(comp.x, 100)
    assert wire.waypoints[0] == (80, 100)
