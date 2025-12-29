"""Command to close the current project."""
from typing import override

from pandaplot.commands.base_command import Command
from pandaplot.models.state.app_context import AppContext


class CloseProjectCommand(Command):
    """Command to close the currently loaded project."""
    
    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context

    @override
    def execute(self) -> bool:
        """Close the current project if one is loaded."""
        try:
            app_state = self.app_context.get_app_state()
            
            if not app_state.has_project:
                self.logger.info("No project is currently loaded")
                return True
            
            project_name = app_state.current_project.name if app_state.current_project else "Unknown"
            self.logger.info(f"Closing project: {project_name}")
            
            # Close the project - this will emit PROJECT_CLOSED event
            app_state.close_project()
            
            self.logger.info("Project closed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close project: {e}")
            return False

    @override
    def undo(self):
        """Undo is not supported for project closing."""
        self.logger.warning("Cannot undo project close operation")
        return False

    @override 
    def redo(self):
        """Redo is not supported for project closing."""
        self.logger.warning("Cannot redo project close operation")
        return False