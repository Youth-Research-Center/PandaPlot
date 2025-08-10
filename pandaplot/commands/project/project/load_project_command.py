from pandaplot.commands.base_command import Command
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.project.project import Project
from pandaplot.services.data_managers.project_manager import ProjectManager
from typing import Optional, override


class LoadProjectCommand(Command):
    """
    Command to load a project into the application state.
    This command follows the MVC pattern by:
    - Being triggered by UI components
    - Using services (ProjectManager) to load data
    - Updating app state which emits events to update UI
    """
    
    def __init__(self, app_context:AppContext, file_path:str):
        self.app_state = app_context.app_state
        self.app_context = app_context
        self.project_manager = ProjectManager()
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
            
            # Load project using service
            self.loaded_project = self.project_manager.load_project(self.file_path)
            
            # Update app state (this will emit events)
            self.app_state.load_project(self.loaded_project, self.file_path)
            return True

        except Exception as e:
            # If loading fails, ensure state remains consistent
            # TODO: instead of raising an exception, we could return False
            # and ensure the state is handled well.
            raise Exception(f"Failed to load project from {self.file_path}: {str(e)}")
    
    def undo(self):
        """Undo the load project command."""
        if self.previous_project is not None:
            self.app_state.load_project(self.previous_project, self.previous_file_path)
        else:
            self.app_state.close_project()
    
    def redo(self):
        """Redo the load project command."""
        if self.loaded_project is not None:
            self.app_state.load_project(self.loaded_project, self.file_path)
        else:
            # Re-execute if we don't have the loaded project cached
            self.execute()
