from typing import override
from pandaplot.commands.base_command import Command
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.services.data_managers.project_manager import ProjectManager


class SaveProjectCommand(Command):
    """
    Command to save the current project.
    This will save the project to its current file path, or prompt for a new path if needed.
    """
    
    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.project_manager = ProjectManager()
        self.save_as_path = None
        self.previous_file_path = None
        
    @override
    def execute(self) -> bool:
        """Execute the save project command."""
        try:
            # Check if we have a project to save
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Save Project", 
                    "No project is currently loaded to save."
                )
                return False

            project = self.app_state.current_project
            if not project:  # Additional safety check
                self.ui_controller.show_warning_message(
                    "Save Project", 
                    "No project is currently loaded to save."
                )
                return False

            current_path = self.app_state.project_file_path
            
            # Determine the save path
            if self.save_as_path:
                # This is a "Save As" operation with specified path
                save_path = self.save_as_path
            elif current_path:
                # This is a regular save to existing file
                save_path = current_path
            else:
                # This is a new project, need to prompt for save location
                save_path = self.ui_controller.show_save_project_dialog(
                    default_name=f"{project.name}.pplot"
                )
                if not save_path:
                    return False  # User cancelled

            # Store previous path for undo
            self.previous_file_path = current_path
            
            # Save the project
            success = self.project_manager.save_project(project, save_path)
            
            if success:
                # Update app state with new file path (if it changed)
                if save_path != current_path:
                    self.app_state.load_project(project, save_path)
                
                # Emit save event
                self.app_state.event_bus.emit('project_saved', {
                    'project': project,
                    'file_path': save_path,
                    'previous_path': current_path
                })
                
                print(f"SaveProjectCommand: Successfully saved project '{project.name}' to '{save_path}'")
                
                # Show success message for Save As operations
                if self.save_as_path or not current_path:
                    self.ui_controller.show_info_message(
                        "Project Saved", 
                        f"Project '{project.name}' has been saved to:\n{save_path}"
                    )
                return True
            else:
                # TODO: we probably should raise exception here, but check command executor
                raise Exception("Save operation failed")
                
        except Exception as e:
            error_msg = f"Failed to save project: {str(e)}"
            print(f"SaveProjectCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Save Project Error", error_msg)
            raise
    
    def undo(self):
        """Undo the save project command by reverting file path changes."""
        try:
            # Only need to undo if the file path changed
            if self.previous_file_path != self.app_state.project_file_path:
                if self.app_state.has_project:
                    project = self.app_state.current_project
                    if project:  # Additional safety check
                        self.app_state.load_project(project, self.previous_file_path)
                        print(f"SaveProjectCommand: Reverted file path to '{self.previous_file_path}'")
                
        except Exception as e:
            error_msg = f"Failed to undo save project: {str(e)}"
            print(f"SaveProjectCommand Undo Error: {error_msg}")
            self.ui_controller.show_error_message("Undo Error", error_msg)
            
    def redo(self):
        """Redo the save project command."""
        self.execute()

class SaveProjectAsCommand(SaveProjectCommand):
    """
    Command to save the current project with a new file path (Save As).
    This always prompts for a new file location.
    """
    
    def __init__(self, app_context: AppContext):
        super().__init__(app_context)

    @override
    def execute(self) -> bool:
        """Execute the save as command."""
        try:
            # Check if we have a project to save
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Save Project As", 
                    "No project is currently loaded to save."
                )
                return False

            project = self.app_state.current_project
            if not project:  # Additional safety check
                self.ui_controller.show_warning_message(
                    "Save Project As", 
                    "No project is currently loaded to save."
                )
                return False

            # Always prompt for new save location
            save_path = self.ui_controller.show_save_project_dialog(
                default_name=f"{project.name}.pplot"
            )
            if not save_path:
                return False  # User cancelled

            # Set the save path and delegate to parent
            self.save_as_path = save_path
            return super().execute()

                
        except Exception as e:
            error_msg = f"Failed to save project as: {str(e)}"
            print(f"SaveProjectAsCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Save Project As Error", error_msg)
            raise
