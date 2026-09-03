"""
Command for running a signal analysis on a background thread.

`run_analysis_async` drives the non-undoable preview path (SignalPanel's
"Run" button); `execute` drives the undo-tracked "Add to Project" path,
dispatching the same computation and then -- once the result is back --
running ApplySignalAnalysisResultCommand, which is the command that actually
occupies an undo slot. See analysis_command.py for the identical pattern.
"""

from typing import Any, Callable, Dict, Optional, override

from pandaplot.analysis import (
    SignalAnalysisResult,
    SignalAnalysisType,
    SignalEngine,
)
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class SignalAnalysisCommand(Command):
    """
    Runs a signal analysis on a source dataset column, either as a
    non-undoable preview (run_analysis_async) or committed as a new project
    dataset (execute).
    """

    def __init__(
        self,
        app_context: AppContext,
        source_dataset_id: str,
        analysis_type: SignalAnalysisType,
        column_name: str,
        sampling_rate: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        on_complete: Optional[Callable[[CommandResult], None]] = None,
    ):
        super().__init__()

        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler = app_context.get_task_scheduler()

        self.source_dataset_id = source_dataset_id
        self.analysis_type = analysis_type
        self.column_name = column_name
        self.sampling_rate = sampling_rate
        self.parameters = parameters or {}

        self.result_name = result_name
        self.folder_id = folder_id
        self.on_complete = on_complete

        self.result_dataset_id: Optional[str] = None
        self.result: Optional[SignalAnalysisResult] = None
        self._is_running = False
        # The project active at dispatch time, so a project switch while the
        # computation runs in the background can be detected and the result
        # rejected instead of silently landing in whatever project happens
        # to be current when the background thread finishes.
        self._dispatch_project = None

    def _get_source_dataset(self) -> Optional[Dataset]:
        project = self.app_state.current_project
        if not project:
            return None
        item = project.find_item(self.source_dataset_id)
        return item if isinstance(item, Dataset) else None

    def _compute_signal_task(self, progress_callback, column) -> dict:
        """Runs on a background thread. Never raises for an expected
        computation failure; returns a plain dict instead."""
        try:
            result = SignalEngine.run_analysis(
                analysis_type=self.analysis_type,
                column=column,
                sampling_rate=self.sampling_rate,
                **self.parameters,
            )
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            self.logger.error("Signal analysis computation failed: %s", e, exc_info=True)
            return {"success": False, "result": None, "error": str(e)}

    def run_analysis_async(self, on_complete: Callable[[Optional[SignalAnalysisResult], Optional[str]], None]) -> None:
        """Non-undoable preview path: computes a SignalAnalysisResult on a
        background thread and reports it (or an error message) via
        on_complete(result, error). Does not touch the project."""
        source = self._get_source_dataset()
        if source is None or source.data is None:
            on_complete(None, "Source dataset is not available.")
            return
        if self.column_name not in source.data.columns:
            on_complete(None, f"Column not found: {self.column_name}")
            return
        column = source.data[self.column_name].copy()

        def _on_result(outcome: dict) -> None:
            if outcome["success"]:
                self.result = outcome["result"]
                on_complete(self.result, None)
            else:
                self.result = None
                on_complete(None, outcome["error"])

        def _on_error(error_info) -> None:
            _, value, _ = error_info
            self.result = None
            on_complete(None, str(value))

        self.task_scheduler.run_task(
            task=self._compute_signal_task,
            task_arguments={"column": column},
            on_result=_on_result,
            on_error=_on_error,
        )

    @override
    def occupies_undo_slot(self) -> bool:
        """The real, undoable effect is ApplySignalAnalysisResultCommand,
        executed once the background computation's result is back (see
        _on_commit_computed)."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Commit path ("Add to Project"): validate, dispatch the
        computation, and return SUCCESS once dispatched -- not once the
        dataset is actually created; use on_complete for that."""
        try:
            self.logger.info("Executing SignalAnalysisCommand (%s)", self.analysis_type.value)

            if self._is_running:
                self.logger.warning("Signal analysis already in progress")
                return CommandResult.FAILURE

            if not self.app_state.has_project or not self.app_state.current_project:
                message = "No project loaded; cannot run signal analysis."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Signal Analysis Error", message)
                return CommandResult.FAILURE

            source = self._get_source_dataset()
            if source is None or source.data is None:
                message = "Source dataset is not available."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Signal Analysis Error", message)
                return CommandResult.FAILURE

            if self.column_name not in source.data.columns:
                message = f"Column not found: {self.column_name}"
                self.logger.warning(message)
                self.ui_controller.show_error_message("Signal Analysis Error", message)
                return CommandResult.FAILURE

            column = source.data[self.column_name].copy()

            self._dispatch_project = self.app_state.current_project
            self._is_running = True
            self.task_scheduler.run_task(
                task=self._compute_signal_task,
                task_arguments={"column": column},
                on_result=self._on_commit_computed,
                on_error=self._on_commit_error,
                on_finished=self._on_commit_finished,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Signal analysis failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Signal Analysis Error", str(e))
            self._is_running = False
            return CommandResult.FAILURE

    def _on_commit_computed(self, outcome: dict) -> None:
        if not outcome["success"]:
            self.ui_controller.show_error_message("Signal Analysis Error", outcome["error"] or "Signal analysis failed")
            self._notify_complete(CommandResult.FAILURE)
            return

        if self.app_state.current_project is not self._dispatch_project:
            # The project changed (or was closed) while this computation was
            # running in the background -- adding the result to whatever
            # project happens to be current now would silently attach it to
            # the wrong project.
            message = "The project changed while the signal analysis was running. The result was discarded."
            self.logger.warning(message)
            self.ui_controller.show_warning_message("Signal Analysis Cancelled", message)
            self._notify_complete(CommandResult.FAILURE)
            return

        apply_command = ApplySignalAnalysisResultCommand(
            self.app_context, self.result_name, self.folder_id, outcome["result"],
        )
        executor = self.app_context.get_command_executor()
        if executor.execute_command(apply_command):
            self.result = outcome["result"]
            self.result_dataset_id = apply_command.result_dataset_id
            self._notify_complete(CommandResult.SUCCESS)
        else:
            self._notify_complete(CommandResult.FAILURE)

    def _on_commit_error(self, error_info) -> None:
        error_type, error_value, error_traceback = error_info
        message = f"Signal analysis failed with {error_type.__name__}: {error_value}"
        self.logger.error(message)
        self.logger.error(error_traceback)
        self.ui_controller.show_error_message("Signal Analysis Error", message)
        self._notify_complete(CommandResult.FAILURE)

    def _on_commit_finished(self) -> None:
        self._is_running = False

    def _notify_complete(self, result: CommandResult) -> None:
        if self.on_complete:
            self.on_complete(result)

    @override
    def undo(self) -> CommandResult:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        self.result_dataset_id = None
        self.result = None
