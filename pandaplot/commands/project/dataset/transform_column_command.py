"""
Transform column command for applying data transformations with undo/redo support.
"""

from typing import Any, override

import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.dataset.column_change_events import emit_columns_changed
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.transform import formula_engine


class TransformColumnCommand(Command):
    """
    Command to apply data transformation to a dataset column.
    Integrates with existing command system for undo/redo support.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, transform_config: dict[str, Any]):
        """
        Initialize transform command.

        Args:
            app_context: Application context
            dataset_id: ID of the dataset to transform
            transform_config: Configuration dictionary with:
                - new_column_name: str - name for the new/modified column
                - transform_type: str - 'column', 'row', 'multi_column'
                - source_columns: list - source column names
                - expression: str - transformation expression
                - replace_existing: bool - whether to replace existing column
                - as_formula: bool - remember the expression on the column so it
                  can be recomputed later (#154), instead of writing static values
                - live: bool - recompute the formula column automatically when a
                  source column changes (implies as_formula)
        """
        super().__init__()
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.transform_config = transform_config

        # State for undo/redo
        self.original_data = None
        self.column_existed_before = False
        self.dataset = None

        # Set to the reason execute()/undo() returned False, so callers (the
        # transform panel) can surface it instead of a generic message.
        self.error_message: str | None = None

        # Extract config
        self.new_column_name = transform_config["new_column_name"]
        self.transform_type = transform_config["transform_type"]
        self.source_columns = transform_config["source_columns"]
        self.expression = transform_config["expression"]
        self.replace_existing = transform_config.get("replace_existing", False)
        self.live = bool(transform_config.get("live", False))
        # "Live" is meaningless without a stored formula, so it implies it.
        self.as_formula = bool(transform_config.get("as_formula", False)) or self.live

        # Formula-registry state for undo: which column id we registered a
        # spec on, and what (if anything) was registered there before.
        self._formula_column_id: str | None = None
        self._previous_formula_spec: FormulaColumnSpec | None = None

    @override
    def execute(self) -> CommandResult:
        """Execute the transformation and add new column to dataset."""
        try:
            self.logger.info("Executing TransformColumnCommand")
            # Get dataset from app context
            self.dataset = self._get_dataset()
            if not self.dataset:
                self.error_message = f"Dataset {self.dataset_id} not found"
                self.logger.warning(self.error_message)
                return CommandResult.FAILURE

            # Ensure we have a Dataset object
            if not isinstance(self.dataset, Dataset):
                self.error_message = f"Retrieved item is not a Dataset: {type(self.dataset)}"
                self.logger.warning(self.error_message)
                return CommandResult.FAILURE

            # Validate inputs
            if not self._validate_inputs():
                return CommandResult.FAILURE

            # Get current dataframe
            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.error_message = "Dataset has no data"
                self.logger.warning(self.error_message)
                return CommandResult.FAILURE

            df = self.dataset.data.copy()  # Work with a copy

            # Store original state for undo
            self._store_original_state(df)

            # Build and vet the formula spec before touching any data, so a
            # circular formula is rejected without half-applying it.
            formula_spec = None
            if self.as_formula:
                formula_spec = self._build_formula_spec(self.dataset)
                if formula_spec is None:
                    return CommandResult.FAILURE
                if not self._validate_no_cycle(self.dataset, formula_spec):
                    return CommandResult.FAILURE

            # Execute transformation
            result_series = self._execute_transform_logic(df)
            if result_series is None:
                return CommandResult.FAILURE

            # Apply result to dataframe
            df[self.new_column_name] = result_series

            # Update dataset using proper method
            self.dataset.set_data(df)

            # Register/detach before emitting: the live-recompute listener
            # reacts to the events below and must see a consistent formula
            # registry. A plain (non-formula) run must detach any formula a
            # *previous* run left on this column -- otherwise the spec
            # would silently survive, and the next source-column edit would
            # have the live-recompute listener overwrite the static values
            # just written here with that stale formula's output.
            self._apply_formula_registry_change(self.dataset, formula_spec)

            # Refresh the data tab and column-source selectors.
            emit_columns_changed(
                self.app_context, self.dataset_id, self.dataset.data,
                added_columns=[] if self.column_existed_before else [self.new_column_name],
                replaced_columns=[self.new_column_name] if self.column_existed_before else [],
            )

            self.logger.info(
                f"Transform applied: '{self.new_column_name}' created from {self.source_columns}")
            return CommandResult.SUCCESS

        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
            self.error_message = str(e)
            self.logger.error(f"Transform execution failed: {e}")
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        """Remove the added column from dataset or restore original data."""
        try:
            if not self.dataset or not isinstance(self.dataset, Dataset):
                self.logger.warning(
                    "TransformColumnCommand.undo: cannot undo for dataset '%s' (dataset found=%s)",
                    self.dataset_id, self.dataset is not None,
                )
                return CommandResult.FAILURE

            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.logger.warning(
                    "TransformColumnCommand.undo: dataset '%s' has no data to restore",
                    self.dataset_id,
                )
                return CommandResult.FAILURE

            df = self.dataset.data.copy()

            # Drop (or restore) the formula spec first: set_data() below prunes
            # specs for columns that no longer exist, and restoring a spec on a
            # column this undo is about to remove would be pointless anyway.
            self._restore_formula_registry(self.dataset)

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
                # Restore original column data
                df[self.new_column_name] = self.original_data
                self.dataset.set_data(df)
                col = int(df.columns.get_loc(self.new_column_name))
                event_bus.emit(
                    DatasetEvents.DATASET_DATA_CHANGED,
                    DatasetDataChangedData(
                        dataset_id=self.dataset_id,
                        start_index=(0, col),
                        end_index=(max(len(df) - 1, 0), col),
                    ).to_dict(),
                )
            else:
                removed_pos = None
                if self.new_column_name in df.columns:
                    # Remove the new column
                    removed_pos = int(df.columns.get_loc(self.new_column_name))
                    df = df.drop(columns=[self.new_column_name])
                self.dataset.set_data(df)
                if removed_pos is not None:
                    event_bus.emit(
                        DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                        DatasetColumnsRemovedData(
                            dataset_id=self.dataset_id,
                            column_positions=[removed_pos],
                        ).to_dict(),
                    )

            self.logger.info(f"Transform undone: '{self.new_column_name}' reverted")
            return CommandResult.SUCCESS

        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
            self.logger.error(f"Transform undo failed: {e}")
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        """Re-execute the transformation."""
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the original-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.original_data = None
        self._previous_formula_spec = None

    def _get_dataset(self):
        """Get dataset from app context."""
        try:
            project = get_current_project(self.app_context)
            if project is not None:
                return project.find_item(self.dataset_id)
            return None
        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
            self.logger.error(f"Error getting dataset: {e}")
            return None

    def _validate_inputs(self) -> bool:
        """Validate all required inputs are present and valid."""
        if not self.new_column_name.strip():
            self.error_message = "New column name cannot be empty"
            self.logger.error(self.error_message)
            return False

        if not self.expression.strip():
            self.error_message = "Transform expression cannot be empty"
            self.logger.error(self.error_message)
            return False

        if not self.source_columns:
            self.error_message = "At least one source column must be selected"
            self.logger.error(self.error_message)
            return False

        # Check if dataset is available
        if not self.dataset or not isinstance(self.dataset, Dataset):
            self.error_message = "Dataset not available for validation"
            self.logger.error(self.error_message)
            return False

        # Get dataframe for validation
        try:
            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.error_message = "Dataset has no data"
                self.logger.error(self.error_message)
                return False
            df = self.dataset.data
        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
            self.error_message = f"Cannot access dataset dataframe: {e}"
            self.logger.error(self.error_message)
            return False

        # Check if source columns exist
        missing_columns = [
            col for col in self.source_columns if col not in df.columns]
        if missing_columns:
            self.error_message = f"Source columns not found: {missing_columns}"
            self.logger.error(self.error_message)
            return False

        # Check if target column exists and handle accordingly
        if self.new_column_name in df.columns and not self.replace_existing:
            self.error_message = (
                f"Column '{self.new_column_name}' already exists. "
                "Enable replace option or choose different name."
            )
            self.logger.error(self.error_message)
            return False

        return True

    def _store_original_state(self, df: pd.DataFrame):
        """Store original state for undo operations."""
        if self.new_column_name in df.columns:
            self.column_existed_before = True
            self.original_data = df[self.new_column_name].copy()
        else:
            self.column_existed_before = False
            self.original_data = None

    def _execute_transform_logic(self, df: pd.DataFrame) -> pd.Series | None:
        """Execute transformation using the shared formula engine, so a
        one-shot transform and a live recompute of the same expression can
        never diverge (#154)."""
        try:
            return formula_engine.evaluate_formula(
                df,
                expression=self.expression,
                transform_type=self.transform_type,
                source_columns=self.source_columns,
            )
        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
            self.error_message = str(e)
            self.logger.error(f"Transform logic execution failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Formula-column registration (#154)
    # ------------------------------------------------------------------
    def _build_formula_spec(self, dataset: Dataset) -> FormulaColumnSpec | None:
        """Resolve the source columns to stable ids and build the spec.

        Sets error_message and returns None if a source column has no id (it
        would leave the formula pointing at nothing).
        """
        source_ids: list[str] = []
        for name in self.source_columns:
            cid = dataset.column_id(name)
            if cid is None:
                self.error_message = f"Column '{name}' has no stable id; cannot save it as a formula source."
                self.logger.error(self.error_message)
                return None
            source_ids.append(cid)
        return FormulaColumnSpec(
            expression=self.expression,
            transform_type=self.transform_type,
            source_column_ids=source_ids,
            live=self.live,
        )

    def _validate_no_cycle(self, dataset: Dataset, spec: FormulaColumnSpec) -> bool:
        """Reject a formula that would close a dependency cycle.

        Only relevant when the target column already exists -- a brand new
        column can't yet be anybody's source. Checked here, at creation time,
        rather than when a recompute cascade trips over it.
        """
        target_id = dataset.column_id(self.new_column_name)
        if target_id is None:
            return True

        dependencies = {
            cid: existing.source_column_ids
            for cid, existing in dataset.formula_columns.items()
            if cid != target_id
        }
        dependencies[target_id] = spec.source_column_ids

        cycle = formula_engine.find_circular_dependency(dependencies)
        if cycle is None:
            return True

        names = [dataset.column_name(cid) or cid for cid in cycle]
        self.error_message = (
            "This formula would create a circular dependency: " + " -> ".join(names)
        )
        self.logger.error(self.error_message)
        return False

    def _apply_formula_registry_change(self, dataset: Dataset, spec: FormulaColumnSpec | None) -> None:
        """Make the formula registry match this run's outcome.

        `spec` registers/updates the formula on the (now existing) target
        column's id. `None` means this run was a plain transform -- if the
        target column previously held a formula (e.g. it's being reused for
        a fresh, non-formula run), that stale spec is detached so it can't
        resurface later.
        """
        target_id = dataset.column_id(self.new_column_name)
        if target_id is None:
            if spec is not None:
                self.logger.warning(
                    "Transform target '%s' has no stable id; formula not saved", self.new_column_name,
                )
            return
        previous = dataset.formula_column(target_id)
        if spec is None and previous is None:
            return  # Nothing registered before, nothing to register now.
        self._formula_column_id = target_id
        self._previous_formula_spec = previous
        if spec is not None:
            dataset.set_formula_column(target_id, spec)
        else:
            dataset.remove_formula_column(target_id)

    def _restore_formula_registry(self, dataset: Dataset) -> None:
        """Undo whatever _apply_formula_registry_change did."""
        if self._formula_column_id is None:
            return
        if self._previous_formula_spec is None:
            dataset.remove_formula_column(self._formula_column_id)
        else:
            dataset.set_formula_column(self._formula_column_id, self._previous_formula_spec)
        self._formula_column_id = None
        self._previous_formula_spec = None
