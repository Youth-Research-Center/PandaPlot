import logging
import os
from pathlib import Path

from pandaplot.models.project import Project
from pandaplot.storage.project_data_manager import ProjectDataManager


class ProjectManager:
    """
    Service responsible for project file operations.

    Callers go through this rather than reaching into ProjectDataManager
    directly, so the on-disk project file format (currently a zip archive
    with per-item files, see ProjectDataManager) stays an implementation
    detail behind file-level concerns (extension/existence validation)
    that would otherwise be duplicated at every call site.
    """

    def __init__(self, project_data_manager: ProjectDataManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._project_data_manager = project_data_manager
        self.supported_extensions = [".pplot"]
        self.logger.debug("ProjectManager initialized with supported extensions: %s", self.supported_extensions)
        
    def create_project(self, name: str) -> Project:
        """Create a new empty project."""
        self.logger.info("Creating new project: '%s'", name)
        try:
            project = Project(name=name, description=f"New project: {name}")
            self.logger.debug("Successfully created project object for '%s' with %d items", 
                            name, len(project.get_all_items()))
            return project
        except Exception as e:
            self.logger.error("Failed to create project '%s': %s", name, str(e))
            raise

    def load_project(self, file_path: str) -> Project:
        """
        Load a project from a file.

        Args:
            file_path (str): Path to the project file

        Returns:
            Project: The loaded project

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        self.logger.info("Attempting to load project from: %s", file_path)

        if not os.path.exists(file_path):
            error_msg = f"Project file not found: {file_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        path = Path(file_path)
        if path.suffix not in self.supported_extensions:
            error_msg = f"Unsupported file format: {path.suffix}. Supported: {self.supported_extensions}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        project = self._project_data_manager.load(file_path)

        self.logger.info(
            "Successfully loaded project '%s' with %d items from %s",
            project.name, len(project.get_all_items()), file_path,
        )
        return project

    def save_project(self, project: Project, file_path: str) -> bool:
        """
        Save a project to a file.

        Args:
            project (Project): The project to save
            file_path (str): Path where to save the project

        Returns:
            bool: True if successful

        Raises:
            ValueError: If the file format is not supported
        """
        self.logger.info("Saving project '%s' to: %s", project.name, file_path)

        path = Path(file_path)
        if path.suffix not in self.supported_extensions:
            error_msg = f"Unsupported file format: {path.suffix}. Supported: {self.supported_extensions}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        path.parent.mkdir(parents=True, exist_ok=True)
        self._project_data_manager.save(project, file_path)

        self.logger.info("Successfully saved project '%s' to: %s", project.name, file_path)
        return True
    
    def get_recent_projects(self) -> list:
        """Get list of recently opened projects."""
        # TODO(#210): Implement recent projects tracking
        return []
    
    def validate_project_file(self, file_path: str) -> bool:
        """
        Validate if a file is a valid project file.
        
        Args:
            file_path (str): Path to the file to validate
            
        Returns:
            bool: True if valid project file
        """
        try:
            if not os.path.exists(file_path):
                return False
                
            path = Path(file_path)
            if path.suffix not in self.supported_extensions:
                return False
            
            return True
        except Exception:
            return False
