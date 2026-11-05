"""Tests for the undoable sketch element commands."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch import (
    AddSketchElementCommand,
    DeleteSketchElementsCommand,
    TransformSketchElementsCommand,
)
from pandaplot.models.events import EventBus, SketchEvents
from pandaplot.models.events.event_data import SketchChangedData
from pandaplot.models.events.event_types import EventHierarchy
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    SketchLayer,
)


@pytest.fixture
def events() -> list[dict]:
    return []


@pytest.fixture
def app_context(events):
    event_bus = EventBus()
    event_bus.subscribe(SketchEvents.SKETCH_CHANGED, events.append)
    context = Mock()
    context.event_bus = event_bus
    return context


@pytest.fixture
def sketch() -> Sketch:
    return Sketch(id="sketch-1", layers=[
        SketchLayer(id="a", elements=[LineElement(id="a1"), LineElement(id="a2"), LineElement(id="a3"), LineElement(id="a4")]),
        SketchLayer(id="b", elements=[RectangleElement(id="b1", width=10.0, height=10.0), EllipseElement(id="b2", rx=5.0, ry=5.0)]),
    ])


def _ids(sketch: Sketch, layer_id: str) -> list[str]:
    layer = sketch.get_layer(layer_id)
    assert layer is not None
    return [element.id for element in layer.elements]


def test_sketch_changed_is_a_standalone_event():
    assert EventHierarchy.get_hierarchy(SketchEvents.SKETCH_CHANGED) == [SketchEvents.SKETCH_CHANGED]


class TestAddSketchElementCommand:
    def test_execute_adds_on_top_and_announces_the_change(self, app_context, sketch, events):
        command = AddSketchElementCommand(app_context, sketch, "b", LineElement(id="new"))

        assert command.execute() is CommandResult.SUCCESS

        assert _ids(sketch, "b") == ["b1", "b2", "new"]
        assert [SketchChangedData.from_dict(event) for event in events] == [SketchChangedData(sketch_id="sketch-1")]

    def test_execute_inserts_at_index(self, app_context, sketch):
        AddSketchElementCommand(app_context, sketch, "a", LineElement(id="new"), index=1).execute()

        assert _ids(sketch, "a") == ["a1", "new", "a2", "a3", "a4"]

    def test_undo_removes_and_redo_restores_the_same_object_at_the_same_index(self, app_context, sketch, events):
        element = LineElement(id="new")
        command = AddSketchElementCommand(app_context, sketch, "a", element, index=2)
        command.execute()

        assert command.undo() is CommandResult.SUCCESS
        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]

        assert command.redo() is CommandResult.SUCCESS
        assert _ids(sketch, "a") == ["a1", "a2", "new", "a3", "a4"]
        found = sketch.find_element("new")
        assert found is not None
        assert found[1] is element
        assert len(events) == 3

    @pytest.mark.parametrize("layer_id", ["missing", "locked"])
    def test_execute_fails_without_change_on_missing_or_locked_layer(self, app_context, sketch, events, layer_id):
        sketch.add_layer(SketchLayer(id="locked", locked=True))
        command = AddSketchElementCommand(app_context, sketch, layer_id, LineElement(id="new"))

        assert command.execute() is CommandResult.FAILURE

        assert sketch.find_element("new") is None
        assert events == []
        assert command.undo() is CommandResult.FAILURE
        assert command.redo() is CommandResult.FAILURE

    def test_execute_fails_for_a_duplicate_id(self, app_context, sketch):
        command = AddSketchElementCommand(app_context, sketch, "a", LineElement(id="b1"))

        assert command.execute() is CommandResult.FAILURE
        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]

    def test_undo_fails_if_the_element_is_already_gone(self, app_context, sketch):
        command = AddSketchElementCommand(app_context, sketch, "a", LineElement(id="new"))
        command.execute()
        sketch.remove_element("new")

        assert command.undo() is CommandResult.FAILURE


class TestDeleteSketchElementsCommand:
    def test_execute_deletes_across_layers(self, app_context, sketch, events):
        command = DeleteSketchElementsCommand(app_context, sketch, ["a2", "b1", "a4"])

        assert command.execute() is CommandResult.SUCCESS

        assert _ids(sketch, "a") == ["a1", "a3"]
        assert _ids(sketch, "b") == ["b2"]
        assert [SketchChangedData.from_dict(event) for event in events] == [SketchChangedData(sketch_id="sketch-1")]

    def test_undo_restores_original_indices_not_appended(self, app_context, sketch):
        command = DeleteSketchElementsCommand(app_context, sketch, ["a4", "a1", "a3", "b1"])
        command.execute()

        assert command.undo() is CommandResult.SUCCESS

        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]
        assert _ids(sketch, "b") == ["b1", "b2"]

    def test_redo_deletes_the_same_elements_again(self, app_context, sketch):
        originals = {element_id: sketch.find_element(element_id) for element_id in ("a2", "b2")}
        command = DeleteSketchElementsCommand(app_context, sketch, ["a2", "b2"])
        command.execute()
        command.undo()

        assert command.redo() is CommandResult.SUCCESS
        assert _ids(sketch, "a") == ["a1", "a3", "a4"]
        assert _ids(sketch, "b") == ["b1"]

        command.undo()
        for element_id, (_layer, element) in originals.items():
            found = sketch.find_element(element_id)
            assert found is not None
            assert found[1] is element

    def test_empty_selection_is_a_noop(self, app_context, sketch, events):
        assert DeleteSketchElementsCommand(app_context, sketch, []).execute() is CommandResult.NOOP
        assert events == []

    def test_missing_element_fails_without_deleting_anything(self, app_context, sketch, events):
        command = DeleteSketchElementsCommand(app_context, sketch, ["a1", "missing"])

        assert command.execute() is CommandResult.FAILURE

        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]
        assert events == []

    def test_element_on_a_locked_layer_fails_without_deleting_anything(self, app_context, sketch):
        layer_b = sketch.get_layer("b")
        assert layer_b is not None
        layer_b.locked = True

        assert DeleteSketchElementsCommand(app_context, sketch, ["a1", "b1"]).execute() is CommandResult.FAILURE

        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]
        assert _ids(sketch, "b") == ["b1", "b2"]

    def test_undo_fails_without_change_if_an_element_is_already_back(self, app_context, sketch):
        command = DeleteSketchElementsCommand(app_context, sketch, ["a1", "a2"])
        command.execute()
        sketch.add_element("a", LineElement(id="a2"))

        assert command.undo() is CommandResult.FAILURE
        assert _ids(sketch, "a") == ["a3", "a4", "a2"]

    def test_cleanup_drops_the_deleted_elements(self, app_context, sketch):
        command = DeleteSketchElementsCommand(app_context, sketch, ["a1"])
        command.execute()

        command.cleanup()

        assert command.undo() is CommandResult.FAILURE


class TestTransformSketchElementsCommand:
    def test_execute_moves_several_elements_in_one_step(self, app_context, sketch, events):
        command = TransformSketchElementsCommand(app_context, sketch, {"a1": {"x": 5.0, "y": 6.0}, "b1": {"x": 7.0}})

        assert command.execute() is CommandResult.SUCCESS

        a1 = sketch.find_element("a1")
        b1 = sketch.find_element("b1")
        assert a1 is not None and b1 is not None
        assert (a1[1].x, a1[1].y, b1[1].x) == (5.0, 6.0, 7.0)
        assert [SketchChangedData.from_dict(event) for event in events] == [SketchChangedData(sketch_id="sketch-1")]

    def test_undo_and_redo_restore_each_state(self, app_context, sketch):
        command = TransformSketchElementsCommand(app_context, sketch, {"b1": {"x": 3.0, "width": 50.0, "rotation": 45.0}})
        command.execute()
        found = sketch.find_element("b1")
        assert found is not None
        rectangle = found[1]
        assert isinstance(rectangle, RectangleElement)

        assert command.undo() is CommandResult.SUCCESS
        assert (rectangle.x, rectangle.width, rectangle.rotation) == (0.0, 10.0, 0.0)

        assert command.redo() is CommandResult.SUCCESS
        assert (rectangle.x, rectangle.width, rectangle.rotation) == (3.0, 50.0, 45.0)

    def test_freehand_points_are_copied_not_shared(self, app_context, sketch):
        stroke = FreehandElement(id="f", points=[(0.0, 0.0), (1.0, 1.0)])
        sketch.add_element("a", stroke)
        new_points = [(0.0, 0.0), (2.0, 2.0)]
        command = TransformSketchElementsCommand(app_context, sketch, {"f": {"points": new_points}})
        command.execute()

        new_points.append((9.0, 9.0))
        stroke.points.append((8.0, 8.0))
        command.undo()
        command.redo()

        assert stroke.points == [(0.0, 0.0), (2.0, 2.0)]

    def test_unchanged_geometry_is_a_noop(self, app_context, sketch, events):
        command = TransformSketchElementsCommand(app_context, sketch, {"a1": {"x": 0.0, "y": 0.0}})

        assert command.execute() is CommandResult.NOOP
        assert events == []

    @pytest.mark.parametrize("changes", [
        {"a1": {"x": 1.0}, "missing": {"x": 1.0}},
        {"a1": {"x": 1.0}, "b1": {"stroke_color": "#FF0000"}},
        {"a1": {"x": 1.0}, "b1": {"width": -5.0}},
        {"a1": {"x": 1.0}, "b2": {"width": 5.0}},
    ], ids=["missing-element", "style-field", "invalid-size", "field-of-another-type"])
    def test_invalid_changes_fail_without_moving_anything(self, app_context, sketch, events, changes):
        command = TransformSketchElementsCommand(app_context, sketch, changes)

        assert command.execute() is CommandResult.FAILURE

        a1 = sketch.find_element("a1")
        assert a1 is not None
        assert a1[1].x == 0.0
        assert events == []
        assert command.undo() is CommandResult.FAILURE

    def test_element_on_a_locked_layer_fails(self, app_context, sketch):
        layer_a = sketch.get_layer("a")
        assert layer_a is not None
        layer_a.locked = True

        assert TransformSketchElementsCommand(app_context, sketch, {"a1": {"x": 1.0}}).execute() is CommandResult.FAILURE


class TestThroughCommandExecutor:
    def test_noop_transform_creates_no_history_entry(self, app_context, sketch):
        executor = CommandExecutor()

        executor.execute_command(TransformSketchElementsCommand(app_context, sketch, {"a1": {"x": 0.0}}))

        assert executor.undo_stack == []

    def test_draw_move_delete_then_undo_everything(self, app_context, sketch):
        executor = CommandExecutor()
        executor.execute_command(AddSketchElementCommand(app_context, sketch, "a", LineElement(id="new"), index=0))
        executor.execute_command(TransformSketchElementsCommand(app_context, sketch, {"new": {"x": 9.0}}))
        executor.execute_command(DeleteSketchElementsCommand(app_context, sketch, ["new", "a2"]))
        assert _ids(sketch, "a") == ["a1", "a3", "a4"]

        executor.undo()
        found = sketch.find_element("new")
        assert found is not None
        assert found[1].x == 9.0
        assert _ids(sketch, "a") == ["new", "a1", "a2", "a3", "a4"]

        executor.undo()
        executor.undo()
        assert _ids(sketch, "a") == ["a1", "a2", "a3", "a4"]

        executor.redo()
        executor.redo()
        executor.redo()
        assert _ids(sketch, "a") == ["a1", "a3", "a4"]
