from pandaplot.gui.components.tabs.sketch.tools.wire_tool import (
    find_snap_terminal,
    get_attached_wire_updates,
)
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch, WireElement


def test_find_snap_terminal():
    sketch = Sketch(name="Snap Test")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(x=100, y=100, component_type="resistor")
    layer.elements.append(comp)

    snap1 = find_snap_terminal((82, 102), sketch, radius_px=15.0)
    assert snap1 is not None
    assert snap1[0] == comp.id
    assert snap1[1] == "t1"
    assert snap1[2] == (80.0, 100.0)

    snap_far = find_snap_terminal((0, 0), sketch, radius_px=15.0)
    assert snap_far is None


def test_get_attached_wire_updates():
    sketch = Sketch(name="Wire Updates Test")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(x=100, y=100, component_type="resistor")
    wire = WireElement(waypoints=[(80, 100), (0, 0)], start_ref=(comp.id, "t1"))
    layer.elements.extend([comp, wire])

    comp.x = 200.0
    updates = get_attached_wire_updates(sketch, comp.id)

    assert len(updates) == 1
    wire_id, new_wps = updates[0]
    assert wire_id == wire.id
    assert new_wps[0] == (180.0, 100.0)
