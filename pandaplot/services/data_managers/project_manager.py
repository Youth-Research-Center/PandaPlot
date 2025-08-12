import json
import os
from pathlib import Path
from pandaplot.models.project.project import Project


class ProjectManager:
    """
    Service responsible for project file operations.
    Handles loading, saving, and creating projects.
    """
    
    def __init__(self):
        self.supported_extensions = ['.pplot']
        
    def create_project(self, name: str) -> Project:
        """Create a new empty project."""
        print(f"Creating new project '{name}'")
        project = Project(name=name, description=f"New project: {name}")
        return project

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
        print(f"Loading project from '{file_path}'")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Project file not found: {file_path}")
        
        path = Path(file_path)
        if path.suffix not in self.supported_extensions:
            raise ValueError(f"Unsupported file format: {path.suffix}. Supported: {self.supported_extensions}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            # Validate required fields
            if not isinstance(data, dict):
                raise ValueError("Project file must contain a JSON object")
                
            project:Project = Project.from_dict(data)
            print(f"Successfully loaded project '{project.name}' with {len(project.get_all_items())} tables")
            return project
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in project file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error loading project: {str(e)}")

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
        print(f"Saving project '{project.name}' to '{file_path}'")
        
        path = Path(file_path)
        if path.suffix not in self.supported_extensions:
            raise ValueError(f"Unsupported file format: {path.suffix}. Supported: {self.supported_extensions}")
        
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert project to dictionary
            data = project.to_dict()
            
            # Save to file
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                
            print(f"Successfully saved project to '{file_path}'")
            return True
            
        except Exception as e:
            raise IOError(f"Error saving project: {str(e)}")
    
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
            """with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
            # Basic validation - check if it has required project fields
            required_fields = ['name', 'version']
            return all(field in data for field in required_fields)"""
            
        except Exception:
            return False
