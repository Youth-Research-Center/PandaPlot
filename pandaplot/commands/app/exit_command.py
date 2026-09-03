# exit_command.py
# Command to handle application exit in PandaPlot.

from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.models.events import AppEvents
from pandaplot.models.state.app_context import AppContext


class ExitCommand(Command):
    """
    Command to exit the application.
    """
    
    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context

    @override
    def execute(self) -> CommandResult:
        """
        Execute the exit command.
        """
        self.logger.info("Executing ExitCommand")
        self.app_context.event_bus.emit(AppEvents.APP_CLOSING)
        return CommandResult.SUCCESS

    @override
    def undo(self):
        """
        This is not applicable for exit command.
        """
        self.logger.error("ExitCommand cannot be undone.")
        raise NotImplementedError("Exit command cannot be undone.")

    @override
    def redo(self):
        """
        This is not applicable for exit command.
        """
        self.logger.error("ExitCommand cannot be redone.")
        raise NotImplementedError("Exit command cannot be redone.")

    @override
    def cleanup(self) -> None:
        """No undo state to release -- this command is not undoable."""
        return