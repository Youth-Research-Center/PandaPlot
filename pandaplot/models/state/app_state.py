import logging
from typing import Optional

from pandaplot.models.events import EventBus
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project


class AppState:
    """
    Central application state that manages the current project and emits events
    when state changes occur.
    """
    
    def __init__(self, event_bus: EventBus):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_bus = event_bus

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
            "project": project,
            "previous_project": old_project
        })
        
        if old_project is None:
            # TODO: this should be removed
            self.event_bus.emit(ProjectEvents.FIRST_PROJECT_LOADED, {
                "project": project
            })

    def close_project(self):
        """Close the currently loaded project."""
        self.logger.info("Closing project")
        if self._current_project is not None:
            # TODO: add support for multiple projects
            old_project = self._current_project
            
            self._current_project = None

            self.event_bus.emit(ProjectEvents.PROJECT_CLOSED, {
                "project": old_project
            })
    
    