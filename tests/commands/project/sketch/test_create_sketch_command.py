"""Tests for CreateSketchCommand, against a real app context and project."""
import pytest

from pandaplot.app import build_app_context
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.sketch import CreateSketchCommand
from pandaplot.models.events import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Folder, Note, Sketch


@pytest.fixture
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def project(app_context) -> Project:
    project = Project(name="Sketches")
    project.add_item(Folder(id="folder", name="Drawings"))
    app_context.get_app_state().load_project(project)
    return project


@pytest.fixture
def events(app_context) -> list[tuple[str, dict]]:
    received: list[tuple[str, dict]] = []
    for event in (ProjectEvents.PROJECT_ITEM_ADDED, ProjectEvents.PROJECT_ITEM_REMOVED):
        app_context.event_bus.subscribe(event, lambda data, event=event: received.append((event, data)))
    return received


def _root_ids(project: Project) -> list[str]:
    return [item.id for item in project.root.get_items()]


def test_execute_creates_a_numbered_sketch_at_the_root(app_context, project):
    first = CreateSketchCommand(app_context)
    second = CreateSketchCommand(app_context)

    assert first.execute() is CommandResult.SUCCESS
    assert second.execute() is CommandResult.SUCCESS

    sketches = [item for item in project.get_all_items() if isinstance(item, Sketch)]
    assert [sketch.name for sketch in sketches] == ["New Sketch 1", "New Sketch 2"]
    assert len(sketches[0].layers) == 1


def test_execute_creates_the_sketch_in_the_given_folder(app_context, project):
    command = CreateSketchCommand(app_context, sketch_name="Circuit", folder_id="folder")

    command.execute()

    assert command.sketch is not None
    assert command.sketch.parent_id == "folder"
    folder = project.find_item("folder")
    assert isinstance(folder, Folder)
    assert [item.id for item in folder.get_items()] == [command.sketch.id]


def test_item_events_carry_the_generic_item_id(app_context, project, events):
    command = CreateSketchCommand(app_context, sketch_name="Circuit")

    command.execute()
    command.undo()

    assert command.sketch is not None
    assert [(event, data["item_id"], data["item_type"]) for event, data in events] == [
        (ProjectEvents.PROJECT_ITEM_ADDED, command.sketch.id, "sketch"),
        (ProjectEvents.PROJECT_ITEM_REMOVED, command.sketch.id, "sketch"),
    ]


def test_undo_removes_and_redo_restores_the_same_sketch_in_place(app_context, project):
    command = CreateSketchCommand(app_context, sketch_name="Circuit")
    command.execute()
    sketch = command.sketch
    assert sketch is not None
    project.add_item(Note(id="later", name="Added after"))

    assert command.undo() is CommandResult.SUCCESS
    assert project.find_item(sketch.id) is None

    assert command.redo() is CommandResult.SUCCESS
    assert project.find_item(sketch.id) is sketch
    assert _root_ids(project) == ["folder", sketch.id, "later"]


def test_undo_fails_if_the_sketch_was_already_removed(app_context, project):
    command = CreateSketchCommand(app_context)
    command.execute()
    assert command.sketch is not None
    project.remove_item(command.sketch)

    assert command.undo() is CommandResult.FAILURE


def test_blank_name_fails_without_creating_anything(app_context, project):
    assert CreateSketchCommand(app_context, sketch_name="   ").execute() is CommandResult.FAILURE

    assert not any(isinstance(item, Sketch) for item in project.get_all_items())


def test_without_a_project_declining_to_create_one_fails(app_context, monkeypatch):
    monkeypatch.setattr(app_context.get_ui_controller(), "show_action_or_cancel", lambda **_kwargs: False)
    command = CreateSketchCommand(app_context)

    assert command.execute() is CommandResult.FAILURE
    assert command.undo() is CommandResult.FAILURE
    assert command.redo() is CommandResult.FAILURE


def test_through_the_executor_it_marks_the_project_modified_and_undoes(app_context, project):
    app_state = app_context.get_app_state()
    app_state.mark_saved()
    executor = app_context.get_command_executor()

    executor.execute_command(CreateSketchCommand(app_context, sketch_name="Circuit"))
    assert app_state.is_modified

    executor.undo()
    assert not any(isinstance(item, Sketch) for item in project.get_all_items())
