from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.sketch.sketch_commands import (
    TransformCircuitComponentCommand,
    UpdateComponentLabelCommand,
)
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch


def test_transform_circuit_component_command():
    sketch = Sketch(name="Transform Test")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(x=100, y=100, rotation=0, component_type="resistor")
    layer.elements.append(comp)

    cmd = TransformCircuitComponentCommand(
        sketch, comp.id, rotation=90.0, flip_horizontal=True, flip_vertical=False
    )
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert comp.rotation == 90.0
    assert comp.flip_horizontal is True
    assert comp.flip_vertical is False

    undo_res = cmd.undo()
    assert undo_res == CommandResult.SUCCESS
    assert comp.rotation == 0.0
    assert comp.flip_horizontal is False

    noop_cmd = TransformCircuitComponentCommand(
        sketch, comp.id, rotation=0.0, flip_horizontal=False, flip_vertical=False
    )
    assert noop_cmd.execute() == CommandResult.NOOP


def test_update_component_label_command():
    sketch = Sketch(name="Label Test")
    layer = sketch.get_active_layer()
    c1 = CircuitComponentElement(component_type="resistor", designator="R1", value="10k")
    c2 = CircuitComponentElement(component_type="resistor", designator="R2", value="20k")
    layer.elements.extend([c1, c2])

    cmd = UpdateComponentLabelCommand(sketch, [c1.id, c2.id], value="100k")
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert c1.value == "100k"
    assert c2.value == "100k"
    assert c1.designator == "R1"
    assert c2.designator == "R2"

    cmd.undo()
    assert c1.value == "10k"
    assert c2.value == "20k"

    noop_cmd = UpdateComponentLabelCommand(sketch, [c1.id], value="10k")
    assert noop_cmd.execute() == CommandResult.NOOP
