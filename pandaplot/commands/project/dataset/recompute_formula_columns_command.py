"""Command that recomputes formula columns on demand (#154).

A non-live formula column keeps the values its transform last produced. This
command re-evaluates the stored expression against the current source data, as
one undoable step.
"""

from typing import override

import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.transform import formula_engine

_TITLE = "Recompute Formula"


class RecomputeFormulaColumnsCommand(Command):
    """Recompute the non-live formula columns among the given column positions.

    Columns that are not formula columns, and live ones (which recompute
    themselves), are ignored. If a selected column reads another selected one,
    the source is recomputed first. All columns are evaluated before any is
    written, so a failing formula changes nothing.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, column_positions: list[int]):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.dataset_id = dataset_id
        self.column_positions = list(column_positions)

        self.dataset: Dataset | None = None
        # Column id -> values before / after the first run; undo and redo swap
        # them back in rather than re-evaluating the formulas.
        self._old_values: dict[str, pd.Series] = {}
        self._new_values: dict[str, pd.Series] = {}

    @override
    def execute(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            found = project.find_item(self.dataset_id) if project is not None else None
            if not isinstance(found, Dataset) or found.data is None:
                self.logger.warning("RecomputeFormulaColumnsCommand.execute: dataset '%s' not found or has no data", self.dataset_id)
                self.ui_controller.show_error_message(_TITLE, f"Dataset with ID '{self.dataset_id}' not found.")
                return CommandResult.FAILURE

            targets = self._target_column_ids(found)
            if not targets:
                return CommandResult.NOOP

            df = found.data.copy()
            new_values = self._evaluate(found, df, targets)
            if new_values is None:
                return CommandResult.FAILURE

            old_values = {cid: found.data[found.column_name(cid)].copy() for cid in new_values}
            changed = [cid for cid in new_values if not old_values[cid].equals(new_values[cid])]
            if not changed:
                return CommandResult.NOOP

            self.dataset = found
            self._old_values = {cid: old_values[cid] for cid in changed}
            self._new_values = {cid: new_values[cid] for cid in changed}
            self._write(self._new_values)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.exception("RecomputeFormulaColumnsCommand.execute failed")
            self.dataset = None
            self.ui_controller.show_error_message(_TITLE, f"Failed to recompute formula columns: {e}")
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        if self.dataset is None or not self._old_values:
            self.logger.warning("RecomputeFormulaColumnsCommand.undo: nothing to undo for dataset '%s'", self.dataset_id)
            return CommandResult.FAILURE
        return self._restore(self._old_values)

    @override
    def redo(self) -> CommandResult:
        if self.dataset is None or not self._new_values:
            self.logger.warning("RecomputeFormulaColumnsCommand.redo: nothing to redo for dataset '%s'", self.dataset_id)
            return CommandResult.FAILURE
        return self._restore(self._new_values)

    @override
    def cleanup(self) -> None:
        """Drop the retained column snapshots and dataset reference."""
        self.dataset = None
        self._old_values = {}
        self._new_values = {}

    def _target_column_ids(self, dataset: Dataset) -> list[str]:
        """Ids of the selected non-live formula columns, sources before dependents."""
        selected: dict[str, list[str]] = {}
        for position in self.column_positions:
            if not 0 <= position < len(dataset.data.columns):
                continue
            column_id = dataset.column_id(str(dataset.data.columns[position]))
            spec = dataset.formula_column(column_id) if column_id is not None else None
            if column_id is not None and spec is not None and not spec.live:
                selected[column_id] = spec.source_column_ids
        return formula_engine.resolve_recompute_order(selected.keys(), selected)

    def _evaluate(self, dataset: Dataset, df: pd.DataFrame, targets: list[str]) -> dict[str, pd.Series] | None:
        """Evaluate each target against ``df`` (updated as it goes). None, after telling the user, on failure."""
        safe_globals = formula_engine.build_formula_globals()
        results: dict[str, pd.Series] = {}
        for column_id in targets:
            spec = dataset.formula_column(column_id)
            name = dataset.column_name(column_id)
            source_names = [dataset.column_name(cid) for cid in spec.source_column_ids]
            if any(source is None for source in source_names):
                self.ui_controller.show_warning_message(_TITLE, f"A source column of '{name}' no longer exists, so it can't be recomputed.")
                return None
            try:
                series = formula_engine.evaluate_formula(
                    df,
                    expression=spec.expression,
                    transform_type=spec.transform_type,
                    source_columns=[str(source) for source in source_names],
                    source_aliases=spec.source_aliases,
                    safe_globals=safe_globals,
                )
            except Exception as e:  # noqa: BLE001 -- a user-authored expression can raise anything; report it instead of crashing
                self.logger.error("Recompute of column '%s' failed: %s", name, e)
                self.ui_controller.show_warning_message(_TITLE, f"Could not recompute '{name}': {e}")
                return None
            df[name] = series
            results[column_id] = df[name].copy()
        return results

    def _restore(self, values: dict[str, pd.Series]) -> CommandResult:
        """Write ``values`` back, refusing if a column has gone missing."""
        names = {cid: self.dataset.column_name(cid) for cid in values}
        if any(name is None or name not in self.dataset.data.columns for name in names.values()):
            self.logger.warning("RecomputeFormulaColumnsCommand: a recomputed column no longer exists in dataset '%s'", self.dataset_id)
            return CommandResult.ABORTED
        self._write(values)
        return CommandResult.SUCCESS

    def _write(self, values: dict[str, pd.Series]) -> None:
        df = self.dataset.data.copy()
        for column_id, series in values.items():
            df[self.dataset.column_name(column_id)] = series
        self.dataset.set_data(df)
        last_row = max(len(df) - 1, 0)
        for column_id in values:
            col = int(df.columns.get_loc(self.dataset.column_name(column_id)))
            self.app_context.event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED,
                DatasetDataChangedData(dataset_id=self.dataset_id, start_index=(0, col), end_index=(last_row, col)).to_dict(),
            )
