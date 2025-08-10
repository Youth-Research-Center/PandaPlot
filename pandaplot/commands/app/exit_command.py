# exit_command.py
# Command to handle application exit in PandaPlot.

from typing import override
from pandaplot.commands.base_command import Command
from pandaplot.models.events.event_types import AppEvents
from pandaplot.models.state.app_context import AppContext

class ExitCommand(Command):
    """
    Command to exit the application.
    """
    
    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context

    @override
    def execute(self):
        """
        Execute the exit command.
        """
        self.app_context.event_bus.emit(AppEvents.APP_CLOSING)

    @override
    def undo(self):
        """
        This is not applicable for exit command.
        """
        raise NotImplementedError("Exit command cannot be undone.")

    @override
    def redo(self):
        """
        This is not applicable for exit command.
        """
        raise NotImplementedError("Exit command cannot be redone.")