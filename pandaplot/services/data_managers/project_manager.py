import json
import logging
import os
from pathlib import Path
from pandaplot.models.project import Project


class ProjectManager:
    """
    Service responsible for project file operations.
    Handles loading, saving, and creating projects.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_extensions = ['.pplot']
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
        
        try:
            self.logger.debug("Reading project file: %s", file_path)
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            # Validate required fields
            if not isinstance(data, dict):
                error_msg = "Project file must contain a JSON object"
                self.logger.error("Invalid project file format in %s: %s", file_path, error_msg)
                raise ValueError(error_msg)
                
            self.logger.debug("Parsing project data from %s", file_path)
            project: Project = Project.from_dict(data)
            
            item_count = len(project.get_all_items())
            self.logger.info("Successfully loaded project '%s' with %d items from %s", 
                           project.name, item_count, file_path)
            
            return project
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in project file: {str(e)}"
            self.logger.error("JSON decode error in %s: %s", file_path, error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Error loading project: {str(e)}"
            self.logger.error("Unexpected error loading project from %s: %s", file_path, error_msg)
            raise ValueError(error_msg)

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
            IOError: If writing fails
        """
        self.logger.info("Saving project '%s' to: %s", project.name, file_path)
        
        path = Path(file_path)
        if path.suffix not in self.supported_extensions:
            error_msg = f"Unsupported file format: {path.suffix}. Supported: {self.supported_extensions}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            # Ensure directory exists
            self.logger.debug("Creating directory structure for: %s", file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert project to dictionary
            self.logger.debug("Converting project '%s' to dictionary format", project.name)
            data = project.to_dict()
            
            # Save to file
            self.logger.debug("Writing project data to file: %s", file_path)
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                
            self.logger.info("Successfully saved project '%s' to: %s", project.name, file_path)
            return True
            
        except Exception as e:
            error_msg = f"Error saving project: {str(e)}"
            self.logger.error("Failed to save project '%s' to %s: %s", project.name, file_path, error_msg)
            raise IOError(error_msg)
    
    def get_recent_projects(self) -> list:
        """Get list of recently opened projects."""
        # TODO: Implement recent projects tracking
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

            #TODO: Implement project file validation
        except Exception:
            return False
