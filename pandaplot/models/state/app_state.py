import logging
from pandaplot.models.events import EventBus
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from typing import Optional

from pandaplot.storage.project_data_manager import ProjectDataManager


class AppState:
    """
    Central application state that manages the current project and emits events
    when state changes occur.
    """
    
    def __init__(self, event_bus: EventBus, project_data_manager: ProjectDataManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_bus = event_bus

        # encapsulate project data manager inside project manager
        self.project_data_manager = project_data_manager

        self._current_project: Optional[Project] = None
        
    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self._current_project
    
    @property
    def project_file_path(self) -> Optional[str]:
        """Get the file path of the currently loaded project."""
        return self._current_project.project_file_path if self._current_project else None

    @property
    def has_project(self) -> bool:
        """Check if a project is currently loaded."""
        return self._current_project is not None
    
    def load_project(self, project: Project):
        """
        Load a project into the application state.
        
        Args:
            project (Project): The project to load
            file_path (str, optional): The file path where the project is stored
        """
        self.logger.info(f"Loading project: {project.name}")
        old_project = self._current_project
        self._current_project = project
        
        # Emit events
        self.event_bus.emit(ProjectEvents.PROJECT_LOADED, {
            'project': project,
            'previous_project': old_project
        })
        
        if old_project is None:
            # TODO: this should be removed
            self.event_bus.emit(ProjectEvents.FIRST_PROJECT_LOADED, {
                'project': project
            })

    def load_project_from_file(self, file_path):
        self.logger.info(f"Loading project from file: {file_path}")
        project = self.project_data_manager.load(file_path)
        if project:
            self.load_project(project)

    def close_project(self):
        """Close the currently loaded project."""
        self.logger.info("Closing project")
        if self._current_project is not None:
            # TODO: add support for multiple projects
            old_project = self._current_project
            
            self._current_project = None

            self.event_bus.emit(ProjectEvents.PROJECT_CLOSED, {
                'project': old_project
            })
    
    def save_project(self, file_path: Optional[str] = None) -> bool:
        """
        Save the current project.
        
        Args:
            file_path (str, optional): New file path to save to. If None, uses current path.
        """
        if self._current_project is None:
            return False
        self.logger.info(f"Saving project {self._current_project.name} to {file_path}")
        # TODO: this shouldn't be in the application state. 
        if self._current_project is None:
            # TODO: consider returning false
            raise ValueError("No project loaded to save")
        
        save_path = file_path or self.project_file_path
        if save_path is None:
            # TODO: consider returning false
            raise ValueError("No file path specified for saving")
        
        # Update the stored path if a new one was provided
        if file_path is not None:
            self._current_project.project_file_path = file_path

        self.event_bus.emit(ProjectEvents.PROJECT_SAVING, {
            'project': self._current_project,
            'file_path': save_path
        })
        
        # TODO: Implement actual saving logic in a service
        # TODO: make saving async since it's a file operation
        self.project_data_manager.save(self._current_project, save_path)

        self.event_bus.emit(ProjectEvents.PROJECT_SAVED, {
            'project': self._current_project,
            'file_path': save_path
        })

        return True