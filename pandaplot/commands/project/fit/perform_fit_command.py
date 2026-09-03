# pandaplot/commands/project/fit/perform_fit_command.py
"""Command that performs a curve fit on a background thread via
TaskScheduler, instead of blocking the Qt main thread on scipy.optimize.curve_fit
(see docs/arch/09-architectural-issues.md).

Computes a preview only -- it never mutates project state (FitPanel's
"Apply" button uses a separate ApplyFitCommand for that) -- so unlike
AnalysisCommand/SignalAnalysisCommand there's no inner "apply result" command
to split out. occupies_undo_slot() is still False: computing a fit preview
was never a meaningful undoable user action.
"""

from typing import Callable, Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.services.fit.fit_service import FitResult, FitService
from pandaplot.services.qtasks.task_scheduler import TaskScheduler


class PerformFitCommand(Command):
    """Command that performs a curve fit."""

    def __init__(
        self,
        fit_service: FitService,
        fit_type: str,
        x_data,
        y_data,
        fit_points: int = 500,
        *,
        calculate_r_squared: bool = True,
        confidence_bands: bool = False,
        sigma_y=None,
        custom_function: str | None = None,
        custom_parameters: str | None = None,
        fixed_parameters: str | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        task_scheduler: TaskScheduler,
        on_complete: Optional[Callable[[CommandResult], None]] = None):
        super().__init__()

        self.fit_service = fit_service
        self.task_scheduler = task_scheduler
        self.on_complete = on_complete

        self.fit_type = fit_type
        self.x_data = x_data
        self.y_data = y_data
        self.fit_points = fit_points
        self.calculate_r_squared = calculate_r_squared
        self.confidence_bands = confidence_bands
        self.sigma_y = sigma_y

        self.custom_function = custom_function
        self.custom_parameters = custom_parameters
        self.fixed_parameters = fixed_parameters
        self.x_min = x_min
        self.x_max = x_max

        self.result: Optional[FitResult] = None
        self.error_message: Optional[str] = None
        self._is_running = False

    @override
    def occupies_undo_slot(self) -> bool:
        """Computing a fit preview was never a meaningful undoable action;
        see module docstring."""
        return False

    @override
    def execute(self) -> CommandResult:
        self.logger.debug("Executing PerformFitCommand: %s", self.fit_type)

        if self._is_running:
            self.logger.warning("PerformFitCommand: a fit is already in progress")
            return CommandResult.FAILURE

        self._is_running = True
        self.task_scheduler.run_task(
            task=self._compute_fit_task,
            on_result=self._on_fit_computed,
            on_error=self._on_fit_error,
            on_finished=self._on_fit_finished,
        )
        return CommandResult.SUCCESS

    def _compute_fit_task(self, progress_callback) -> dict:
        """Runs on a background thread. Never raises for an expected fit
        failure; returns a plain dict instead."""
        try:
            result = self.fit_service.perform_fit(
                fit_type=self.fit_type,
                x_data=self.x_data,
                y_data=self.y_data,
                fit_points=self.fit_points,
                calculate_r_squared=self.calculate_r_squared,
                confidence_bands=self.confidence_bands,
                sigma_y=self.sigma_y,
                custom_function=self.custom_function,
                custom_parameters=self.custom_parameters,
                fixed_parameters=self.fixed_parameters,
                x_min=self.x_min,
                x_max=self.x_max)
            return {"success": result is not None, "result": result, "error": None}
        except Exception as e:
            self.logger.exception("PerformFitCommand failed")
            return {"success": False, "result": None, "error": str(e)}

    def _on_fit_computed(self, outcome: dict) -> None:
        if outcome["success"]:
            self.result = outcome["result"]
            self.error_message = None
            self._notify_complete(CommandResult.SUCCESS)
        else:
            self.logger.warning(
                "PerformFitCommand.execute: fit_service returned no result for fit_type=%s",
                self.fit_type,
            )
            self.result = None
            self.error_message = outcome["error"]
            self._notify_complete(CommandResult.FAILURE)

    def _on_fit_error(self, error_info) -> None:
        _, value, _ = error_info
        self.result = None
        self.error_message = str(value)
        self._notify_complete(CommandResult.FAILURE)

    def _on_fit_finished(self) -> None:
        self._is_running = False

    def _notify_complete(self, result: CommandResult) -> None:
        if self.on_complete:
            self.on_complete(result)

    @override
    def undo(self) -> CommandResult:
        self.result = None
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the computed fit result held for undo once this command
        is dropped from the stacks for good (see Command.cleanup)."""
        self.result = None
