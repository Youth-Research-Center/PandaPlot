"""Dataset commands undo and redo the live dataset after it is deleted and restored (#666).

``DeleteItemCommand.undo()`` rebuilds a deleted dataset from its snapshot, so the project then holds a new
``Dataset`` object with the same id. A command that kept the object it found in ``execute()`` would undo or redo
the detached copy and report success while the dataset the user sees stays unchanged.
"""

from collections.abc import Callable
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.add_rows_columns_command import AddRowsColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.apply_analysis_result_command import ApplyAnalysisResultCommand
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.commands.project.dataset.preprocess_column_command import PreprocessColumnCommand
from pandaplot.commands.project.dataset.recompute_formula_columns_command import RecomputeFormulaColumnsCommand
from pandaplot.commands.project.dataset.rename_column_command import RenameColumnCommand
from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
from pandaplot.commands.project.item import DeleteItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx() -> tuple[Mock, Project]:
    project = Project(name="P")
    project.add_item(Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})))
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.app_state = app_state
    app_context.event_bus = app_state.event_bus
    app_context.get_app_state.return_value = app_state
    ui_controller = Mock(spec=UIController)
    ui_controller.parent_widget = None
    ui_controller.show_confirmation.return_value = True
    app_context.get_ui_controller.return_value = ui_controller
    return app_context, project


def _stale_formula_recompute(app_context: Mock, project: Project) -> Command:
    """A non-live formula column whose source changed, so recomputing it changes its values."""
    config = {
        "new_column_name": "f", "transform_type": "column", "source_columns": ["a"],
        "expression": "value * 2", "as_formula": True, "live": False,
    }
    assert TransformColumnCommand(app_context, "ds-1", config).execute() is CommandResult.SUCCESS
    dataset = project.find_item("ds-1")
    dataset.data["a"] = [10.0, 20.0, 30.0]
    return RecomputeFormulaColumnsCommand(app_context, "ds-1", [list(dataset.data.columns).index("f")])


COMMANDS: dict[str, Callable[[Mock, Project], Command]] = {
    "add_columns": lambda c, _p: AddColumnsCommand(c, "ds-1", column_names=["c"], reference_positions=[0]),
    "add_rows": lambda c, _p: AddRowsCommand(c, "ds-1", reference_positions=[1]),
    "add_rows_columns": lambda c, _p: AddRowsColumnsCommand(c, "ds-1", target_rows=4, target_columns=3),
    "change_column_dtype": lambda c, _p: ChangeColumnDtypeCommand(c, "ds-1", 0, "string"),
    "apply_analysis_result": lambda c, _p: ApplyAnalysisResultCommand(
        c, "ds-1", "r", pd.Series([7.0, 8.0, 9.0]), column_existed_before=False, original_data=None,
    ),
    "delete_rows": lambda c, _p: DeleteRowsCommand(c, "ds-1", [1]),
    "delete_columns": lambda c, _p: DeleteColumnsCommand(c, "ds-1", [0]),
    "edit": lambda c, _p: EditCommand(c, "ds-1", (1, 0), 2.0, 99.0),
    "edit_batch": lambda c, _p: EditBatchCommand(c, "ds-1", 2, 1, [[50.0, 51.0], [52.0, 53.0]]),
    "preprocess_column": lambda c, _p: PreprocessColumnCommand(c, "ds-1", {"method": "center", "source_columns": ["a"]}),
    "rename_column": lambda c, _p: RenameColumnCommand(c, "ds-1", 0, "renamed"),
    "recompute_formula_columns": _stale_formula_recompute,
    "transform_column": lambda c, _p: TransformColumnCommand(c, "ds-1", {
        "new_column_name": "t", "transform_type": "column", "source_columns": ["a"], "expression": "value * 2",
    }),
}


def _state(project: Project) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    dataset = project.find_item("ds-1")
    return dataset.data.copy(), list(dataset.column_ids.items())


def _delete_and_restore(app_context: Mock, project: Project) -> Dataset:
    before = project.find_item("ds-1")
    delete = DeleteItemCommand(app_context, "ds-1", confirm=False)
    assert delete.execute() is CommandResult.SUCCESS
    assert delete.undo() is CommandResult.SUCCESS
    restored = project.find_item("ds-1")
    assert restored is not before
    return restored


@pytest.mark.parametrize("make_command", COMMANDS.values(), ids=COMMANDS.keys())
def test_undo_and_redo_change_the_restored_dataset(ctx, make_command):
    app_context, project = ctx
    command = make_command(app_context, project)
    frame_before, ids_before = _state(project)
    assert command.execute() is CommandResult.SUCCESS
    frame_after, ids_after = _state(project)

    _delete_and_restore(app_context, project)

    assert command.undo() is CommandResult.SUCCESS
    frame, ids = _state(project)
    pd.testing.assert_frame_equal(frame, frame_before)
    assert ids == ids_before

    assert command.redo() is CommandResult.SUCCESS
    frame, ids = _state(project)
    pd.testing.assert_frame_equal(frame, frame_after)
    assert ids == ids_after


@pytest.mark.parametrize("make_command", COMMANDS.values(), ids=COMMANDS.keys())
def test_undo_and_redo_are_aborted_once_the_dataset_is_deleted(ctx, make_command):
    app_context, project = ctx
    command = make_command(app_context, project)
    assert command.execute() is CommandResult.SUCCESS
    assert DeleteItemCommand(app_context, "ds-1", confirm=False).execute() is CommandResult.SUCCESS

    assert command.undo() is CommandResult.ABORTED
    assert command.redo() is CommandResult.ABORTED
