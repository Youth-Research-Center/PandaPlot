"""
Preprocess column command for applying preprocessing transformations
(centering, standardizing, scaling) with undo/redo support.
"""

from typing import Any, Dict, List, Optional, Tuple, override

import pandas as pd

from pandaplot.analysis import PreprocessingEngine, PreprocessingMethod
from pandaplot.analysis.preprocessing_types import PREPROCESSING_METHODS
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.dataset.column_change_events import emit_columns_changed
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class PreprocessColumnCommand(Command):
    """
    Command to apply a preprocessing transformation to one or more dataset
    columns, creating a new (or replacing an existing) column per source column.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, config: Dict[str, Any]):
        """
        Initialize the preprocessing command.

        Args:
            app_context: Application context.
            dataset_id: ID of the dataset to transform.
            config: Configuration dictionary with:
                - method: str - preprocessing method value ('center', 'standardize', ...)
                - source_columns: list[str] - columns to transform
                - params: dict - method-specific parameters (optional)
                - replace_existing: bool - overwrite the source column in place
                - column_names: dict[str, str] - explicit result names per source
                  column (optional; auto-generated when omitted)
        """
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.dataset_id = dataset_id
        self.config = config

        self.method = PreprocessingMethod(config["method"])
        self.source_columns: List[str] = list(config["source_columns"])
        self.params: Dict[str, Any] = config.get("params", {})
        self.replace_existing: bool = config.get("replace_existing", False)
        self.column_names: Dict[str, str] = config.get("column_names", {})

        # State for undo/redo: (target_column, existed_before, original_data)
        self.dataset: Optional[Dataset] = None
        self._undo_state: List[Tuple[str, bool, Optional[pd.Series]]] = []

    def _target_name(self, source_column: str) -> str:
        """Resolve the result column name for a source column."""
        if source_column in self.column_names and self.column_names[source_column].strip():
            return self.column_names[source_column].strip()
        if self.replace_existing:
            return source_column
        suffix = PREPROCESSING_METHODS[self.method].suffix
        return f"{source_column}_{suffix}"

    @override
    def execute(self) -> CommandResult:
        """Apply the transformation and add/replace the result columns."""
        try:
            self.logger.info(
                "Executing PreprocessColumnCommand (%s) on %s",
                self.method.value, self.source_columns,
            )
            self.dataset = self._get_dataset()
            if not isinstance(self.dataset, Dataset):
                self.logger.warning("Dataset %s not found", self.dataset_id)
                self.ui_controller.show_error_message(
                    "Preprocessing Error", f"Dataset '{self.dataset_id}' not found."
                )
                return CommandResult.FAILURE

            if not self._validate_inputs():
                return CommandResult.FAILURE

            df = self.dataset.data.copy()
            self._undo_state = []
            added_columns: List[str] = []
            replaced_columns: List[str] = []

            for source_column in self.source_columns:
                result = PreprocessingEngine.transform(
                    self.method, df[source_column], self.params
                )
                target = self._target_name(source_column)

                existed_before = target in df.columns
                original = df[target].copy() if existed_before else None
                self._undo_state.append((target, existed_before, original))
                (replaced_columns if existed_before else added_columns).append(target)

                df[target] = result.data

            self.dataset.set_data(df)
            emit_columns_changed(
                self.app_context, self.dataset_id, self.dataset.data,
                added_columns, replaced_columns,
            )
            self.logger.info(
                "Preprocessing applied: %s columns transformed with '%s'",
                len(self.source_columns), self.method.value,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Preprocessing execution failed: %s", e)
            self.ui_controller.show_error_message("Preprocessing Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        """Restore replaced columns and drop newly created ones."""
        try:
            if not isinstance(self.dataset, Dataset) or self.dataset.data is None:
                self.logger.warning(
                    "PreprocessColumnCommand.undo: cannot undo for dataset '%s' (dataset found=%s)",
                    self.dataset_id, isinstance(self.dataset, Dataset),
                )
                return CommandResult.FAILURE

            df = self.dataset.data.copy()
            removed_positions: List[int] = []
            restored_columns: List[str] = []
            # Reverse order so re-created columns are handled before their sources.
            for target, existed_before, original in reversed(self._undo_state):
                if existed_before and original is not None:
                    df[target] = original
                    restored_columns.append(target)
                elif target in df.columns:
                    removed_positions.append(int(df.columns.get_loc(target)))
                    df = df.drop(columns=[target])

            self.dataset.set_data(df)
            self._emit_undo_events(removed_positions, restored_columns)
            self.logger.info("Preprocessing undone (%s)", self.method.value)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Preprocessing undo failed: %s", e)
            return CommandResult.FAILURE

    def _emit_undo_events(self, removed_positions, restored_columns) -> None:
        """Refresh the table after an undo (columns dropped / values restored)."""
        from pandaplot.models.events.event_data import (
            DatasetColumnsRemovedData,
            DatasetDataChangedData,
        )
        from pandaplot.models.events.event_types import (
            DatasetEvents,
            DatasetOperationEvents,
        )

        assert self.dataset is not None and self.dataset.data is not None
        event_bus = self.app_context.get_app_state().event_bus
        if removed_positions:
            event_bus.emit(
                DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                DatasetColumnsRemovedData(
                    dataset_id=self.dataset_id,
                    column_positions=sorted(removed_positions),
                ).to_dict(),
            )
        if restored_columns:
            last_row = max(len(self.dataset.data) - 1, 0)
            for name in restored_columns:
                col = int(self.dataset.data.columns.get_loc(name))
                event_bus.emit(
                    DatasetEvents.DATASET_DATA_CHANGED,
                    DatasetDataChangedData(
                        dataset_id=self.dataset_id,
                        start_index=(0, col),
                        end_index=(last_row, col),
                    ).to_dict(),
                )

    @override
    def redo(self) -> CommandResult:
        """Re-apply the transformation."""
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the per-column undo state held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self._undo_state = []

    def _get_dataset(self) -> Optional[Dataset]:
        """Get the dataset from the app context."""
        try:
            project = get_current_project(self.app_context)
            if project is not None:
                item = project.find_item(self.dataset_id)
                if isinstance(item, Dataset):
                    return item
            return None
        except Exception as e:
            self.logger.error("Error getting dataset: %s", e)
            return None

    def _validate_inputs(self) -> bool:
        """Validate columns exist, are numeric, and targets do not collide."""
        if self.dataset is None or self.dataset.data is None:
            message = "Dataset has no data"
            self.logger.error(message)
            self.ui_controller.show_error_message("Preprocessing Error", message)
            return False

        if not self.source_columns:
            message = "No source columns selected"
            self.logger.error(message)
            self.ui_controller.show_error_message("Preprocessing Error", message)
            return False

        df = self.dataset.data

        missing = [c for c in self.source_columns if c not in df.columns]
        if missing:
            message = f"Source columns not found: {missing}"
            self.logger.error(message)
            self.ui_controller.show_error_message("Preprocessing Error", message)
            return False

        non_numeric = [
            c for c in self.source_columns
            if not pd.api.types.is_numeric_dtype(df[c])
        ]
        if non_numeric:
            message = f"Preprocessing requires numeric columns; not numeric: {non_numeric}"
            self.logger.error(message)
            self.ui_controller.show_error_message("Preprocessing Error", message)
            return False

        # Guard against overwriting an existing column that the user did not
        # opt into replacing.
        seen_targets: set[str] = set()
        for source_column in self.source_columns:
            target = self._target_name(source_column)
            if target in seen_targets:
                message = f"Multiple source columns map to the same result column '{target}'"
                self.logger.error(message)
                self.ui_controller.show_error_message("Preprocessing Error", message)
                return False
            seen_targets.add(target)

            overwrites_existing = target in df.columns and target != source_column
            if overwrites_existing and not self.replace_existing:
                message = f"Column '{target}' already exists. Enable replace or rename."
                self.logger.error(message)
                self.ui_controller.show_error_message("Preprocessing Error", message)
                return False

        return True
