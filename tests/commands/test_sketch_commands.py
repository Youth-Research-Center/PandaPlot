from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch.sketch_commands import (
    AddSketchElementCommand,
    DeleteSketchElementsCommand,
    MoveResizeSketchElementsCommand,
    UpdateSketchElementStyleCommand,
)
from pandaplot.models.project.items.sketch import RectangleElement, Sketch


def test_move_resize_sketch_elements_command():
    sketch = Sketch(name="Move Command Test")
    layer = sketch.get_active_layer()
    rect = RectangleElement(x=10, y=10, width=50, height=50)
    layer.elements.append(rect)

    old_state = {rect.id: {"x": 10.0, "y": 10.0, "width": 50.0, "height": 50.0}}
    new_state = {rect.id: {"x": 100.0, "y": 150.0, "width": 120.0, "height": 80.0}}

    cmd = MoveResizeSketchElementsCommand(sketch, old_state, new_state)
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert rect.x == 100.0
    assert rect.y == 150.0
    assert rect.width == 120.0
    assert rect.height == 80.0

    undo_res = cmd.undo()
    assert undo_res == CommandResult.SUCCESS
    assert rect.x == 10.0
    assert rect.y == 10.0
    assert rect.width == 50.0
    assert rect.height == 50.0


def test_move_resize_command_noop():
    sketch = Sketch(name="Noop Move Test")
    layer = sketch.get_active_layer()
    rect = RectangleElement(x=10, y=10, width=50, height=50)
    layer.elements.append(rect)

    same_state = {rect.id: {"x": 10.0, "y": 10.0}}
    cmd = MoveResizeSketchElementsCommand(sketch, same_state, same_state)
    assert cmd.execute() == CommandResult.NOOP
