from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.services.fit.fit_service import FitResult, FitService


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
        fixed_parameters: str | None = None):
        super().__init__()

        self.fit_service = fit_service

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

        self.result: Optional[FitResult] = None
        self.error_message: Optional[str] = None

    @override
    def execute(self) -> bool:
        self.logger.debug("Executing PerformFitCommand: %s", self.fit_type)

        try:
            self.result = self.fit_service.perform_fit(
                fit_type=self.fit_type,
                x_data=self.x_data,
                y_data=self.y_data,
                fit_points=self.fit_points,
                calculate_r_squared=self.calculate_r_squared,
                confidence_bands=self.confidence_bands,
                sigma_y=self.sigma_y,
                custom_function=self.custom_function,
                custom_parameters=self.custom_parameters,
                fixed_parameters=self.fixed_parameters)

            if self.result is None:
                self.logger.warning(
                    "PerformFitCommand.execute: fit_service returned no result for fit_type=%s",
                    self.fit_type,
                )
                return False

            return True

        except Exception as e:
            self.logger.exception("PerformFitCommand failed")
            self.result = None
            self.error_message = str(e)
            return False

    @override
    def undo(self) -> bool:
        self.result = None
        return True

    @override
    def redo(self) -> bool:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the computed fit result held for undo once this command
        is dropped from the stacks for good (see Command.cleanup)."""
        self.result = None
