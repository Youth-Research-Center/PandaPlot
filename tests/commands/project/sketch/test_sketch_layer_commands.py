"""Tests for the undoable sketch layer commands."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.sketch import (
    AddSketchLayerCommand,
    DeleteSketchLayerCommand,
    RenameSketchLayerCommand,
    ReorderSketchLayerCommand,
    SetActiveSketchLayerCommand,
    SetSketchLayerPropertiesCommand,
)
from pandaplot.commands.project.sketch.add_sketch_layer_command import next_layer_name
from pandaplot.models.events import EventBus, SketchEvents
from pandaplot.models.events.event_data import SketchChangedData
from pandaplot.models.project.items.sketch import LineElement, Sketch, SketchLayer


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
    return Sketch(id="sketch-1", active_layer_id="b", layers=[
        SketchLayer(id="a", name="Layer 1", elements=[LineElement(id="a1")]),
        SketchLayer(id="b", name="Layer 2", elements=[LineElement(id="b1"), LineElement(id="b2")]),
        SketchLayer(id="c", name="Layer 3"),
    ])


def _layer_ids(sketch: Sketch) -> list[str]:
    return [layer.id for layer in sketch.layers]


def _layer(sketch: Sketch, layer_id: str) -> SketchLayer:
    layer = sketch.get_layer(layer_id)
    assert layer is not None
    return layer


def _announced(events: list[dict]) -> list[SketchChangedData]:
    return [SketchChangedData.from_dict(event) for event in events]


class TestNextLayerName:
    def test_counts_on_from_the_number_of_layers(self, sketch):
        assert next_layer_name(sketch) == "Layer 4"

    def test_skips_names_already_in_use(self):
        sketch = Sketch(layers=[SketchLayer(name="Layer 2"), SketchLayer(name="Layer 3")])

        assert next_layer_name(sketch) == "Layer 4"


class TestAddSketchLayerCommand:
    def test_adds_an_empty_named_layer_above_the_active_one_and_activates_it(self, app_context, sketch, events):
        command = AddSketchLayerCommand(app_context, sketch)

        assert command.execute() is CommandResult.SUCCESS

        assert command.layer is not None
        assert _layer_ids(sketch) == ["a", "b", command.layer.id, "c"]
        assert command.layer.name == "Layer 4"
        assert command.layer.elements == []
        assert sketch.active_layer_id == command.layer.id
        assert _announced(events) == [SketchChangedData(sketch_id="sketch-1")]

    def test_name_and_index_can_be_given(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch, name="  Notes  ", index=0)
        command.execute()

        assert command.layer is not None
        assert sketch.layers[0] is command.layer
        assert command.layer.name == "Notes"

    def test_blank_name_falls_back_to_the_default(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch, name="   ")
        command.execute()

        assert command.layer is not None
        assert command.layer.name == "Layer 4"

    def test_undo_removes_it_and_reactivates_the_previous_layer(self, app_context, sketch, events):
        command = AddSketchLayerCommand(app_context, sketch)
        command.execute()

        assert command.undo() is CommandResult.SUCCESS

        assert _layer_ids(sketch) == ["a", "b", "c"]
        assert sketch.active_layer_id == "b"
        assert len(events) == 2

    def test_redo_restores_the_same_layer_at_the_same_index(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch)
        command.execute()
        layer = command.layer
        command.undo()

        assert command.redo() is CommandResult.SUCCESS

        assert sketch.layers[2] is layer
        assert layer is not None and sketch.active_layer_id == layer.id

    def test_undo_fails_when_the_layer_is_already_gone(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch)
        command.execute()
        assert command.layer is not None
        sketch.remove_layer(command.layer.id)

        assert command.undo() is CommandResult.FAILURE

    def test_redo_fails_when_the_layer_is_still_there(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch)
        command.execute()

        assert command.redo() is CommandResult.FAILURE
        assert len(sketch.layers) == 4

    def test_undo_and_redo_before_execute_fail(self, app_context, sketch):
        command = AddSketchLayerCommand(app_context, sketch)

        assert command.undo() is CommandResult.FAILURE
        assert command.redo() is CommandResult.FAILURE


class TestDeleteSketchLayerCommand:
    def test_deletes_the_layer_with_its_elements(self, app_context, sketch, events):
        command = DeleteSketchLayerCommand(app_context, sketch, "b")

        assert command.execute() is CommandResult.SUCCESS

        assert _layer_ids(sketch) == ["a", "c"]
        assert sketch.find_element("b1") is None
        assert sketch.active_layer_id == "c"
        assert _announced(events) == [SketchChangedData(sketch_id="sketch-1")]

    def test_undo_restores_the_same_layer_elements_position_and_active_layer(self, app_context, sketch):
        layer = _layer(sketch, "b")
        command = DeleteSketchLayerCommand(app_context, sketch, "b")
        command.execute()

        assert command.undo() is CommandResult.SUCCESS

        assert _layer_ids(sketch) == ["a", "b", "c"]
        assert sketch.layers[1] is layer
        assert [element.id for element in layer.elements] == ["b1", "b2"]
        assert sketch.active_layer_id == "b"

    def test_undo_keeps_another_active_layer_active(self, app_context, sketch):
        command = DeleteSketchLayerCommand(app_context, sketch, "a")
        command.execute()

        command.undo()

        assert sketch.active_layer_id == "b"

    def test_redo_deletes_it_again(self, app_context, sketch):
        command = DeleteSketchLayerCommand(app_context, sketch, "b")
        command.execute()
        command.undo()

        assert command.redo() is CommandResult.SUCCESS

        assert _layer_ids(sketch) == ["a", "c"]

    def test_refuses_the_last_layer(self, app_context, events):
        sketch = Sketch(layers=[SketchLayer(id="only")])

        assert DeleteSketchLayerCommand(app_context, sketch, "only").execute() is CommandResult.FAILURE

        assert _layer_ids(sketch) == ["only"]
        assert events == []

    def test_refuses_a_locked_layer(self, app_context, sketch, events):
        _layer(sketch, "b").locked = True

        assert DeleteSketchLayerCommand(app_context, sketch, "b").execute() is CommandResult.FAILURE

        assert _layer_ids(sketch) == ["a", "b", "c"]
        assert events == []

    def test_refuses_a_missing_layer(self, app_context, sketch):
        assert DeleteSketchLayerCommand(app_context, sketch, "missing").execute() is CommandResult.FAILURE

    def test_undo_fails_when_the_layer_is_already_back(self, app_context, sketch):
        command = DeleteSketchLayerCommand(app_context, sketch, "b")
        command.execute()
        command.undo()

        assert command.undo() is CommandResult.FAILURE
        assert _layer_ids(sketch) == ["a", "b", "c"]

    def test_undo_and_redo_before_execute_fail(self, app_context, sketch):
        command = DeleteSketchLayerCommand(app_context, sketch, "b")

        assert command.undo() is CommandResult.FAILURE
        assert command.redo() is CommandResult.FAILURE
        assert _layer_ids(sketch) == ["a", "b", "c"]

    def test_cleanup_drops_the_deleted_layer(self, app_context, sketch):
        command = DeleteSketchLayerCommand(app_context, sketch, "b")
        command.execute()

        command.cleanup()

        assert command.undo() is CommandResult.FAILURE


class TestReorderSketchLayerCommand:
    def test_moves_the_layer(self, app_context, sketch, events):
        command = ReorderSketchLayerCommand(app_context, sketch, "a", 2)

        assert command.execute() is CommandResult.SUCCESS

        assert _layer_ids(sketch) == ["b", "c", "a"]
        assert len(events) == 1

    def test_undo_and_redo(self, app_context, sketch):
        command = ReorderSketchLayerCommand(app_context, sketch, "c", 0)
        command.execute()

        assert command.undo() is CommandResult.SUCCESS
        assert _layer_ids(sketch) == ["a", "b", "c"]

        assert command.redo() is CommandResult.SUCCESS
        assert _layer_ids(sketch) == ["c", "a", "b"]

    def test_index_is_clamped(self, app_context, sketch):
        command = ReorderSketchLayerCommand(app_context, sketch, "a", 99)
        command.execute()

        assert _layer_ids(sketch) == ["b", "c", "a"]
        assert command.new_index == 2

    def test_moving_to_the_same_place_is_a_noop(self, app_context, sketch, events):
        assert ReorderSketchLayerCommand(app_context, sketch, "c", 5).execute() is CommandResult.NOOP

        assert events == []

    def test_missing_layer_fails(self, app_context, sketch):
        assert ReorderSketchLayerCommand(app_context, sketch, "missing", 0).execute() is CommandResult.FAILURE

    def test_undo_fails_when_the_layer_is_gone(self, app_context, sketch):
        command = ReorderSketchLayerCommand(app_context, sketch, "a", 2)
        command.execute()
        sketch.remove_layer("a")

        assert command.undo() is CommandResult.FAILURE


class TestRenameSketchLayerCommand:
    def test_renames_and_trims(self, app_context, sketch, events):
        command = RenameSketchLayerCommand(app_context, sketch, "b", "  Labels ")

        assert command.execute() is CommandResult.SUCCESS

        assert _layer(sketch, "b").name == "Labels"
        assert len(events) == 1

    def test_undo_and_redo(self, app_context, sketch):
        command = RenameSketchLayerCommand(app_context, sketch, "b", "Labels")
        command.execute()

        assert command.undo() is CommandResult.SUCCESS
        assert _layer(sketch, "b").name == "Layer 2"

        assert command.redo() is CommandResult.SUCCESS
        assert _layer(sketch, "b").name == "Labels"

    def test_same_name_is_a_noop(self, app_context, sketch, events):
        assert RenameSketchLayerCommand(app_context, sketch, "b", " Layer 2 ").execute() is CommandResult.NOOP
        assert events == []

    def test_empty_name_fails(self, app_context, sketch):
        assert RenameSketchLayerCommand(app_context, sketch, "b", "   ").execute() is CommandResult.FAILURE
        assert _layer(sketch, "b").name == "Layer 2"

    def test_duplicate_names_are_allowed(self, app_context, sketch):
        assert RenameSketchLayerCommand(app_context, sketch, "b", "Layer 1").execute() is CommandResult.SUCCESS

    def test_locked_layers_can_be_renamed(self, app_context, sketch):
        _layer(sketch, "b").locked = True

        assert RenameSketchLayerCommand(app_context, sketch, "b", "Labels").execute() is CommandResult.SUCCESS

    def test_missing_layer_fails(self, app_context, sketch):
        assert RenameSketchLayerCommand(app_context, sketch, "missing", "Labels").execute() is CommandResult.FAILURE


class TestSetSketchLayerPropertiesCommand:
    def test_sets_the_given_properties_only(self, app_context, sketch, events):
        command = SetSketchLayerPropertiesCommand(app_context, sketch, "b", visible=False, opacity=0.25)

        assert command.execute() is CommandResult.SUCCESS

        layer = _layer(sketch, "b")
        assert (layer.visible, layer.locked, layer.opacity) == (False, False, 0.25)
        assert len(events) == 1

    def test_undo_and_redo(self, app_context, sketch):
        command = SetSketchLayerPropertiesCommand(app_context, sketch, "b", locked=True, opacity=0.5)
        command.execute()
        layer = _layer(sketch, "b")

        assert command.undo() is CommandResult.SUCCESS
        assert (layer.visible, layer.locked, layer.opacity) == (True, False, 1.0)

        assert command.redo() is CommandResult.SUCCESS
        assert (layer.visible, layer.locked, layer.opacity) == (True, True, 0.5)

    def test_unlocking_a_locked_layer_is_allowed(self, app_context, sketch):
        _layer(sketch, "b").locked = True

        assert SetSketchLayerPropertiesCommand(app_context, sketch, "b", locked=False).execute() is CommandResult.SUCCESS
        assert _layer(sketch, "b").locked is False

    def test_unchanged_values_are_a_noop(self, app_context, sketch, events):
        assert SetSketchLayerPropertiesCommand(app_context, sketch, "b", visible=True, opacity=1.0).execute() is CommandResult.NOOP
        assert SetSketchLayerPropertiesCommand(app_context, sketch, "b").execute() is CommandResult.NOOP
        assert events == []

    @pytest.mark.parametrize("opacity", [-0.1, 1.5, float("nan"), float("inf")])
    def test_invalid_opacity_fails_without_changing_anything(self, app_context, sketch, opacity):
        command = SetSketchLayerPropertiesCommand(app_context, sketch, "b", visible=False, opacity=opacity)

        assert command.execute() is CommandResult.FAILURE

        layer = _layer(sketch, "b")
        assert (layer.visible, layer.opacity) == (True, 1.0)

    def test_missing_layer_fails(self, app_context, sketch):
        assert SetSketchLayerPropertiesCommand(app_context, sketch, "missing", visible=False).execute() is CommandResult.FAILURE

    def test_undo_fails_when_the_layer_is_gone(self, app_context, sketch):
        command = SetSketchLayerPropertiesCommand(app_context, sketch, "a", visible=False)
        command.execute()
        sketch.remove_layer("a")

        assert command.undo() is CommandResult.FAILURE


class TestSetActiveSketchLayerCommand:
    def test_activates_the_layer(self, app_context, sketch, events):
        assert SetActiveSketchLayerCommand(app_context, sketch, "a").execute() is CommandResult.SUCCESS

        assert sketch.active_layer_id == "a"
        assert len(events) == 1

    def test_already_active_is_a_noop(self, app_context, sketch, events):
        assert SetActiveSketchLayerCommand(app_context, sketch, "b").execute() is CommandResult.NOOP
        assert events == []

    def test_missing_layer_fails(self, app_context, sketch):
        assert SetActiveSketchLayerCommand(app_context, sketch, "missing").execute() is CommandResult.FAILURE
        assert sketch.active_layer_id == "b"

    def test_marks_the_project_modified_without_taking_an_undo_slot_or_clearing_redo(self, app_context, sketch):
        modified = Mock()
        executor = CommandExecutor(on_project_modified=modified)
        executor.execute_command(RenameSketchLayerCommand(app_context, sketch, "b", "Labels"))
        executor.undo()
        modified.reset_mock()

        assert executor.execute_command(SetActiveSketchLayerCommand(app_context, sketch, "a")) is True

        modified.assert_called_once_with()
        assert executor.undo_stack == []
        assert len(executor.redo_stack) == 1


def test_undo_history_replays_a_sequence_of_layer_edits(app_context, sketch):
    """Undoing everything returns the sketch to where it started, and redoing
    everything replays it, through the real executor."""
    executor = CommandExecutor()
    before = sketch.to_dict()
    add = AddSketchLayerCommand(app_context, sketch, name="Notes")
    executor.execute_command(add)
    assert add.layer is not None
    executor.execute_command(ReorderSketchLayerCommand(app_context, sketch, add.layer.id, 0))
    executor.execute_command(SetSketchLayerPropertiesCommand(app_context, sketch, "a", locked=True))
    executor.execute_command(DeleteSketchLayerCommand(app_context, sketch, "b"))
    executor.execute_command(RenameSketchLayerCommand(app_context, sketch, "c", "Top"))
    after = sketch.to_dict()

    while executor.can_undo():
        assert executor.undo() is True
    assert {key: value for key, value in sketch.to_dict().items() if key != "modified_at"} == {
        key: value for key, value in before.items() if key != "modified_at"
    }

    while executor.can_redo():
        assert executor.redo() is True
    assert {key: value for key, value in sketch.to_dict().items() if key != "modified_at"} == {
        key: value for key, value in after.items() if key != "modified_at"
    }
