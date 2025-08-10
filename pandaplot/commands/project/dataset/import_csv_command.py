import uuid
from pandaplot.commands.base_command import Command
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController
from typing import Optional, override
import pandas as pd
import os


class ImportCsvCommand(Command):
    """
    Command to import a CSV file as a dataset in the project.
    """

    def __init__(self, app_context: AppContext, folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.folder_id = folder_id
        self.file_path = None  # Path to the CSV file, can be set later
        self.dataset_name = None
        
        # Store state for undo
        self.dataset_id = None
        self.imported_data = None
        self.project = None

    @override
    def execute(self) -> bool:
        """Execute the import CSV command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Import CSV", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_state.current_project
            if not self.project:
                return False
            
            # Get file path
            self.file_path = self.ui_controller.show_import_csv_dialog()
            if not self.file_path:
                return False  # User cancelled
            
            # Validate file exists
            if not os.path.exists(self.file_path):
                self.ui_controller.show_error_message(
                    "Import CSV", 
                    f"File not found: {self.file_path}"
                )
                return False
            
            # Try to read the CSV file
            try:
                df = pd.read_csv(self.file_path)
                if df.empty:
                    self.ui_controller.show_warning_message(
                        "Import CSV", 
                        "The selected CSV file is empty."
                    )
                    return False
                    
                self.imported_data = df
                
            except Exception as e:
                self.ui_controller.show_error_message(
                    "Import CSV Error", 
                    f"Failed to read CSV file:\n{str(e)}"
                )
                return False
            
            # Get dataset name if not provided
            self.dataset_name = os.path.splitext(os.path.basename(self.file_path))[0]
            
            # Create dataset ID
            self.dataset_id = str(uuid.uuid4())
            dataset = Dataset(
                id=self.dataset_id,
                name=self.dataset_name,
                data=self.imported_data,
                source_file=self.file_path
            )
            self.project.add_item(dataset, parent_id=self.folder_id)

            # Emit event
            self.app_state.event_bus.emit('dataset_imported', {
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset_name,
                'folder_id': self.folder_id,
                'dataset_data': dataset.data,
                'file_path': self.file_path,
                'dataframe': self.imported_data
            })

            print(f"ImportCsvCommand: Imported CSV '{self.dataset_name}' from '{self.file_path}' with ID '{self.dataset_id}'")

            # Show success message to user
            self.ui_controller.show_info_message(
                "Import CSV", 
                f"Successfully imported '{self.dataset_name}'\n"
                f"Rows: {self.imported_data.shape[0]}, Columns: {self.imported_data.shape[1]}"
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to import CSV: {str(e)}"
            print(f"ImportCsvCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Import CSV Error", error_msg)
            return False
    
    def undo(self):
        """Undo the import CSV command."""
        try:
            if self.dataset_id and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    dataset = project.find_item(self.dataset_id)
                    if dataset:
                        project.remove_item(dataset)
                    
                    # Emit event
                    self.app_state.event_bus.emit('dataset_removed', {
                        'project': project,
                        'dataset_id': self.dataset_id,
                        'dataset_data': self.imported_data
                    })

                    print(f"ImportCsvCommand: Undone import of dataset '{self.dataset_id}'")

        except Exception as e:
            error_msg = f"Failed to undo CSV import: {str(e)}"
            print(f"ImportCsvCommand Undo Error: {error_msg}")
            self.ui_controller.show_error_message("Undo Error", error_msg)
    
    def redo(self):
        """Redo the import CSV command."""
        try:
            if self.dataset_id and self.imported_data is not None and self.app_state.has_project:
                # Re-execute the command with the same parameters
                return self.execute()
        except Exception as e:
            error_msg = f"Failed to redo CSV import: {str(e)}"
            print(f"ImportCsvCommand Redo Error: {error_msg}")
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
