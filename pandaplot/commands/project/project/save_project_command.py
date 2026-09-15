from typing import Any, Callable, Optional, Tuple, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.qtasks import TaskScheduler
from pandaplot.services.session import SessionPersistenceManager


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
        # AppState.modification_revision as of the moment the background
        # save task was kicked off -- see _on_save_result.
        self._save_started_revision: int = 0
        # The Project (and its resolved save path) captured at dispatch
        # time, in execute() -- passed into _save_project_task via
        # task_arguments rather than having the background thread re-read
        # AppState.current_project itself, and compared by identity in
        # _on_save_result() so a completion is discarded rather than
        # applied to whatever project happens to be current if the active
        # project changed (opened/created/closed) while this save was
        # writing to disk in the background.
        self._dispatch_project: Optional[Project] = None

        # Task state
        self.is_saving = False

    @override
    def marks_project_modified(self) -> bool:
        """A save clears AppState's modified flag (via mark_saved in
        _on_save_result) rather than setting it."""
        return False

    @override
    def occupies_undo_slot(self) -> bool:
        """Saving is a side effect on disk, not an edit to the project's
        content -- it has nothing for undo/redo to revert or reapply, so it
        should never occupy a slot on either stack. See #221."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Execute the save project command."""
        try:
            self.logger.info("Executing SaveProjectCommand")

            # Prevent concurrent saves -- both this specific instance
            # re-executing (self.is_saving) and any other writer of the same
            # project file (another SaveProjectCommand instance, e.g.
            # auto-save, or a caller doing its own synchronous save; see
            # AppState.is_saving) racing this one. ProjectDataManager.save()
            # opens the target file in write mode, so two overlapping
            # writers can corrupt it.
            if self.is_saving or self.app_state.is_saving:
                self.logger.warning("SaveProjectCommand.execute: a save operation is already in progress")
                self.ui_controller.show_warning_message("Save Project", "A save operation is already in progress. Please wait for it to complete.")
                return CommandResult.FAILURE

            # Check if we have a project to save
            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning("SaveProjectCommand.execute: no project is currently loaded to save")
                self.ui_controller.show_warning_message("Save Project", "No project is currently loaded to save.")
                return CommandResult.FAILURE

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
                save_path = self.ui_controller.show_save_project_dialog(default_name=f"{project.name}.pplot")
                if not save_path:
                    return CommandResult.FAILURE  # User cancelled

            # Remember the pre-save path so _on_save_result can tell whether
            # this save changed it (a Save As or a first save of a new
            # project) versus an ordinary same-path save.
            self.previous_file_path = current_path

            # If this is a Save As operation, store the new path
            if not self.save_as_path and save_path != current_path:
                self.save_as_path = save_path

            # Show starting message for operations that prompt for path or are Save As
            if self.save_as_path or not current_path:
                self.ui_controller.show_info_message("Save Starting", f"Starting save of project '{project.name}' to:\n{save_path}")

            # Emit saving event on main thread before starting background task
            self.app_context.event_bus.emit(ProjectEvents.PROJECT_SAVING, {"project": project, "file_path": save_path})

            # Start background save operation. Capture the project and its
            # resolved save path now (main thread) rather than having the
            # background task re-read AppState.current_project/
            # project_file_path itself -- those are mutable on the main
            # thread while this task runs, and _on_save_result compares
            # this same captured project by identity to detect (and
            # discard) a completion for a project that's no longer current.
            self._dispatch_project = project
            self.is_saving = True
            self.app_state.begin_save()
            self._save_started_revision = self.app_state.modification_revision

            # Run save in background thread
            self.task_scheduler.run_task(
                task=self._save_project_task,
                task_arguments={"project": project, "save_path": save_path},
                on_result=self._on_save_result,
                on_error=self._on_save_error,
                on_finished=self._on_save_finished,
                on_progress=self._on_save_progress,
            )

            return CommandResult.SUCCESS  # Command initiated successfully

        except Exception as e:
            error_msg = f"Failed to initiate project save: {e}"
            self.logger.error("SaveProjectCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Save Project Error", error_msg)
            self.is_saving = False  # Reset flag on error
            # Safe even if begin_save() was never reached (a no-op flip):
            # covers the case where run_task() itself raised after
            # begin_save(), which would otherwise leave AppState.is_saving
            # stuck True forever since _on_save_finished would never run.
            self.app_state.end_save()
            return CommandResult.FAILURE

    def _save_project_task(
        self, progress_callback: Callable[[float], None], project: Project, save_path: str, **kwargs
    ) -> dict:
        """
        Save task function to be run in a background thread.
        Returns a dictionary with success status and any error message.

        Args:
            progress_callback: Optional callback for progress updates
            project: The Project to save, captured on the main thread by
                execute() -- never re-read from AppState here, since
                AppState.current_project is mutable on the main thread
                while this runs on a background one.
            save_path: The resolved path to save to, likewise captured by
                execute().

        Returns:
            dict: {'success': bool, 'error': str or None, 'path': str or None, 'project': Project or None}
        """
        self.logger.debug("Starting project save task")
        try:
            if progress_callback:
                progress_callback(0.1)  # Starting save

            if progress_callback:
                progress_callback(0.3)  # Save path determined

            # Update the project file path if needed
            if save_path != project.project_file_path:
                project.project_file_path = save_path

            if progress_callback:
                progress_callback(0.4)  # Project path updated

            # Perform the actual save operation
            project_manager = self.app_context.get_manager(ProjectManager)
            project_manager.save_project(project, save_path)

            if progress_callback:
                progress_callback(0.9)  # Save operation complete

            self.logger.info(f"Successfully saved project '{project.name}' to {save_path}")

            if progress_callback:
                progress_callback(1.0)  # Finished

            return {"success": True, "error": None, "path": save_path, "project": project}

        except Exception as e:
            error_msg = f"Error during project save: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg, "path": None, "project": None}

    def _on_save_result(self, result: dict):
        """Handle successful completion of save task."""
        try:
            self.is_saving = False

            if self.app_state.current_project is not self._dispatch_project:
                # The active project changed (opened/created/closed) while
                # this save was writing self._dispatch_project to disk in
                # the background -- applying this result now (Save-As
                # path-tracking, mark_saved()) would act on whatever
                # project happens to be current, not the one that was
                # actually saved. That write to disk already happened (or
                # failed) for the old project regardless; just don't act on
                # it here.
                self.logger.warning(
                    "Discarding save result for '%s': the active project changed while saving",
                    self._dispatch_project.name if self._dispatch_project else "<unknown>",
                )
                return

            if result.get("success", False):
                project = result.get("project")
                save_path = result.get("path")

                if project and save_path:
                    # Update app state with new file path (if it changed)
                    if save_path != self.previous_file_path:
                        self.app_state.load_project(project)
                        # load_project unconditionally clears is_modified (a
                        # freshly (re)loaded project has nothing unsaved
                        # yet) -- but if a command modified the project in
                        # the gap between the background save finishing and
                        # this callback running, that edit wasn't part of
                        # the file just written, so restore the dirty flag
                        # rather than letting load_project's reset silently
                        # swallow it.
                        if self.app_state.modification_revision != self._save_started_revision:
                            self.app_state.mark_modified()
                    else:
                        # A successful save has nothing left unsaved -- but
                        # only if nothing modified the project since this
                        # save started (see mark_saved's at_revision).
                        self.app_state.mark_saved(at_revision=self._save_started_revision)

                    # Emit save event
                    self.app_state.event_bus.emit(
                        ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": save_path, "previous_path": self.previous_file_path}
                    )

                    # Remember this project so it can be restored on next launch
                    try:
                        session_manager = self.app_context.get_manager(SessionPersistenceManager)
                        session_manager.update_project(save_path)
                    except Exception as e:  # noqa: BLE001
                        self.logger.warning("Failed to persist last_project_path: %s", e)

                    self.logger.info("Project '%s' saved successfully to '%s'", project.name, save_path)

                    # Show success message for Save As operations or new projects
                    if self.save_as_path or not self.previous_file_path:
                        self.ui_controller.show_info_message("Project Saved", f"Project '{project.name}' has been saved to:\n{save_path}")
                else:
                    self.logger.warning("Save completed but missing project or path information")
            else:
                error_msg = result.get("error", "Unknown save error")
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
        """Handle completion of save task (success or failure). Always
        called, regardless of whether _on_save_result discarded a stale
        result -- see begin_save()/end_save()."""
        try:
            self.is_saving = False
            self.app_state.end_save()
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

    @override
    def undo(self) -> CommandResult:
        """Saving has nothing to undo -- see occupies_undo_slot(). Never
        called through the normal undo flow since this command never sits
        on the undo stack; a no-op if called directly."""
        self.logger.debug("SaveProjectCommand.undo: no-op, saving is not undoable")
        return CommandResult.NOOP

    @override
    def redo(self) -> CommandResult:
        """Saving has nothing to redo -- see occupies_undo_slot(). Never
        called through the normal redo flow since this command never sits
        on the redo stack; a no-op if called directly."""
        self.logger.debug("SaveProjectCommand.redo: no-op, saving is not undoable")
        return CommandResult.NOOP

    @override
    def cleanup(self) -> None:
        """No undo state to release -- this command does not support
        undo/redo."""
        return


class SaveProjectAsCommand(SaveProjectCommand):
    """
    Command to save the current project with a new file path (Save As).
    This always prompts for a new file location.
    """

    def __init__(self, app_context: AppContext):
        super().__init__(app_context)

    @override
    def execute(self) -> CommandResult:
        """Execute the save as command."""
        try:
            # Check if we have a project to save
            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning("SaveProjectAsCommand.execute: no project is currently loaded to save")
                self.ui_controller.show_warning_message("Save Project As", "No project is currently loaded to save.")
                return CommandResult.FAILURE

            # Always prompt for new save location
            save_path = self.ui_controller.show_save_project_dialog(default_name=f"{project.name}.pplot")
            if not save_path:
                return CommandResult.FAILURE  # User cancelled

            # Set the save path and delegate to parent
            self.save_as_path = save_path
            return super().execute()

        except Exception as e:
            error_msg = f"Failed to save project as: {e}"
            self.logger.error("SaveProjectAsCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Save Project As Error", error_msg)
            raise
