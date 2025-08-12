from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project.project import Project
from typing import Optional

from pandaplot.storage.project_data_manager import ProjectDataManager


class AppState:
    """
    Central application state that manages the current project and emits events
    when state changes occur.
    """
    
    def __init__(self, event_bus: EventBus, project_data_manager: ProjectDataManager):
        self.event_bus = event_bus
        self.project_data_manager = project_data_manager
        self._current_project: Optional[Project] = None
        # TODO: move to the project model or project container model
        self._project_file_path: Optional[str] = None  
        
    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self._current_project
    
    @property
    def project_file_path(self) -> Optional[str]:
        """Get the file path of the currently loaded project."""
        return self._project_file_path
    
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
        old_project = self._current_project
        self._current_project = project
        
        # Emit events
        self.event_bus.emit('project_loaded', {
            'project': project,
            'previous_project': old_project
        })
        
        if old_project is None:
            # TODO: this should be removed
            self.event_bus.emit('first_project_loaded', {
                'project': project
            })

    def load_project_from_file(self, file_path):
        project = self.project_data_manager.load(file_path)
        if project:
            self.load_project(project)

    def close_project(self):
        """Close the currently loaded project."""
        if self._current_project is not None:
            # TODO: add support for multiple projects
            old_project = self._current_project
            old_file_path = self._project_file_path
            
            self._current_project = None
            self._project_file_path = None
            
            self.event_bus.emit('project_closed', {
                'project': old_project,
                'file_path': old_file_path
            })
    
    def save_project(self, file_path: Optional[str] = None):
        """
        Save the current project.
        
        Args:
            file_path (str, optional): New file path to save to. If None, uses current path.
        """
        # TODO: this shouldn't be in the application state. 
        if self._current_project is None:
            raise ValueError("No project loaded to save")
        
        save_path = file_path or self._project_file_path
        if save_path is None:
            raise ValueError("No file path specified for saving")
        
        # Update the stored path if a new one was provided
        if file_path is not None:
            self._project_file_path = file_path
        
        self.event_bus.emit('project_saving', {
            'project': self._current_project,
            'file_path': save_path
        })
        
        # TODO: Implement actual saving logic in a service
        self.project_data_manager.save(self._current_project, save_path)
        
        self.event_bus.emit('project_saved', {
            'project': self._current_project,
            'file_path': save_path
        })
