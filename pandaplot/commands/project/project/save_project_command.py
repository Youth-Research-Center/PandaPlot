from typing import override, Callable, Tuple, Any

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.state import (AppState, AppContext)
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.services.qtasks import TaskScheduler


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
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()
        self.save_as_path = None
        self.previous_file_path = None
        
        # Task state
        self.is_saving = False

    @override
    def execute(self) -> bool:
        """Execute the save project command."""
        try:
            self.logger.info("Executing SaveProjectCommand")
            
            # Prevent concurrent saves
            if self.is_saving:
                self.ui_controller.show_warning_message(
                    "Save Project",
                    "A save operation is already in progress. Please wait for it to complete."
                )
                return False
            
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
            
            # If this is a Save As operation, store the new path
            if not self.save_as_path and save_path != current_path:
                self.save_as_path = save_path

            # Show starting message for operations that prompt for path or are Save As
            if self.save_as_path or not current_path:
                self.ui_controller.show_info_message(
                    "Save Starting", 
                    f"Starting save of project '{project.name}' to:\n{save_path}"
                )

            # Start background save operation
            self.is_saving = True
            
            # Run save in background thread
            self.task_scheduler.run_task(
                task=self._save_project_task,
                task_arguments={},
                on_result=self._on_save_result,
                on_error=self._on_save_error,
                on_finished=self._on_save_finished,
                on_progress=self._on_save_progress
            )
            
            return True  # Command initiated successfully

        except Exception as e:
            error_msg = f"Failed to initiate project save: {e}"
            self.logger.error("SaveProjectCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Save Project Error", error_msg)
            self.is_saving = False  # Reset flag on error
            return False

    def _save_project_task(self, progress_callback: Callable[[float], None], **kwargs) -> dict:
        """
        Save task function to be run in a background thread.
        Returns a dictionary with success status and any error message.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: {'success': bool, 'error': str or None, 'path': str or None, 'project': Project or None}
        """
        self.logger.debug("Starting project save task")
        try:
            if progress_callback:
                progress_callback(0.1)  # Starting save
                
            if not self.app_state.has_project:
                return {'success': False, 'error': "No project is currently loaded to save.", 'path': None, 'project': None}
                
            project = self.app_state.current_project
            if not project:
                return {'success': False, 'error': "No project is currently loaded to save.", 'path': None, 'project': None}
                
            if progress_callback:
                progress_callback(0.2)  # Project validation complete
                
            # Determine the save path
            save_path = None
            if self.save_as_path:
                save_path = self.save_as_path
            elif self.app_state.project_file_path:
                save_path = self.app_state.project_file_path
            else:
                return {'success': False, 'error': "No save path available. This should have been handled in execute().", 'path': None, 'project': None}
                
            if progress_callback:
                progress_callback(0.3)  # Save path determined
                
            # Emit saving event
            self.app_context.event_bus.emit(ProjectEvents.PROJECT_SAVING, {
                'project': project,
                'file_path': save_path
            })
            
            if progress_callback:
                progress_callback(0.4)  # Event emitted
                
            # Update the project file path if needed
            if save_path != project.project_file_path:
                project.project_file_path = save_path
                
            if progress_callback:
                progress_callback(0.5)  # Project path updated
                
            # Perform the actual save operation
            project_data_manager = self.app_context.get_manager(ProjectDataManager)
            project_data_manager.save(project, save_path)
            
            if progress_callback:
                progress_callback(0.9)  # Save operation complete
                
            self.logger.info(f"Successfully saved project '{project.name}' to {save_path}")
            
            if progress_callback:
                progress_callback(1.0)  # Finished
                
            return {'success': True, 'error': None, 'path': save_path, 'project': project}
            
        except Exception as e:
            error_msg = f"Error during project save: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {'success': False, 'error': error_msg, 'path': None, 'project': None}

    def _on_save_result(self, result: dict):
        """Handle successful completion of save task."""
        try:
            self.is_saving = False
            
            if result.get('success', False):
                project = result.get('project')
                save_path = result.get('path')
                
                if project and save_path:
                    # Update app state with new file path (if it changed)
                    if save_path != self.previous_file_path:
                        self.app_state.load_project(project)

                    # Emit save event
                    self.app_state.event_bus.emit(ProjectEvents.PROJECT_SAVED, {
                        'project': project,
                        'file_path': save_path,
                        'previous_path': self.previous_file_path
                    })

                    self.logger.info(
                        "Project '%s' saved successfully to '%s'", project.name, save_path)

                    # Show success message for Save As operations or new projects
                    if self.save_as_path or not self.previous_file_path:
                        self.ui_controller.show_info_message(
                            "Project Saved",
                            f"Project '{project.name}' has been saved to:\n{save_path}"
                        )
                else:
                    self.logger.warning("Save completed but missing project or path information")
            else:
                error_msg = result.get('error', 'Unknown save error')
                self.ui_controller.show_error_message("Save Failed", error_msg)
                self.logger.error(f"Save failed: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Error handling save result: {e}", exc_info=True)
            self.ui_controller.show_error_message("Save Error", f"Error processing save result: {str(e)}")

    def _on_save_error(self, error_info: Tuple[Any, Any, str]):
        """Handle error during save task."""
        try:
            self.is_saving = False
            error_type, error_value, error_traceback = error_info
            error_msg = f"Save failed with {error_type.__name__}: {str(error_value)}"
            
            self.logger.error(f"Save task error: {error_msg}")
            self.logger.error(f"Traceback: {error_traceback}")
            
            self.ui_controller.show_error_message("Save Project Error", error_msg)
            
        except Exception as e:
            self.logger.error(f"Error handling save error: {e}", exc_info=True)

    def _on_save_finished(self):
        """Handle completion of save task (success or failure)."""
        try:
            self.is_saving = False
            self.logger.info("Save task finished")
            
        except Exception as e:
            self.logger.error(f"Error in save finished handler: {e}", exc_info=True)

    def _on_save_progress(self, progress: float):
        """Handle progress updates from save task."""
        try:
            # Log the progress for now - could update a progress bar if UI supports it
            if progress <= 1.0:
                percentage = int(progress * 100)
                self.logger.debug(f"Save progress: {percentage}%")
                
        except Exception as e:
            self.logger.error(f"Error handling save progress: {e}", exc_info=True)

    def undo(self):
        """Undo the save project command by reverting file path changes."""
        try:
            # Only need to undo if the file path changed
            if self.previous_file_path != self.app_state.project_file_path:
                if self.app_state.has_project:
                    project = self.app_state.current_project
                    if project:  # Additional safety check
                        self.app_state.load_project(project)
                        # TODO: this doesn't do anything currently
                        self.logger.info(
                            "Reverted file path to '%s'", self.previous_file_path
                        )

        except Exception as e:
            error_msg = f"Failed to undo save project: {e}"
            self.logger.error("SaveProjectCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the save project command."""
        if not self.is_saving:
            return self.execute()
        else:
            self.logger.warning("Cannot redo save command while save is in progress")
            return False


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
            error_msg = f"Failed to save project as: {e}"
            self.logger.error("SaveProjectAsCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Save Project As Error", error_msg)
            raise
