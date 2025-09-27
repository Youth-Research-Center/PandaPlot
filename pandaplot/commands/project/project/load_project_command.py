from typing import Any, Callable, Optional, Tuple, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.services.qtasks import TaskScheduler
from pandaplot.storage.project_data_manager import ProjectDataManager


class LoadProjectCommand(Command):
    """
    Command to load a project into the application state.
    This command follows the MVC pattern by:
    - Being triggered by UI components
    - Using services (ProjectManager) to load data
    - Updating app state which emits events to update UI
    """

    def __init__(self, app_context: AppContext, file_path: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()
        self.project_data_manager = app_context.get_manager(ProjectDataManager)
        self.file_path = file_path
        self.previous_project: Optional[Project] = None
        self.previous_file_path: Optional[str] = None
        self.loaded_project: Optional[Project] = None

        # Task state
        self.is_loading = False

    @override
    def execute(self) -> bool:
        """Execute the load project command."""
        try:
            self.logger.info("Executing LoadProjectCommand")

            # Prevent concurrent loads
            if self.is_loading:
                self.logger.warning("Load operation already in progress")
                self.ui_controller.show_info_message("Load In Progress", "A project load is already in progress.")
                return False

            # Store current state for undo
            self.previous_project = self.app_state.current_project
            self.previous_file_path = self.app_state.project_file_path

            # Show starting message
            self.ui_controller.show_info_message("Load Starting", f"Starting to load project from:\n{self.file_path}")

            # Start background load operation
            self.is_loading = True

            # Run load in background thread
            self.task_scheduler.run_task(
                task=self._load_project_task,
                task_arguments={},
                on_result=self._on_load_result,
                on_error=self._on_load_error,
                on_finished=self._on_load_finished,
                on_progress=self._on_load_progress,
            )

            return True  # Command initiated successfully

        except Exception as e:
            error_msg = f"Failed to initiate project load: {e}"
            self.logger.error("LoadProjectCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Load Project Error", error_msg)
            self.is_loading = False  # Reset flag on error
            return False

    def _load_project_task(self, progress_callback: Callable[[float], None], **kwargs) -> dict:
        """
        Load task function to be run in a background thread.
        Returns a dictionary with success status and any error message.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            dict: {'success': bool, 'error': str or None, 'project': Project or None, 'file_path': str or None}
        """
        self.logger.debug("Starting project load task")
        try:
            if progress_callback:
                progress_callback(0.1)  # Starting load

            if not self.file_path:
                return {"success": False, "error": "No file path provided for loading.", "project": None, "file_path": None}

            if progress_callback:
                progress_callback(0.2)  # File path validated

            # Note: No PROJECT_LOADING event exists yet, but could be added to ProjectEvents if needed
            # For now, we'll skip the loading event and just load the project

            if progress_callback:
                progress_callback(0.3)  # Event emitted

            # Load the project using the data manager
            loaded_project = self.project_data_manager.load(self.file_path)

            if progress_callback:
                progress_callback(0.7)  # Project loaded from file

            if not loaded_project:
                return {"success": False, "error": f"Failed to load project from {self.file_path}", "project": None, "file_path": self.file_path}

            if progress_callback:
                progress_callback(0.9)  # Load validation complete

            self.logger.info(f"Successfully loaded project '{loaded_project.name}' from {self.file_path}")

            if progress_callback:
                progress_callback(1.0)  # Finished

            return {"success": True, "error": None, "project": loaded_project, "file_path": self.file_path}

        except Exception as e:
            error_msg = f"Error during project load: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg, "project": None, "file_path": self.file_path}

    def _on_load_result(self, result: dict):
        """Handle successful completion of load task."""
        try:
            self.is_loading = False

            if result.get("success", False):
                project = result.get("project")
                file_path = result.get("file_path")

                if project and file_path:
                    # Store the loaded project for undo/redo
                    self.loaded_project = project

                    # Update app state with the loaded project
                    self.app_state.load_project(project)

                    self.logger.info(f"Project '{project.name}' loaded successfully from '{file_path}'")

                    # Show success message
                    self.ui_controller.show_info_message("Project Loaded", f"Project '{project.name}' loaded successfully from:\n{file_path}")
                else:
                    error_msg = "Missing project or file path in load result"
                    self.ui_controller.show_error_message("Load Failed", error_msg)
                    self.logger.error(error_msg)
            else:
                error_msg = result.get("error", "Unknown load error")
                self.ui_controller.show_error_message("Load Failed", error_msg)
                self.logger.error(f"Load failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"Error handling load result: {e}", exc_info=True)
            self.ui_controller.show_error_message("Load Error", f"Error processing load result: {str(e)}")

    def _on_load_error(self, error_info: Tuple[Any, Any, str]):
        """Handle error during load task."""
        try:
            self.is_loading = False
            error_type, error_value, error_traceback = error_info
            error_msg = f"Load failed with {error_type.__name__}: {str(error_value)}"

            self.logger.error(f"Load task error: {error_msg}")
            self.logger.error(f"Traceback: {error_traceback}")

            self.ui_controller.show_error_message("Load Project Error", error_msg)

        except Exception as e:
            self.logger.error(f"Error handling load error: {e}", exc_info=True)

    def _on_load_finished(self):
        """Handle completion of load task (success or failure)."""
        try:
            self.is_loading = False
            self.logger.info("Load task finished")

        except Exception as e:
            self.logger.error(f"Error in load finished handler: {e}", exc_info=True)

    def _on_load_progress(self, progress: float):
        """Handle progress updates from load task."""
        try:
            # Log the progress for now - could update a progress bar if UI supports it
            if progress <= 1.0:
                percentage = int(progress * 100)
                self.logger.debug(f"Load progress: {percentage}%")

        except Exception as e:
            self.logger.error(f"Error handling load progress: {e}", exc_info=True)

    def undo(self):
        """Undo the load project command."""
        if self.previous_project is not None:
            self.app_state.load_project(self.previous_project)
        else:
            self.app_state.close_project()

    def redo(self):
        """Redo the load project command."""
        if not self.is_loading:
            if self.loaded_project is not None:
                # We have a cached project, load it directly without file I/O
                self.app_state.load_project(self.loaded_project)
                return True
            else:
                # Re-execute if we don't have the loaded project cached
                return self.execute()
        else:
            self.logger.warning("Cannot redo load command while load is in progress")
            return False
