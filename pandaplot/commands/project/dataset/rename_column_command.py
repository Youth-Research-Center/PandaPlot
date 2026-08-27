"""Command for renaming a dataset column, cascading to chart/fit references."""

from typing import List, Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.events.event_data import DatasetColumnRenamedData
from pandaplot.models.events.event_types import ChartEvents, DatasetOperationEvents
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class RenameColumnCommand(Command):
    """Rename a dataset column and update chart/fit references to it.

    The DataFrame rename and the reference cascade are one undoable step;
    series/fit labels are user-editable text and are never modified.
    """

    def __init__(self, app_context: AppContext, dataset_id: str,
                 column_index: int, new_name: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.column_index = column_index
        self.new_name = new_name.strip()
        self.old_name: Optional[str] = None
        self.dataset: Optional[Dataset] = None
        self._applied: bool = False

    @override
    def execute(self) -> bool:
        try:
            if not self.app_state.has_project or not self.app_state.current_project:
                self.logger.warning(
                    "RenameColumnCommand.execute: no project open; cannot rename column in dataset '%s'",
                    self.dataset_id,
                )
                self.ui_controller.show_warning_message(
                    "Rename Column", "Please open or create a project first.")
                return False
            project = self.app_state.current_project

            found_item = project.find_item(self.dataset_id)
            if not isinstance(found_item, Dataset) or found_item.data is None:
                self.logger.warning(
                    "RenameColumnCommand.execute: dataset '%s' not found or has no data",
                    self.dataset_id,
                )
                self.ui_controller.show_error_message(
                    "Rename Column", f"Dataset with ID '{self.dataset_id}' not found.")
                return False
            self.dataset = found_item

            columns = list(self.dataset.data.columns)
            if not (0 <= self.column_index < len(columns)):
                self.logger.warning(
                    "RenameColumnCommand.execute: column_index %s out of range for dataset '%s' (%d columns)",
                    self.column_index, self.dataset_id, len(columns),
                )
                self.ui_controller.show_error_message(
                    "Rename Column", f"Column index {self.column_index} is out of range.")
                return False

            self.old_name = columns[self.column_index]
            if not self.new_name:
                self.logger.warning(
                    "RenameColumnCommand.execute: new column name is empty for dataset '%s' index %s",
                    self.dataset_id, self.column_index,
                )
                self.ui_controller.show_error_message(
                    "Rename Column", "Column name cannot be empty.")
                return False
            if self.new_name == self.old_name:
                return False
            if self.new_name in columns:
                self.logger.warning(
                    "RenameColumnCommand.execute: column name '%s' already exists in dataset '%s'",
                    self.new_name, self.dataset_id,
                )
                self.ui_controller.show_error_message(
                    "Rename Column",
                    f"A column named '{self.new_name}' already exists in this dataset.")
                return False

            self._apply_rename(self.old_name, self.new_name)
            self._applied = True
            return True

        except Exception as e:
            error_msg = f"Failed to rename column: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Rename Column Error", error_msg)
            return False

    def _apply_rename(self, from_name: str, to_name: str) -> None:
        """Rename the column and notify; do not rewrite series references.

        Series/fits reference the column by its stable id, so the rename only
        needs to update the dataset's id->name registry (in place, keeping the
        id) and the DataFrame. Charts that use the column are refreshed via
        events rather than by mutating their series — that's the whole point of
        the column id: the reference survives the rename untouched.
        """
        if self.dataset is None or self.dataset.data is None:
            return
        # Update the id registry first (preserves the column's id), then the
        # DataFrame, keeping the two in sync.
        self.dataset.rename_column(from_name, to_name)
        self.dataset.data.rename(columns={from_name: to_name}, inplace=True)
        self.dataset.update_modified_time()

        affected_charts = self._charts_referencing_column(to_name)

        self.app_context.event_bus.emit(
            DatasetOperationEvents.DATASET_COLUMN_RENAMED,
            DatasetColumnRenamedData(
                dataset_id=self.dataset_id,
                column_index=self.column_index,
                old_name=from_name,
                new_name=to_name,
            ).to_dict())
        for chart in affected_charts:
            chart.update_modified_time()
            self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
                "chart_id": chart.id,
                "chart": chart,
            })

    def _charts_referencing_column(self, current_name: str) -> List[Chart]:
        """Return charts whose series/fits reference the renamed column.

        Matched by column id (via the dataset registry) with a name fallback
        for legacy references that never got an id. Nothing is mutated — this
        only decides which charts to refresh.
        """
        project = self.app_state.current_project
        if not project or self.dataset is None:
            return []
        column_id = self.dataset.column_id(current_name)

        def series_refs(series) -> bool:
            id_fields = [series.x_column_id, series.y_column_id]
            name_fields = [series.x_column, series.y_column]

            error_bars = getattr(series.style, "error_bars", None)
            if error_bars is not None:
                id_fields.extend([
                    error_bars.x_error_column_id, error_bars.y_error_column_id,
                    error_bars.x_error_minus_column_id, error_bars.y_error_minus_column_id,
                ])
                name_fields.extend([
                    error_bars.x_error_column, error_bars.y_error_column,
                    error_bars.x_error_minus_column, error_bars.y_error_minus_column,
                ])

            if isinstance(series.style, VectorSeriesStyle):
                id_fields.extend([
                    series.style.u_column_id, series.style.v_column_id,
                    series.style.magnitude_column_id,
                ])
                name_fields.extend([
                    series.style.u_column, series.style.v_column,
                    series.style.magnitude_column,
                ])

            if column_id and column_id in id_fields:
                return True
            return current_name in name_fields or self.old_name in name_fields

        def fit_refs(fit) -> bool:
            if column_id and column_id in (fit.source_x_column_id, fit.source_y_column_id):
                return True
            names = (fit.source_x_column, fit.source_y_column)
            return current_name in names or self.old_name in names

        affected: List[Chart] = []
        for item in project.get_all_items():
            if not isinstance(item, Chart):
                continue
            uses = any(s.dataset_id == self.dataset_id and series_refs(s)
                       for s in item.data_series)
            uses = uses or any(f.source_dataset_id == self.dataset_id and fit_refs(f)
                               for f in item.fit_data)
            if uses:
                affected.append(item)
        return affected

    @override
    def undo(self):
        """Rename back and restore references (same walk, names swapped)."""
        if self._applied and self.old_name is not None:
            self._apply_rename(self.new_name, self.old_name)

    @override
    def redo(self):
        """Re-apply the rename and reference cascade."""
        if self._applied and self.old_name is not None:
            self._apply_rename(self.old_name, self.new_name)

    @override
    def cleanup(self) -> None:
        """Release the live Dataset reference held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.dataset = None
