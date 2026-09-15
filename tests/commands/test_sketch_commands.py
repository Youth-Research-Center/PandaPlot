from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch.sketch_commands import (
    AddSketchElementCommand,
    DeleteSketchElementsCommand,
    UpdateSketchElementStyleCommand,
)
from pandaplot.models.project.items.sketch import RectangleElement, Sketch


def test_add_sketch_element_command():
    sketch = Sketch(name="Command Test")
    layer = sketch.get_active_layer()
    rect = RectangleElement(x=10, y=10, width=50, height=50)

    cmd = AddSketchElementCommand(sketch, layer.id, rect)
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert len(layer.elements) == 1
    assert layer.elements[0] is rect

    undo_res = cmd.undo()
    assert undo_res == CommandResult.SUCCESS
    assert len(layer.elements) == 0

    redo_res = cmd.redo()
    assert redo_res == CommandResult.SUCCESS
    assert len(layer.elements) == 1


def test_delete_sketch_elements_command():
    sketch = Sketch(name="Delete Command Test")
    layer = sketch.get_active_layer()
    r1 = RectangleElement(x=10, y=10, width=50, height=50)
    r2 = RectangleElement(x=100, y=100, width=50, height=50)
    layer.elements.extend([r1, r2])

    cmd = DeleteSketchElementsCommand(sketch, layer.id, [r1.id])
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert len(layer.elements) == 1
    assert layer.elements[0] is r2

    undo_res = cmd.undo()
    assert undo_res == CommandResult.SUCCESS
    assert len(layer.elements) == 2
    assert layer.elements[0] is r1


def test_update_sketch_element_style_command_noop_and_execute():
    sketch = Sketch(name="Style Command Test")
    layer = sketch.get_active_layer()
    r1 = RectangleElement(x=10, y=10, width=50, height=50, stroke_color="#000000")
    layer.elements.append(r1)

    noop_cmd = UpdateSketchElementStyleCommand(sketch, [r1.id], {"stroke_color": "#000000"})
    assert noop_cmd.execute() == CommandResult.NOOP

    cmd = UpdateSketchElementStyleCommand(sketch, [r1.id], {"stroke_color": "#FF0000", "stroke_width": 5.0})
    res = cmd.execute()
    assert res == CommandResult.SUCCESS
    assert r1.stroke_color == "#FF0000"
    assert r1.stroke_width == 5.0

    undo_res = cmd.undo()
    assert undo_res == CommandResult.SUCCESS
    assert r1.stroke_color == "#000000"
    assert r1.stroke_width == 2.0


def test_command_executor_ignores_noop():
    sketch = Sketch(name="Executor Test")
    layer = sketch.get_active_layer()
    r1 = RectangleElement(x=10, y=10, width=50, height=50, stroke_color="#000000")
    layer.elements.append(r1)

    executor = CommandExecutor()
    noop_cmd = UpdateSketchElementStyleCommand(sketch, [r1.id], {"stroke_color": "#000000"})
    executor.execute_command(noop_cmd)

    assert executor.can_undo() is False
