"""Failures in the dataset editing commands reach the user as a short sentence plus the cause.

The dialog message is a fixed "Couldn't <do X>." sentence; the caught exception is passed as
``error=`` so the dialog can describe it in plain language (see ``describe_error``).
"""

from collections.abc import Callable
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.add_rows_columns_command import AddRowsColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.commands.project.dataset.rename_column_command import RenameColumnCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState
from pandaplot.utils.error_messages import describe_error
from pandaplot.utils.errors import UserFacingError

_CommandFactory = Callable[[AppContext], Command]

_COMMANDS: list[tuple[str, _CommandFactory, str]] = [
    ("add_columns", lambda ctx: AddColumnsCommand(ctx, "ds-1", ["x"], [0]), "Couldn't add the columns."),
    ("add_rows_columns", lambda ctx: AddRowsColumnsCommand(ctx, "ds-1", target_rows=5, target_columns=5), "Couldn't add the rows and columns."),
    ("add_rows", lambda ctx: AddRowsCommand(ctx, "ds-1", [0]), "Couldn't add the rows."),
    ("change_column_dtype", lambda ctx: ChangeColumnDtypeCommand(ctx, "ds-1", 0, "float64"), "Couldn't change the column type."),
    ("create_empty_dataset", lambda ctx: CreateEmptyDatasetCommand(ctx, dataset_name="New"), "Couldn't create the dataset."),
    ("delete_columns", lambda ctx: DeleteColumnsCommand(ctx, "ds-1", [0]), "Couldn't delete the selected columns."),
    ("delete_rows", lambda ctx: DeleteRowsCommand(ctx, "ds-1", [0]), "Couldn't delete the selected rows."),
    ("edit_batch", lambda ctx: EditBatchCommand(ctx, "ds-1", 0, 0, [[1]]), "Couldn't apply the pasted or edited cells."),
    ("edit", lambda ctx: EditCommand(ctx, "ds-1", (0, 0), old_value=1, new_value=2), "Couldn't change the cell."),
    ("rename_column", lambda ctx: RenameColumnCommand(ctx, "ds-1", 0, "b"), "Couldn't rename the column."),
]


@pytest.fixture
def env():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    ui_controller = Mock(spec=UIController)
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.app_state = app_state
    app_context.event_bus = Mock()
    project = Mock()
    app_state.current_project = project
    return app_context, project, ui_controller


@pytest.mark.parametrize(("factory", "message"), [(f, m) for _, f, m in _COMMANDS], ids=[n for n, _, _ in _COMMANDS])
def test_execute_failure_shows_a_short_sentence_and_passes_the_exception(env, factory, message):
    app_context, project, ui_controller = env
    error = PermissionError("[Errno 13] Permission denied: '/secret/path'")
    project.find_item.side_effect = error
    project.add_item.side_effect = error
    project.get_all_items.side_effect = error
    command = factory(app_context)

    with patch("pandaplot.commands.project.dataset.create_empty_dataset_command.Dataset", side_effect=error):
        assert command.execute() is CommandResult.FAILURE

    ui_controller.show_error_message.assert_called_once()
    args, kwargs = ui_controller.show_error_message.call_args
    assert args[1] == message
    assert kwargs["error"] is error
    assert "Errno" not in args[1]
    assert "secret" not in args[1]


def test_changing_a_column_type_that_pandas_rejects_reads_as_a_plain_description(env):
    app_context, project, ui_controller = env
    project.find_item.return_value = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": ["1", "2"]}))
    command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")
    pandas_error = ValueError("could not convert string to float: 'abc'")

    with patch("pandaplot.commands.project.dataset.change_column_dtype_command.pd.to_numeric", side_effect=pandas_error):
        assert command.execute() is CommandResult.FAILURE

    ui_controller.show_error_message.assert_called_once()
    args, kwargs = ui_controller.show_error_message.call_args
    assert args[1] == "Couldn't change the column type."
    assert kwargs["error"] is pandas_error
    assert "could not convert" not in args[1]
    description = describe_error(kwargs["error"])
    assert description.reason == "PandaPlot could not process this data with these settings."
    assert "could not convert string to float" in description.details


def test_a_user_facing_error_is_passed_through_unchanged(env):
    app_context, project, ui_controller = env
    project.find_item.side_effect = UserFacingError("That cell is locked.")
    command = EditCommand(app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    assert command.execute() is CommandResult.FAILURE

    error = ui_controller.show_error_message.call_args.kwargs["error"]
    assert describe_error(error).reason == "That cell is locked."
    assert describe_error(error).details == ""


def test_create_empty_dataset_undo_failure_shows_a_short_sentence(env):
    app_context, project, ui_controller = env
    command = CreateEmptyDatasetCommand(app_context, dataset_name="New")
    command.dataset_id = "ds-1"
    error = OSError("disk exploded")
    project.find_item.side_effect = error

    assert command.undo() is CommandResult.FAILURE

    args, kwargs = ui_controller.show_error_message.call_args
    assert args[1] == "Couldn't undo creating the dataset."
    assert kwargs["error"] is error


def test_create_empty_dataset_redo_failure_shows_a_short_sentence(env):
    app_context, project, ui_controller = env
    error = RuntimeError("boom")
    project.find_item.side_effect = error
    command = CreateEmptyDatasetCommand(app_context, dataset_name="New")
    command.execute = Mock(side_effect=error)

    assert command.redo() is CommandResult.FAILURE

    args, kwargs = ui_controller.show_error_message.call_args
    assert args[1] == "Couldn't redo creating the dataset."
    assert kwargs["error"] is error


def test_delete_columns_redo_failure_shows_a_short_sentence(env):
    app_context, _project, ui_controller = env
    command = DeleteColumnsCommand(app_context, "ds-1", [0])
    command.dataset = Mock()
    command.original_data = pd.DataFrame({"a": [1]})
    command.column_names = ["a"]
    error = KeyError("a")
    command._find_chart_references = Mock(side_effect=error)

    assert command.redo() is CommandResult.FAILURE

    args, kwargs = ui_controller.show_error_message.call_args
    assert args[1] == "Couldn't redo deleting the columns."
    assert kwargs["error"] is error
