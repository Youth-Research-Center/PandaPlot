from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.models.project import Project
from pandaplot.models.state.app_context import AppContext


class LoadProjectCommand(Command):
    """
    Command to load a project into the application state.
    This command follows the MVC pattern by:
    - Being triggered by UI components
    - Using services (ProjectManager) to load data
    - Updating app state which emits events to update UI
    """

    def __init__(self, app_context: AppContext, file_path: str):
        super().__init__()
        self.app_state = app_context.app_state
        self.app_context = app_context
        self.file_path = file_path
        self.previous_project: Optional[Project] = None
        self.previous_file_path: Optional[str] = None
        self.loaded_project: Optional[Project] = None

    @override
    def execute(self) -> bool:
        """Execute the load project command."""
        try:
            # Store current state for undo
            self.previous_project = self.app_state.current_project
            self.previous_file_path = self.app_state.project_file_path

            # Update app state (this will emit events)
            self.app_state.load_project_from_file(self.file_path)
            return True

        except Exception as e:
            # If loading fails, ensure state remains consistent
            # TODO: instead of raising an exception, we could return False
            # and ensure the state is handled well.
            raise Exception(
                f"Failed to load project from {self.file_path}: {str(e)}")

    def undo(self):
        """Undo the load project command."""
        if self.previous_project is not None:
            self.app_state.load_project(self.previous_project)
        else:
            self.app_state.close_project()

    def redo(self):
        """Redo the load project command."""
        if self.loaded_project is not None:
            self.app_state.load_project(self.loaded_project)
        else:
            # Re-execute if we don't have the loaded project cached
            self.execute()
