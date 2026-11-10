"""Tests for UpdateProjectDetailsCommand."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project import UpdateProjectDetailsCommand
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.example_info import ExampleInfo, ExampleLevel, ExampleSection

PNG_A = b"\x89PNG-a"
PNG_B = b"\x89PNG-b"


@pytest.fixture
def env():
    project = Project("Original", description="Old notes")
    project.cover_image = PNG_A
    project.example_info = ExampleInfo(summary="old")
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = Mock()
    return app_context, project


def _command(app_context, project, **overrides):
    values = {
        "name": project.name,
        "description": project.description,
        "cover_image": project.cover_image,
        "example_info": project.example_info,
    }
    values.update(overrides)
    return UpdateProjectDetailsCommand(app_context, **values)


FIELD_CHANGES = {
    "name": ("name", "Renamed"),
    "description": ("description", "New notes"),
    "cover_image": ("cover_image", PNG_B),
    "cover_removed": ("cover_image", None),
    "example_info": ("example_info", ExampleInfo(is_example=True, summary="new", section=ExampleSection.CHARTS, level=ExampleLevel.INTERMEDIATE)),
}


@pytest.mark.parametrize("case", FIELD_CHANGES)
def test_execute_undo_redo_each_field(env, case):
    app_context, project = env
    field, value = FIELD_CHANGES[case]
    before = (project.name, project.description, project.cover_image, project.example_info)
    command = _command(app_context, project, **{field: value})

    assert command.execute() is CommandResult.SUCCESS
    assert getattr(project, field) == value

    assert command.undo() is CommandResult.SUCCESS
    assert (project.name, project.description, project.cover_image, project.example_info) == before

    assert command.redo() is CommandResult.SUCCESS
    assert getattr(project, field) == value


def test_all_fields_change_together_and_restore(env):
    app_context, project = env
    info = ExampleInfo(is_example=True, tag_ids=("physics",))
    command = _command(app_context, project, name="N", description="D", cover_image=PNG_B, example_info=info)
    command.execute()
    assert (project.name, project.description, project.cover_image, project.example_info) == ("N", "D", PNG_B, info)
    command.undo()
    assert (project.name, project.description, project.cover_image) == ("Original", "Old notes", PNG_A)
    assert project.example_info == ExampleInfo(summary="old")


def test_identical_values_are_a_noop_and_emit_nothing(env):
    app_context, project = env
    command = _command(app_context, project, cover_image=bytes(PNG_A), example_info=replace(project.example_info))
    assert command.execute() is CommandResult.NOOP
    app_context.event_bus.emit.assert_not_called()
    assert command.undo() is CommandResult.NOOP
    assert command.redo() is CommandResult.NOOP


def test_name_is_stripped_before_comparison(env):
    app_context, project = env
    assert _command(app_context, project, name="  Original  ").execute() is CommandResult.NOOP


def test_empty_name_fails_without_changing_anything(env):
    app_context, project = env
    command = _command(app_context, project, name="  ", description="changed")
    assert command.execute() is CommandResult.FAILURE
    assert project.description == "Old notes"
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    assert command.undo() is CommandResult.NOOP


def test_no_project_fails(env):
    app_context, project = env
    app_context.get_app_state.return_value.has_project = False
    command = _command(app_context, project, name="x")
    assert command.execute() is CommandResult.FAILURE
    app_context.get_ui_controller.return_value.show_warning_message.assert_called_once()


def test_name_change_emits_project_changed_like_rename(env):
    app_context, project = env
    _command(app_context, project, name="Renamed").execute()
    app_context.event_bus.emit.assert_called_once_with(ProjectEvents.PROJECT_CHANGED, {"project": project})


def test_undo_and_redo_emit_project_changed(env):
    app_context, project = env
    command = _command(app_context, project, description="x")
    command.execute()
    app_context.event_bus.emit.reset_mock()
    command.undo()
    command.redo()
    assert app_context.event_bus.emit.call_count == 2


def test_occupies_undo_slot_and_marks_project_modified(env):
    app_context, project = env
    command = _command(app_context, project, description="x")
    assert command.occupies_undo_slot() is True
    assert command.marks_project_modified() is True


def test_failure_while_applying_restores_every_field(env):
    app_context, project = env
    app_context.event_bus.emit.side_effect = RuntimeError("boom")
    command = _command(app_context, project, name="N", description="D", cover_image=PNG_B, example_info=ExampleInfo(is_example=True))

    assert command.execute() is CommandResult.FAILURE
    assert (project.name, project.description, project.cover_image, project.example_info) == (
        "Original", "Old notes", PNG_A, ExampleInfo(summary="old"))
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    # The failed execute() left nothing to undo or redo.
    assert command.undo() is CommandResult.NOOP
    assert command.redo() is CommandResult.NOOP


def test_failure_during_undo_restores_the_applied_values(env):
    app_context, project = env
    command = _command(app_context, project, name="N", description="D")
    command.execute()
    app_context.event_bus.emit.side_effect = RuntimeError("boom")

    assert command.undo() is CommandResult.FAILURE
    assert (project.name, project.description) == ("N", "D")


def test_cleanup_drops_held_cover_bytes(env):
    app_context, project = env
    command = _command(app_context, project, cover_image=PNG_B)
    command.execute()
    command.cleanup()
    assert command._new.cover_image is None
    assert command._old is None
