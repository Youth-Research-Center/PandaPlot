"""Tests for AddImportedDatasetsCommand -- the undoable command that actually
adds already-read Dataset object(s) to the project. Split out of
ImportDataCommand so the dispatching command (fire-and-forget, never on the
undo stack) and the real, undoable effect are separate commands (#301)."""
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset import AddImportedDatasetsCommand
from pandaplot.models.project.items import Dataset


@pytest.fixture
def app_context_with_project():
    project = Mock()
    inserted_items = {}

    def _add_item(item, parent_id=None):
        item.parent_id = parent_id
        inserted_items[item.id] = item

    def _find_item(item_id):
        return inserted_items.get(item_id)

    def _remove_item(item):
        inserted_items.pop(item.id, None)

    project.add_item.side_effect = _add_item
    project.find_item.side_effect = _find_item
    project.remove_item.side_effect = _remove_item

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, project, app_state


def _dataset(name="ds"):
    return Dataset(name=name, data=pd.DataFrame({"a": [1, 2]}))


def test_execute_adds_each_dataset_to_the_project(app_context_with_project):
    app_context, project, _ = app_context_with_project
    datasets = [_dataset("a"), _dataset("b")]

    command = AddImportedDatasetsCommand(app_context, datasets, folder_id="folder-1")
    result = command.execute()

    assert result is CommandResult.SUCCESS
    assert project.add_item.call_count == 2
    project.add_item.assert_any_call(datasets[0], parent_id="folder-1")
    project.add_item.assert_any_call(datasets[1], parent_id="folder-1")


def test_execute_emits_dataset_created_per_dataset(app_context_with_project):
    app_context, _, app_state = app_context_with_project
    datasets = [_dataset("a"), _dataset("b")]

    command = AddImportedDatasetsCommand(app_context, datasets)
    command.execute()

    assert app_state.event_bus.emit.call_count == 2


def test_undo_removes_all_datasets(app_context_with_project):
    app_context, project, _ = app_context_with_project
    datasets = [_dataset("a"), _dataset("b")]
    command = AddImportedDatasetsCommand(app_context, datasets)
    command.execute()

    result = command.undo()

    assert result is CommandResult.SUCCESS
    assert project.remove_item.call_count == 2
    for dataset in datasets:
        assert project.find_item(dataset.id) is None


def test_redo_readds_the_same_dataset_instances(app_context_with_project):
    app_context, project, _ = app_context_with_project
    datasets = [_dataset("a")]
    command = AddImportedDatasetsCommand(app_context, datasets, folder_id="folder-1")
    command.execute()

    command.undo()
    command.redo()

    assert project.add_item.call_count == 2
    assert project.add_item.call_args == ((datasets[0],), {"parent_id": "folder-1"})


def test_execute_fails_when_no_project(app_context_with_project):
    app_context, _, app_state = app_context_with_project
    app_state.has_project = False

    command = AddImportedDatasetsCommand(app_context, [_dataset()])
    result = command.execute()

    assert result is CommandResult.FAILURE


def test_undo_without_project_does_not_raise(app_context_with_project):
    app_context, _, app_state = app_context_with_project
    command = AddImportedDatasetsCommand(app_context, [_dataset()])
    command.execute()
    app_state.has_project = False

    result = command.undo()

    assert result is CommandResult.FAILURE


def test_cleanup_does_not_raise_and_keeps_datasets_for_redo(app_context_with_project):
    """cleanup() must not null out self.datasets -- redo() calls execute(),
    which re-adds self.datasets, so they need to stay alive for the lifetime
    of the command even after cleanup() (see Command.cleanup)."""
    app_context, _, _ = app_context_with_project
    datasets = [_dataset("a")]
    command = AddImportedDatasetsCommand(app_context, datasets)
    command.execute()

    command.cleanup()  # must not raise

    assert command.datasets == datasets
