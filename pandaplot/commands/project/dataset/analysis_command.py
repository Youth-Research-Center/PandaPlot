"""
Analysis command: validates inputs and runs the actual mathematical
computation (scipy cubic splines, Savitzky-Golay filters, cumulative
integrals) on a background thread via TaskScheduler, instead of blocking the
Qt main thread (see docs/arch/09-architectural-issues.md).

This command never occupies an undo slot: the real, undoable effect is
ApplyAnalysisResultCommand, executed once the background computation's result
comes back (see _on_analysis_computed). This mirrors the pattern established
by CreateChartFromWizardCommand for #185/#186 -- there is no "analysis started
but nothing happened yet" state sitting on the undo stack.
"""

from typing import Any, Callable, Dict, Optional, override

import pandas as pd

from pandaplot.analysis import AnalysisEngine, AnalysisType
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.dataset.apply_analysis_result_command import ApplyAnalysisResultCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class AnalysisCommand(Command):
    """
    Validates analysis inputs and dispatches the computation to a background
    thread. See module docstring for the undo-tracking split with
    ApplyAnalysisResultCommand.
    """

    def __init__(
        self,
        app_context: AppContext,
        dataset_id: str,
        analysis_config: Dict[str, Any],
        on_complete: Optional[Callable[[CommandResult], None]] = None,
    ):
        """
        Initialize analysis command.

        Args:
            app_context: Application context
            dataset_id: ID of the dataset to analyze
            analysis_config: Configuration dictionary with:
                - analysis_type: str - type of analysis ('derivative', 'integral', etc.)
                - x_column: str - X-axis column name
                - y_column: str - Y-axis column name
                - new_column_name: str - name for the result column
                - replace_existing: bool - whether to replace existing column
                - parameters: dict - analysis-specific parameters
            on_complete: called with the final CommandResult once the
                dispatched computation and (on success) the resulting
                ApplyAnalysisResultCommand have both finished. Lets callers
                (e.g. AnalysisPanel) react to completion instead of reading
                execute()'s return value, which now only means "dispatched".
        """
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler = app_context.get_task_scheduler()
        self.dataset_id = dataset_id
        self.analysis_config = analysis_config
        self.on_complete = on_complete

        # State captured at dispatch time, needed once the result is back.
        self.dataset: Optional[Dataset] = None
        self.column_existed_before = False
        self.original_data = None
        self._is_running = False
        # The project active at dispatch time, so a project switch (e.g. to
        # another copy of a project persisting the same dataset id) while
        # the computation runs in the background can be detected and the
        # result rejected instead of silently applying it to whatever
        # project happens to be current when the background thread
        # finishes. Mirrors SignalAnalysisCommand._on_commit_computed().
        self._dispatch_project = None

        # Extract config
        self.analysis_type = AnalysisType(analysis_config["analysis_type"])
        self.x_column = analysis_config["x_column"]
        self.y_column = analysis_config["y_column"]
        self.new_column_name = analysis_config["new_column_name"]
        self.replace_existing = analysis_config.get("replace_existing", False)
        self.parameters = analysis_config.get("parameters", {})

    @override
    def occupies_undo_slot(self) -> bool:
        """The real, undoable effect is ApplyAnalysisResultCommand (see module
        docstring). Kept False so this dispatcher never sits on the undo
        stack in an incomplete state."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Validate inputs and dispatch the computation. Returns SUCCESS once
        dispatched -- not once the analysis is actually applied; use
        on_complete for that."""
        try:
            self.logger.info("Executing AnalysisCommand")

            if self._is_running:
                self.logger.warning("Analysis operation already in progress")
                self.ui_controller.show_info_message("Analysis In Progress", "An analysis is already running.")
                return CommandResult.FAILURE

            self.dataset = self._get_dataset()
            if not self.dataset:
                message = f"Dataset {self.dataset_id} not found"
                self.logger.warning(f"Analysis execution failed: {message}")
                self.ui_controller.show_error_message("Analysis Error", message)
                return CommandResult.FAILURE

            if not self._validate_inputs():
                return CommandResult.FAILURE

            df = self.dataset.data
            if df is None:
                message = "Dataset is empty"
                self.logger.warning(f"Analysis execution failed: {message}")
                self.ui_controller.show_error_message("Analysis Error", message)
                return CommandResult.FAILURE

            self._store_original_state(df)

            # Hand the background task only a copy of the columns it actually
            # reads (see _execute_analysis) -- never the live DataFrame.
            # EditCommand/EditBatchCommand mutate dataset.data in place
            # synchronously on the main thread, and pandas is not thread-safe
            # for concurrent read+mutate on the same object. x_column and
            # y_column may be the same column, so dedupe to avoid selecting
            # a duplicate-named pair (which would turn df[self.x_column]
            # into a DataFrame instead of a Series inside _execute_analysis).
            needed_columns = list(dict.fromkeys([self.x_column, self.y_column]))
            analysis_df = df[needed_columns].copy()

            self._dispatch_project = self.app_context.get_app_state().current_project
            self._is_running = True
            self.task_scheduler.run_task(
                task=self._compute_analysis_task,
                task_arguments={"df": analysis_df},
                on_result=self._on_analysis_computed,
                on_error=self._on_analysis_error,
                on_finished=self._on_analysis_finished,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error(f"Analysis execution failed: {e}")
            self.ui_controller.show_error_message("Analysis Error", str(e))
            self._is_running = False
            return CommandResult.FAILURE

    def _compute_analysis_task(self, progress_callback, df: pd.DataFrame) -> dict:
        """Runs on a background thread (TaskScheduler/QThreadPool). Takes only
        the plain DataFrame captured at dispatch time -- no AppContext/Dataset
        object crosses the thread boundary. Never raises for an expected
        computation failure (bad parameters, scipy errors); returns a plain
        dict instead, since that's what safely crosses back via Qt's `result`
        signal (a single `object`)."""
        try:
            result = self._execute_analysis(df)
            if result is None:
                return {"success": False, "error": "Analysis returned no result", "result": None}
            return {"success": True, "error": None, "result": result}
        except Exception as e:
            self.logger.error(f"Analysis computation failed: {e}")
            return {"success": False, "error": str(e), "result": None}

    def _on_analysis_computed(self, outcome: dict) -> None:
        """Runs on the main thread (Worker signals are queued back to it)."""
        try:
            if not outcome["success"]:
                self.ui_controller.show_error_message("Analysis Error", outcome["error"] or "Analysis failed")
                self._notify_complete(CommandResult.FAILURE)
                return

            if self.app_context.get_app_state().current_project is not self._dispatch_project:
                # The project changed (or was closed) while this computation
                # was running in the background -- re-resolving the dataset
                # now would look it up in whatever project happens to be
                # current, which could be a different project that persists
                # a dataset with the same id.
                message = "The project changed while the analysis was running. The result was discarded."
                self.logger.warning(message)
                self.ui_controller.show_warning_message("Analysis Cancelled", message)
                self._notify_complete(CommandResult.FAILURE)
                return

            # Re-check the target column's current state rather than trusting
            # the snapshot taken at dispatch time: another command may have
            # added/removed a column of the same name while this one's
            # computation was running in the background, and applying with a
            # stale column_existed_before/original_data would silently drop
            # or misrestore that other command's contribution on undo.
            current_dataset = self._get_dataset()
            if current_dataset is not None and current_dataset.data is not None:
                self._store_original_state(current_dataset.data)

            apply_command = ApplyAnalysisResultCommand(
                self.app_context,
                self.dataset_id,
                self.new_column_name,
                outcome["result"].result_data,
                self.column_existed_before,
                self.original_data,
            )
            executor = self.app_context.get_command_executor()
            if executor.execute_command(apply_command):
                self._notify_complete(CommandResult.SUCCESS)
            else:
                self._notify_complete(CommandResult.FAILURE)

        except Exception as e:
            self.logger.error(f"Error applying analysis result: {e}")
            self.ui_controller.show_error_message("Analysis Error", str(e))
            self._notify_complete(CommandResult.FAILURE)

    def _on_analysis_error(self, error_info) -> None:
        """Only reached for a bug in this command's own glue code -- expected
        computation failures are caught inside _compute_analysis_task and
        reported through _on_analysis_computed instead."""
        error_type, error_value, error_traceback = error_info
        message = f"Analysis failed with {error_type.__name__}: {error_value}"
        self.logger.error(message)
        self.logger.error(error_traceback)
        self.ui_controller.show_error_message("Analysis Error", message)
        self._notify_complete(CommandResult.FAILURE)

    def _on_analysis_finished(self) -> None:
        self._is_running = False

    def _notify_complete(self, result: CommandResult) -> None:
        if self.on_complete:
            self.on_complete(result)

    @override
    def undo(self) -> CommandResult:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False.
        Undoing the applied column is ApplyAnalysisResultCommand's job. Kept
        as a no-op only to satisfy the abstract Command interface."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        """See undo() -- unreachable via CommandExecutor for the same reason."""
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False, so
        this command is never pushed onto a stack for cleanup() to apply to."""
        return

    def _get_dataset(self) -> Dataset | None:
        """Get dataset from app context."""
        try:
            app_state = self.app_context.get_app_state()
            if app_state.has_project and app_state.current_project:
                project = app_state.current_project
                dataset_item = project.find_item(self.dataset_id)
                if dataset_item and hasattr(dataset_item, "data") and isinstance(dataset_item, Dataset):
                    return dataset_item
            return None
        except Exception as e:
            self.logger.error(f"Error getting dataset: {e}")
            return None

    def _validate_inputs(self) -> bool:
        """Validate all required inputs are present and valid."""
        if not self.new_column_name.strip():
            message = "New column name cannot be empty"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
            return False

        if self.dataset is None or not hasattr(self.dataset, "data") or self.dataset.data is None:
            message = "Dataset has no data"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
            return False

        df = self.dataset.data

        missing_columns = []
        if self.x_column not in df.columns:
            missing_columns.append(self.x_column)
        if self.y_column not in df.columns:
            missing_columns.append(self.y_column)

        if missing_columns:
            message = f"Source columns not found: {missing_columns}"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
            return False

        if self.new_column_name in df.columns and not self.replace_existing:
            message = f"Column '{self.new_column_name}' already exists"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
            return False

        if not pd.api.types.is_numeric_dtype(df[self.x_column]):
            message = f"X column '{self.x_column}' must be numeric"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
            return False

        if not pd.api.types.is_numeric_dtype(df[self.y_column]):
            message = f"Y column '{self.y_column}' must be numeric"
            self.logger.error(f"Error: {message}")
            self.ui_controller.show_error_message("Analysis Error", message)
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

    def _execute_analysis(self, df: pd.DataFrame):
        """Execute the specific analysis operation. Called on the background
        thread from _compute_analysis_task."""
        x_data = df[self.x_column]
        y_data = df[self.y_column]

        start_index = self.parameters.get("start_index", 0)
        end_index = self.parameters.get("end_index", -1)
        method = self.parameters.get("method", "central")

        if self.analysis_type == AnalysisType.DERIVATIVE:
            return AnalysisEngine.calculate_derivative(
                x_data, y_data, method, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.INTEGRAL:
            return AnalysisEngine.calculate_integral(
                x_data, y_data, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.ARC_LENGTH:
            return AnalysisEngine.calculate_arc_length(
                x_data, y_data, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.SMOOTHING:
            additional_params = {k: v for k, v in self.parameters.items()
                                 if k not in ["start_index", "end_index", "method"]}
            return AnalysisEngine.smooth_data(
                x_data, y_data, method, start_index, end_index, **additional_params
            )
        elif self.analysis_type == AnalysisType.INTERPOLATION:
            num_points = self.parameters.get("num_points", None)
            return AnalysisEngine.interpolate_data(
                x_data, y_data, method, num_points, start_index, end_index
            )
        else:
            self.logger.error(f"Unknown analysis type: {self.analysis_type}")
            return None
