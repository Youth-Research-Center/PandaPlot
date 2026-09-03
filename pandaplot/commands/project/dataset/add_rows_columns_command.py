"""
Command to grow a dataset to a desired table size.

Unlike AddRowsCommand / AddColumnsCommand -- which insert relative to a
selection in the table and are driven from the row/column context menus --
this command is the Data-menu entry point: it asks for the table size the user
wants and appends whatever rows and columns are needed to reach it, as a single
undoable step.
"""

from typing import Any, List, Optional, override

import pandas as pd
from PySide6.QtWidgets import QDialog

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import (
    DatasetColumnsAddedData,
    DatasetColumnsRemovedData,
    DatasetRowsAddedData,
    DatasetRowsRemovedData,
)
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState
from pandaplot.utils.item_display_options import dataset_display_options


class AddRowsColumnsCommand(Command):
    """
    Command to append rows and/or columns to an existing dataset so that it
    reaches the requested table size.

    With no target size given, the size (and the target dataset) is asked for
    with `AddRowsColumnsDialog`.
    """

    def __init__(self, app_context: AppContext, dataset_id: Optional[str] = None,
                 target_rows: Optional[int] = None,
                 target_columns: Optional[int] = None):
        """
        Initialize the AddRowsColumnsCommand.

        Args:
            app_context: Application context
            dataset_id: ID of the target dataset; also the dataset preselected
                in the dialog when no target size is given
            target_rows: Desired total number of rows (prompts when omitted)
            target_columns: Desired total number of columns (prompts when omitted)
        """
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.target_rows = target_rows
        self.target_columns = target_columns

        # Store state for undo
        self.original_data: Optional[pd.DataFrame] = None
        self.project = None
        self.dataset: Optional[Dataset] = None
        self.added_row_positions: List[int] = []
        self.added_column_positions: List[int] = []

    @override
    def execute(self) -> CommandResult:
        """Execute the add rows/columns command."""
        try:
            self.logger.info("Executing AddRowsColumnsCommand")

            if not self.app_state.has_project:
                self.logger.warning(
                    "AddRowsColumnsCommand.execute: no project open; cannot add rows/columns"
                )
                self.ui_controller.show_warning_message(
                    "Add Rows / Columns",
                    "Please open or create a project first."
                )
                return CommandResult.FAILURE

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning(
                    "AddRowsColumnsCommand.execute: has_project is True but current_project is None"
                )
                return CommandResult.FAILURE

            # Ask for the target dataset and size unless they were provided
            # programmatically (or already resolved by a previous execute(),
            # which is what redo() replays).
            if self.target_rows is None or self.target_columns is None:
                if not self._prompt_for_target():
                    return CommandResult.FAILURE

            dataset = self._resolve_dataset()
            if dataset is None:
                return CommandResult.FAILURE
            self.dataset = dataset

            data = dataset.data if dataset.data is not None else pd.DataFrame()
            current_rows, current_columns = data.shape

            assert self.target_rows is not None and self.target_columns is not None
            rows_to_add = max(0, self.target_rows - current_rows)
            columns_to_add = max(0, self.target_columns - current_columns)

            if rows_to_add == 0 and columns_to_add == 0:
                self.ui_controller.show_info_message(
                    "Add Rows / Columns",
                    f"'{dataset.name}' is already {current_rows} rows x "
                    f"{current_columns} columns or larger. Nothing to add."
                )
                return CommandResult.NOOP

            # Store original data for undo
            self.original_data = data.copy()

            new_data = data.copy()
            if columns_to_add:
                new_data = self._append_columns(new_data, columns_to_add)
            if rows_to_add:
                new_data = self._append_rows(new_data, rows_to_add)

            self.added_column_positions = [
                current_columns + i for i in range(columns_to_add)]
            self.added_row_positions = [
                current_rows + i for i in range(rows_to_add)]

            dataset.set_data(new_data)

            if columns_to_add:
                self.app_state.event_bus.emit(
                    DatasetOperationEvents.DATASET_COLUMN_ADDED,
                    DatasetColumnsAddedData(
                        dataset_id=dataset.id,
                        column_positions=self.added_column_positions
                    ).to_dict())
            if rows_to_add:
                self.app_state.event_bus.emit(
                    DatasetOperationEvents.DATASET_ROW_ADDED,
                    DatasetRowsAddedData(
                        dataset_id=dataset.id,
                        row_positions=self.added_row_positions
                    ).to_dict())

            self.logger.info(
                "Added %d rows and %d columns to dataset '%s' (ID: %s)",
                rows_to_add, columns_to_add, dataset.name, dataset.id)
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to add rows/columns: {str(e)}"
            self.logger.error("AddRowsColumnsCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Add Rows / Columns Error", error_msg)
            return CommandResult.FAILURE

    def _prompt_for_target(self) -> bool:
        """Ask for the dataset and target size. False if there is nothing to
        ask about, or the user cancelled."""
        from pandaplot.gui.dialogs.dataset.add_rows_columns_dialog import (
            AddRowsColumnsDialog,
            DatasetSize,
        )

        assert self.project is not None
        display_names = dict(dataset_display_options(self.project))
        options = []
        for item in self.project.get_all_items():
            if not isinstance(item, Dataset):
                continue
            rows, columns = item.data.shape if item.data is not None else (0, 0)
            options.append(DatasetSize(id=item.id, name=display_names[item.id], rows=rows, columns=columns))

        if not options:
            self.logger.warning(
                "AddRowsColumnsCommand._prompt_for_target: project has no datasets"
            )
            self.ui_controller.show_warning_message(
                "Add Rows / Columns",
                "This project has no datasets. Create or import one first."
            )
            return False

        dialog = AddRowsColumnsDialog(
            options, initial_dataset_id=self.dataset_id,
            parent=self.ui_controller.parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False  # User cancelled

        self.dataset_id = dialog.get_dataset_id()
        self.target_rows = dialog.get_target_rows()
        self.target_columns = dialog.get_target_columns()
        return True

    def _resolve_dataset(self) -> Optional[Dataset]:
        """Look up the target dataset, reporting why it is unusable if it is."""
        assert self.project is not None
        if not self.dataset_id:
            self.logger.warning(
                "AddRowsColumnsCommand._resolve_dataset: no dataset selected"
            )
            self.ui_controller.show_warning_message(
                "Add Rows / Columns",
                "No dataset selected."
            )
            return None

        found_item = self.project.find_item(self.dataset_id)
        if not found_item:
            self.logger.warning(
                "AddRowsColumnsCommand._resolve_dataset: dataset '%s' not found",
                self.dataset_id,
            )
            self.ui_controller.show_error_message(
                "Add Rows / Columns",
                f"Dataset with ID '{self.dataset_id}' not found."
            )
            return None

        if not isinstance(found_item, Dataset):
            self.logger.warning(
                "AddRowsColumnsCommand._resolve_dataset: item '%s' is not a Dataset (got %s)",
                self.dataset_id, type(found_item).__name__,
            )
            self.ui_controller.show_error_message(
                "Add Rows / Columns",
                "Selected item is not a dataset."
            )
            return None

        return found_item

    def _append_columns(self, data: pd.DataFrame, count: int) -> pd.DataFrame:
        """Append `count` new float64 columns filled with 0.0, matching the
        default AddColumnsCommand gives a column with no explicit value."""
        existing_names = {str(name) for name in data.columns}
        new_columns = {}
        suffix = len(data.columns)
        for _ in range(count):
            suffix += 1
            name = f"Column{suffix}"
            while name in existing_names or name in new_columns:
                suffix += 1
                name = f"Column{suffix}"
            new_columns[name] = pd.Series(
                [0.0] * len(data), index=data.index, dtype="float64")

        return pd.concat([data, pd.DataFrame(new_columns, index=data.index)], axis=1)

    def _append_rows(self, data: pd.DataFrame, count: int) -> pd.DataFrame:
        """Append `count` new rows filled with each column's default value."""
        new_row = {column: self._default_value_for_column(data, column)
                   for column in data.columns}
        new_rows = pd.DataFrame([new_row] * count, columns=data.columns)
        return pd.concat([data, new_rows], ignore_index=True)

    def _default_value_for_column(self, data: pd.DataFrame, column: Any) -> Any:
        """Generate appropriate default value based on column type."""
        col_dtype = data[column].dtype

        if pd.api.types.is_bool_dtype(col_dtype):
            return False
        elif pd.api.types.is_numeric_dtype(col_dtype):
            if pd.api.types.is_integer_dtype(col_dtype):
                return 0
            return 0.0
        return ""

    def undo(self) -> CommandResult:
        """Undo the add rows/columns command."""
        try:
            if self.dataset and self.original_data is not None:
                self.dataset.set_data(self.original_data)

                # Mirror execute()'s emissions in reverse so the table model
                # tears the added rows down before the added columns.
                if self.added_row_positions:
                    self.app_state.event_bus.emit(
                        DatasetOperationEvents.DATASET_ROW_REMOVED,
                        DatasetRowsRemovedData(
                            dataset_id=self.dataset.id,
                            row_positions=self.added_row_positions
                        ).to_dict())
                if self.added_column_positions:
                    self.app_state.event_bus.emit(
                        DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                        DatasetColumnsRemovedData(
                            dataset_id=self.dataset.id,
                            column_positions=self.added_column_positions
                        ).to_dict())

                self.logger.info(
                    "Undid adding %d rows and %d columns to dataset '%s'",
                    len(self.added_row_positions),
                    len(self.added_column_positions),
                    self.dataset.name)
                return CommandResult.SUCCESS
            self.logger.warning(
                "AddRowsColumnsCommand.undo: cannot undo for dataset '%s' (dataset found=%s, original_data set=%s)",
                self.dataset_id, self.dataset is not None, self.original_data is not None,
            )
            return CommandResult.FAILURE
        except Exception as e:
            self.logger.error("AddRowsColumnsCommand Undo Error: %s", e)
            return CommandResult.FAILURE

    def redo(self):
        """Redo the add rows/columns command."""
        # Re-execute with the target resolved on the first run, so redo does
        # not re-open the dialog.
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the original-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.original_data = None
