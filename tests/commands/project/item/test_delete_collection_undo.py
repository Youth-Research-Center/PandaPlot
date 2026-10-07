from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.item import DeleteItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Folder, Image, ImageGallery, Note
from pandaplot.models.state import AppContext, AppState


@pytest.mark.parametrize("collection_type", [Folder, ImageGallery])
def test_collection_undo_restores_nested_payloads_and_index(collection_type):
    ctx = Mock(spec=AppContext)
    state = Mock(spec=AppState)
    ctx.get_app_state.return_value = state
    ctx.get_ui_controller.return_value = Mock(spec=UIController)
    ctx.event_bus = Mock()
    state.event_bus = Mock()
    project = Project("Test")
    parent = Folder(id="parent")
    collection = collection_type(id="collection")
    nested = Folder(id="nested")
    note = Note(id="note", content="Keep me", tags=["tag"])
    dataset = Dataset(id="data", data=pd.DataFrame({"x": [1, 2]}))
    image = Image(id="image")
    image.set_bytes(b"image payload")
    project.add_item(parent)
    project.add_item(collection, parent.id)
    project.add_item(note, collection.id)
    project.add_item(nested, collection.id)
    project.add_item(dataset, nested.id)
    project.add_item(image, nested.id)
    chart = Chart(id="chart")
    chart.add_data_series(dataset.id, label="s1")
    project.add_item(chart)
    state.has_project = True
    state.current_project = project
    column_ids = dict(dataset.column_ids)
    command = DeleteItemCommand(ctx, collection.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert project.find_item("data") is None
    assert not chart.data_series
    for _ in range(2):
        assert command.undo() is CommandResult.SUCCESS
        restored = project.find_item("collection")
        assert isinstance(restored, collection_type)
        assert restored.parent_id == parent.id
        assert [i.id for i in restored.get_items()] == ["note", "nested"]
        assert project.find_item("note").content == "Keep me"
        assert project.find_item("note").tags == ["tag"]
        assert project.find_item("nested").parent_id == collection.id
        assert project.find_item("data").parent_id == nested.id
        pd.testing.assert_frame_equal(project.find_item("data").data, dataset.data)
        assert dict(project.find_item("data").column_ids) == column_ids
        assert project.find_item("image").get_bytes() == b"image payload"
        assert [s.dataset_id for s in chart.data_series] == ["data"]
        assert project.find_item("note") is not note
        assert command.redo() is CommandResult.SUCCESS
        assert all(project.find_item(i) is None for i in ["collection", "note", "nested", "data", "image"])
        assert not chart.data_series


def test_adding_populated_collection_indexes_descendants():
    project = Project("Test")
    folder = Folder(id="folder")
    nested = Folder(id="nested")
    note = Note(id="note")
    nested.add_item(note)
    folder.add_item(nested)
    project.add_item(folder)
    assert project.find_item("nested") is nested
    assert project.find_item("note") is note


def test_add_item_rejects_descendant_id_collision_without_attaching():
    project = Project("Test")
    existing = Note(id="dup")
    project.add_item(existing)
    folder = Folder(id="folder")
    folder.add_item(Note(id="dup"))
    with pytest.raises(ValueError, match="dup"):
        project.add_item(folder)
    assert project.find_item("dup") is existing
    assert project.find_item("folder") is None
    assert folder not in project.root.get_items()


def test_add_item_rejects_descendant_with_wrong_parent_reference():
    project = Project("Test")
    folder = Folder(id="folder")
    note = Note(id="note")
    folder.add_item(note)
    note.parent_id = "elsewhere"
    with pytest.raises(ValueError, match="note"):
        project.add_item(folder)
    assert project.find_item("folder") is None
    assert project.find_item("note") is None


def _make_delete_setup():
    ctx = Mock(spec=AppContext)
    state = Mock(spec=AppState)
    ctx.get_app_state.return_value = state
    ui = Mock(spec=UIController)
    ctx.get_ui_controller.return_value = ui
    ctx.event_bus = Mock()
    state.event_bus = Mock()
    project = Project("Test")
    state.has_project = True
    state.current_project = project
    return ctx, ui, project


def test_declined_confirmation_retains_no_snapshot():
    ctx, ui, project = _make_delete_setup()
    ui.show_question.return_value = False
    folder = Folder(id="folder")
    project.add_item(folder)
    command = DeleteItemCommand(ctx, folder.id)
    assert command.execute() is CommandResult.FAILURE
    assert command._deleted_collection is None
    assert command.deleted_item_data is None
    assert project.find_item("folder") is folder


def test_failed_remove_retains_no_snapshot(monkeypatch):
    ctx, _, project = _make_delete_setup()
    folder = Folder(id="folder")
    project.add_item(folder)
    monkeypatch.setattr(project, "remove_item", Mock(side_effect=RuntimeError("boom")))
    command = DeleteItemCommand(ctx, folder.id, confirm=False)
    assert command.execute() is CommandResult.FAILURE
    assert command._deleted_collection is None
    assert command.deleted_item_data is None


def test_undo_after_redo_restores_state_at_redo_time():
    ctx, _, project = _make_delete_setup()
    folder = Folder(id="folder")
    note = Note(id="note", content="old")
    project.add_item(folder)
    project.add_item(note, folder.id)
    command = DeleteItemCommand(ctx, folder.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    project.find_item("note").content = "edited"
    assert command.redo() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    assert project.find_item("note").content == "edited"


def test_undo_after_redo_restores_standalone_item_edited_before_redo():
    ctx, _, project = _make_delete_setup()
    note = Note(id="note", content="old")
    project.add_item(note)
    command = DeleteItemCommand(ctx, note.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    project.find_item("note").content = "edited"
    assert command.redo() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    assert project.find_item("note").content == "edited"


@pytest.mark.parametrize("parent_in_folder", [False, True])
def test_undo_restores_original_sibling_position(parent_in_folder):
    ctx, _, project = _make_delete_setup()
    holder = Folder(id="holder")
    project.add_item(holder)
    parent_id = holder.id if parent_in_folder else None
    for item_id in ["a", "b", "c"]:
        project.add_item(Folder(id=item_id), parent_id)
    siblings = holder if parent_in_folder else project.root
    command = DeleteItemCommand(ctx, "b", confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    for _ in range(2):
        assert command.undo() is CommandResult.SUCCESS
        assert [i.id for i in siblings.get_items() if i.id in "abc"] == ["a", "b", "c"]
        assert command.redo() is CommandResult.SUCCESS


def _chart_referencing_dataset(project):
    dataset = Dataset(id="data", data=pd.DataFrame({"x": [1, 2]}))
    chart = Chart(id="chart")
    chart.add_data_series(dataset.id, label="s1")
    project.add_item(dataset)
    project.add_item(chart)
    return dataset, chart


def test_failed_remove_in_execute_restores_cascaded_dependents(monkeypatch):
    ctx, _, project = _make_delete_setup()
    dataset, chart = _chart_referencing_dataset(project)
    monkeypatch.setattr(project, "remove_item", Mock(side_effect=RuntimeError("boom")))
    command = DeleteItemCommand(ctx, dataset.id, confirm=False)
    assert command.execute() is CommandResult.FAILURE
    assert [s.dataset_id for s in chart.data_series] == ["data"]


def test_failed_remove_in_redo_restores_cascaded_dependents(monkeypatch):
    ctx, _, project = _make_delete_setup()
    dataset, chart = _chart_referencing_dataset(project)
    command = DeleteItemCommand(ctx, dataset.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    monkeypatch.setattr(project, "remove_item", Mock(side_effect=RuntimeError("boom")))
    live_dataset = project.find_item("data")
    assert command.redo() is CommandResult.ABORTED
    assert project.find_item("data") is live_dataset
    assert [s.dataset_id for s in chart.data_series] == ["data"]


def test_aborted_redo_leaves_collection_untouched(monkeypatch):
    ctx, _, project = _make_delete_setup()
    folder = Folder(id="folder")
    note = Note(id="note", content="keep")
    project.add_item(folder)
    project.add_item(note, folder.id)
    command = DeleteItemCommand(ctx, folder.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    live_folder = project.find_item("folder")
    live_note = project.find_item("note")
    monkeypatch.setattr(project, "remove_item", Mock(side_effect=RuntimeError("boom")))
    assert command.redo() is CommandResult.ABORTED
    assert project.find_item("folder") is live_folder
    assert project.find_item("note") is live_note


def test_add_item_rejects_descendant_using_project_root_id():
    project = Project("Test")
    folder = Folder(id="folder")
    folder.add_item(Note(id=project.root.id))
    with pytest.raises(ValueError, match="root"):
        project.add_item(folder)
    assert project.find_item("folder") is None


def _removed_ids(state):
    return [
        call.args[1]["item_id"]
        for call in state.event_bus.emit.call_args_list
        if call.args[0] == ProjectEvents.PROJECT_ITEM_REMOVED
    ]


def test_deleting_collection_emits_removed_event_for_every_descendant():
    ctx, _, project = _make_delete_setup()
    state = ctx.get_app_state()
    folder = Folder(id="folder")
    nested = Folder(id="nested")
    project.add_item(folder)
    project.add_item(Note(id="note"), folder.id)
    project.add_item(nested, folder.id)
    project.add_item(Note(id="deep"), nested.id)
    command = DeleteItemCommand(ctx, folder.id, confirm=False)
    assert command.execute() is CommandResult.SUCCESS
    assert sorted(_removed_ids(state)) == ["deep", "folder", "nested", "note"]
    assert _removed_ids(state)[-1] == "folder"
    state.event_bus.emit.reset_mock()
    assert command.undo() is CommandResult.SUCCESS
    state.event_bus.emit.reset_mock()
    assert command.redo() is CommandResult.SUCCESS
    assert sorted(_removed_ids(state)) == ["deep", "folder", "nested", "note"]
    assert _removed_ids(state)[-1] == "folder"
