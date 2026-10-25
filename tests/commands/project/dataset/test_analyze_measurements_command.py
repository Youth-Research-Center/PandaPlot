"""Tests for creating, undoing, and redoing measurement-summary datasets."""

from unittest.mock import Mock

import pandas as pd

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.analyze_measurements_command import AnalyzeMeasurementsCommand
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import ColumnRole, Dataset
from pandaplot.models.state import AppContext, AppState


def _make_command(data: pd.DataFrame, roles: dict[str, ColumnRole], *, name: str | None = None):
    project = Project("P")
    source = Dataset(id="source", name="Experiment", data=data)
    project.add_item(source)
    sibling = Dataset(id="sibling", name="Existing", data=pd.DataFrame({"x": [1]}))
    project.add_item(sibling)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    command = AnalyzeMeasurementsCommand(
        app_context,
        source.id,
        {source.column_id(column): role for column, role in roles.items()},
        result_name=name,
    )
    return command, project, source, app_state


def test_execute_persists_roles_and_adds_result_dataset():
    command, project, source, app_state = _make_command(
        pd.DataFrame({"dose": [1, 1, 2], "response": [3.0, 5.0, 7.0]}),
        {"dose": ColumnRole.CONTROLLED, "response": ColumnRole.MEASURED},
        name="Summary",
    )

    assert command.execute() is CommandResult.SUCCESS

    result = project.find_item(command.result_dataset_id)
    assert isinstance(result, Dataset)
    assert result.name == "Summary"
    assert result.data["Mean"].tolist() == [4.0, 7.0]
    assert source.column_roles == {
        source.column_id("dose"): ColumnRole.CONTROLLED,
        source.column_id("response"): ColumnRole.MEASURED,
    }
    app_state.event_bus.emit.assert_any_call(
        ProjectEvents.PROJECT_ITEM_ADDED,
        {
            "project": project,
            "item_id": result.id,
            "item_type": "dataset",
            "item_name": result.name,
            "item": result,
            "folder_id": None,
        },
    )


def test_execute_persists_replicate_group_and_undo_redo_restores_it():
    command, project, source, _app_state = _make_command(
        pd.DataFrame({"area": [1, 1], "Velocity1": [10.0, 12.0], "Velocity2": [14.0, 16.0]}),
        {
            "area": ColumnRole.CONTROLLED,
            "Velocity1": ColumnRole.MEASURED,
            "Velocity2": ColumnRole.MEASURED,
        },
    )
    groups = {
        source.column_id("Velocity1"): "Velocity",
        source.column_id("Velocity2"): "Velocity",
    }
    command.measurement_groups = groups

    assert command.execute() is CommandResult.SUCCESS
    result_id = command.result_dataset_id
    result = project.find_item(result_id)
    assert result.data.loc[0, "Count"] == 4
    assert result.data.loc[0, "Mean"] == 13
    assert source.column_measurement_groups == groups

    assert command.undo() is CommandResult.SUCCESS
    assert source.column_measurement_groups == {}
    assert command.redo() is CommandResult.SUCCESS
    assert project.find_item(result_id) is result
    assert source.column_measurement_groups == groups


def test_undo_redo_restores_roles_dataset_identity_and_order():
    command, project, source, app_state = _make_command(
        pd.DataFrame({"dose": [1, 1], "response": [3.0, 5.0]}),
        {"dose": ColumnRole.CONTROLLED, "response": ColumnRole.MEASURED},
    )
    source.set_column_role(source.column_id("dose"), ColumnRole.FIXED)
    prior_roles = dict(source.column_roles)

    assert command.execute() is CommandResult.SUCCESS
    result_id = command.result_dataset_id
    result = project.find_item(result_id)
    sibling_order = list(project.root.items)
    assert sibling_order[-1] == result_id

    assert command.undo() is CommandResult.SUCCESS
    assert project.find_item(result_id) is None
    assert dict(source.column_roles) == prior_roles
    app_state.event_bus.emit.assert_any_call(
        ProjectEvents.PROJECT_ITEM_REMOVED,
        {
            "project": project,
            "item_id": result_id,
            "item_type": "dataset",
            "item_name": result.name,
        },
    )

    assert command.redo() is CommandResult.SUCCESS
    assert project.find_item(result_id) is result
    assert list(project.root.items) == sibling_order
    assert source.column_roles[source.column_id("dose")] is ColumnRole.CONTROLLED


def test_invalid_fixed_column_fails_without_persisting_roles():
    command, project, source, _app_state = _make_command(
        pd.DataFrame({"dose": [1, 1], "device": ["A", "B"], "response": [3.0, 5.0]}),
        {
            "dose": ColumnRole.CONTROLLED,
            "device": ColumnRole.FIXED,
            "response": ColumnRole.MEASURED,
        },
    )
    prior_roles = dict(source.column_roles)

    assert command.execute() is CommandResult.FAILURE

    assert dict(source.column_roles) == prior_roles
    assert command.result_dataset_id is None
    assert len(project.root.items) == 2
    app_context_ui = command.ui_controller
    app_context_ui.show_error_message.assert_called_once()
