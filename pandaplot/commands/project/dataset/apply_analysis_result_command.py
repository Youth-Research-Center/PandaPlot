"""Command that writes an already-computed analysis result column onto a
dataset, with undo/redo support.

Split out of AnalysisCommand so the background scipy computation
(AnalysisCommand, dispatched via TaskScheduler) and the actual, undo-tracked
project mutation are separate commands: AnalysisCommand never occupies an
undo slot (see its occupies_undo_slot() override), and this command -- built
only once the computation's result is back -- is the one CommandExecutor
actually pushes onto the undo stack. See docs/arch/09-architectural-issues.md,
"Analysis operations block the Qt main thread".
"""

from typing import Optional, Union, override

import numpy as np
import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.dataset.column_change_events import emit_columns_changed
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class ApplyAnalysisResultCommand(Command):
    """Writes a precomputed analysis result column onto a dataset."""

    def __init__(
        self,
        app_context: AppContext,
        dataset_id: str,
        new_column_name: str,
        result_series: Union[pd.Series, np.ndarray],
        *,
        column_existed_before: bool,
        original_data: Optional[pd.Series],
    ):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.dataset_id = dataset_id
        self.new_column_name = new_column_name
        self.result_series = result_series
        self.column_existed_before = column_existed_before
        self.original_data = original_data

        self.dataset: Optional[Dataset] = None

    def _get_dataset(self) -> Optional[Dataset]:
        project = get_current_project(self.app_context)
        if project is not None:
            dataset_item = project.find_item(self.dataset_id)
            if dataset_item and hasattr(dataset_item, "data") and isinstance(dataset_item, Dataset):
                return dataset_item
        return None

    @override
    def execute(self) -> CommandResult:
        try:
            self.dataset = self._get_dataset()
            if not self.dataset or self.dataset.data is None:
                message = f"Dataset {self.dataset_id} is no longer available"
                self.logger.warning("ApplyAnalysisResultCommand.execute: %s", message)
                self.ui_controller.show_error_message("Analysis Error", message)
                return CommandResult.FAILURE

            df = self.dataset.data
            df_copy = df.copy()

            result_series = self.result_series
            if isinstance(result_series, pd.Series) and result_series.index.isin(df_copy.index).all():
                # Index-aligned assignment: for segment analyses (derivative /
                # integral / arc length over a sub-range) the result carries the
                # original row index, so pandas places each value on its source
                # row and leaves the rest of the column as NaN.
                df_copy[self.new_column_name] = result_series
                self.logger.info(
                    "Index-aligned assignment: column '%s' set on %d of %d rows",
                    self.new_column_name, len(result_series), len(df_copy))
            else:
                # Result does not map onto existing rows (e.g. interpolation
                # resamples to a new grid): fill from the top, best effort.
                df_copy[self.new_column_name] = pd.NA
                df_copy.iloc[:len(result_series), df_copy.columns.get_loc(
                    self.new_column_name)] = np.asarray(result_series)
                self.logger.info(
                    "Positional assignment: column '%s' added, shape now: %s",
                    self.new_column_name, df_copy.shape)

            self.dataset.set_data(df_copy)
            emit_columns_changed(
                self.app_context, self.dataset_id, self.dataset.data,
                added_columns=[] if self.column_existed_before else [self.new_column_name],
                replaced_columns=[self.new_column_name] if self.column_existed_before else [],
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error(f"ApplyAnalysisResultCommand execution failed: {e}")
            self.ui_controller.show_error_message("Analysis Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not self.dataset or not isinstance(self.dataset, Dataset):
                self.logger.warning("Undo failed: Invalid dataset reference")
                return CommandResult.FAILURE

            df = self.dataset.data
            if df is None:
                self.logger.warning("Undo failed: No data in dataset")
                return CommandResult.FAILURE

            from pandaplot.models.events.event_data import (
                DatasetColumnsRemovedData,
                DatasetDataChangedData,
            )
            from pandaplot.models.events.event_types import (
                DatasetEvents,
                DatasetOperationEvents,
            )
            event_bus = self.app_context.get_app_state().event_bus

            if self.column_existed_before and self.original_data is not None:
                df_copy = df.copy()
                df_copy[self.new_column_name] = self.original_data
                self.dataset.set_data(df_copy)
                col = int(df_copy.columns.get_loc(self.new_column_name))
                event_bus.emit(
                    DatasetEvents.DATASET_DATA_CHANGED,
                    DatasetDataChangedData(
                        dataset_id=self.dataset_id,
                        start_index=(0, col),
                        end_index=(max(len(df_copy) - 1, 0), col),
                    ).to_dict(),
                )
            elif not self.column_existed_before and self.new_column_name in df.columns:
                df_copy = df.copy()
                removed_pos = int(df_copy.columns.get_loc(self.new_column_name))
                df_copy = df_copy.drop(columns=[self.new_column_name])
                self.dataset.set_data(df_copy)
                event_bus.emit(
                    DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                    DatasetColumnsRemovedData(
                        dataset_id=self.dataset_id,
                        column_positions=[removed_pos],
                    ).to_dict(),
                )

            self.logger.info("Analysis undone successfully: %s", self.new_column_name)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error(f"ApplyAnalysisResultCommand undo failed: {e}")
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the original-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.original_data = None
