import os
from typing import Any, Callable, Optional, Tuple, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.project.unsaved_changes import flush_pending_edits
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.qtasks import TaskScheduler
from pandaplot.services.session import SessionPersistenceManager


def _same_path(a: Optional[str], b: Optional[str]) -> bool:
    """Compare two project file paths for "is this the same file", tolerant
    of relative-vs-absolute and symlink differences."""
    if not a or not b:
        return False
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class LoadProjectCommand(Command):
    """
    Command to load a project into the application state.
    This command follows the MVC pattern by:
    - Being triggered by UI components
    - Using services (ProjectManager) to load data
    - Updating app state which emits events to update UI
    """

    def __init__(self, app_context: AppContext, file_path: str,
                 on_loaded: Optional[Callable[[Project], None]] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()
        self.project_manager = app_context.get_manager(ProjectManager)
        self.file_path = file_path
        # Called after the project has been loaded into app state (e.g. so the
        # caller can restore session tabs once the project is actually ready).
        self.on_loaded = on_loaded
        self.previous_project: Optional[Project] = None
        self.previous_file_path: Optional[str] = None
        # Whether the previous project had unsaved changes, so undo() can
        # restore that dirty state rather than letting load_project() reset
        # it to "no changes" -- see undo().
        self.previous_was_modified = False
        self.loaded_project: Optional[Project] = None
        # Whether loaded_project had unsaved changes when undo() last swapped
        # away from it (e.g. a note edit flushed during that same undo()),
        # so redo()'s cached fast path can restore that dirty state rather
        # than letting load_project() reset it to "no changes".
        self.loaded_project_was_modified = False
        # AppState.modification_revision as of the moment the background
        # load task was kicked off -- see _on_load_result.
        self._dispatch_revision: int = 0

        # Task state
        self.is_loading = False

    @override
    def marks_project_modified(self) -> bool:
        """Loading a project sets AppState's modified flag explicitly (via
        load_project, called from _on_load_result) -- not a project edit
        itself."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Execute the load project command."""
        try:
            self.logger.info("Executing LoadProjectCommand")

            # Prevent concurrent loads
            if self.is_loading:
                self.logger.warning("Load operation already in progress")
                self.ui_controller.show_info_message("Load In Progress", "A project load is already in progress.")
                return CommandResult.FAILURE

            # Centralized guards for every load path (the file-dialog flow
            # via OpenProjectCommand, recent/example projects from the
            # welcome tab, and the Examples dialog) -- previously only
            # OpenProjectCommand checked these, so the other entry points
            # could silently replace a modified project or reload the
            # current file from disk, discarding undo history. Living here
            # means every caller gets the same protection with nothing
            # extra to remember at the call site.
            if self.app_state.has_project and _same_path(self.app_state.project_file_path, self.file_path):
                self.logger.info("'%s' is already open; skipping reload", self.file_path)
                return CommandResult.NOOP

            if not flush_pending_edits(self.app_context):
                self.ui_controller.show_error_message(
                    "Open Project",
                    "One or more open notes could not be saved. Save them manually before continuing.",
                )
                return CommandResult.FAILURE

            if self.app_state.has_project and self.app_state.is_modified:
                should_continue = self.ui_controller.show_question(
                    "Open Project",
                    "Opening a new project will close the current project.\nAny unsaved changes will be lost.\n\nDo you want to continue?",
                )
                if not should_continue:
                    self.logger.info("Load project cancelled by user (unsaved changes)")
                    return CommandResult.NOOP

            # Store current state for undo
            self.previous_project = self.app_state.current_project
            self.previous_file_path = self.app_state.project_file_path
            self.previous_was_modified = self.app_state.is_modified

            # Show starting message
            self.ui_controller.show_info_message("Load Starting", f"Starting to load project from:\n{self.file_path}")

            # Start background load operation. The old project stays active
            # and editable while this runs -- capture its modification
            # revision now so _on_load_result can tell whether a *new* edit
            # landed during the load (one the confirmation above never
            # covered) and needs its own confirmation before being discarded.
            self._dispatch_revision = self.app_state.modification_revision
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

            return CommandResult.SUCCESS  # Command initiated successfully

        except Exception as e:
            error_msg = f"Failed to initiate project load: {e}"
            self.logger.error("LoadProjectCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Load Project Error", error_msg)
            self.is_loading = False  # Reset flag on error
            return CommandResult.FAILURE

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
            loaded_project = self.project_manager.load_project(self.file_path)

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
                    # A note left mid-debounce when this callback fires would
                    # otherwise read as an unchanged modification_revision
                    # below, the same race execute()'s own pre-dispatch check
                    # needed flushing for (see flush_pending_edits). A
                    # flush failure here means that edit is still stuck
                    # unsaved -- must not install the loaded project over it.
                    if not flush_pending_edits(self.app_context):
                        self.ui_controller.show_error_message(
                            "Open Project",
                            "One or more open notes could not be saved. "
                            "Save them manually before opening a different project.",
                        )
                        self.logger.warning(
                            "Discarding loaded project '%s': a pending note edit could "
                            "not be flushed during the load",
                            project.name,
                        )
                        return

                    # A command executed against the still-active old project
                    # while this load ran in the background bumps
                    # modification_revision -- an edit the confirmation
                    # shown before dispatch (if any) never covered. Installing
                    # the loaded project now would silently discard it, so
                    # re-confirm before doing that instead of assuming the
                    # original answer still applies.
                    if (
                        self.app_state.has_project
                        and self.app_state.modification_revision != self._dispatch_revision
                        and not self.ui_controller.show_question(
                            "Open Project",
                            "The current project changed while the new one was loading.\n"
                            "Loading it now will discard those additional changes.\n\n"
                            "Do you want to continue?",
                        )
                    ):
                        self.logger.info(
                            "Discarding loaded project '%s': the current project changed "
                            "during the load and the user declined to discard it",
                            project.name,
                        )
                        return

                    # Project.from_dict deserializes project_file_path from
                    # project.json's own record of where IT was saved from.
                    # If the .pplot file was since moved or copied, that
                    # stored path no longer matches where it was just
                    # opened from -- stamp it with the path this command
                    # actually loaded from so later "already open"
                    # comparisons and Save target the right file.
                    project.project_file_path = file_path

                    # Store the loaded project for undo/redo
                    self.loaded_project = project

                    # Update app state with the loaded project
                    self.app_state.load_project(project)

                    # Remember this project so it can be restored on next launch
                    try:
                        session_manager = self.app_context.get_manager(SessionPersistenceManager)
                        session_manager.update_project(file_path)
                    except Exception as e:  # noqa: BLE001
                        self.logger.warning("Failed to persist last_project_path: %s", e)

                    self.logger.info(f"Project '{project.name}' loaded successfully from '{file_path}'")

                    # Items that failed to deserialize are silently dropped from the
                    # hierarchy by ProjectDataManager.load() -- warn instead of letting
                    # the project just open with fewer items than its manifest lists.
                    failed_item_ids = getattr(project, "failed_item_ids", [])
                    if failed_item_ids:
                        self.logger.warning(
                            "Project '%s' loaded with %d item(s) missing: %s",
                            project.name, len(failed_item_ids), failed_item_ids,
                        )
                        self.ui_controller.show_warning_message(
                            "Some Items Failed to Load",
                            f"Project '{project.name}' loaded, but {len(failed_item_ids)} "
                            "item(s) could not be read and are missing from the project:\n\n"
                            + "\n".join(failed_item_ids)
                            + "\n\nSee the log for details. Saving the project now will "
                            "remove these items permanently.",
                        )

                    if self.on_loaded:
                        try:
                            self.on_loaded(project)
                        except Exception as e:  # noqa: BLE001
                            self.logger.error("on_loaded callback failed: %s", e, exc_info=True)
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

    def undo(self) -> CommandResult:
        """Undo the load project command."""
        # A note edited in the currently-installed project, right before
        # this undo, can still be mid-debounce -- no EditNoteCommand has run
        # yet to invalidate anything, so nothing else protects this swap
        # (see PR #352 review).
        if not flush_pending_edits(self.app_context):
            self.ui_controller.show_error_message(
                "Open Project",
                "One or more open notes could not be saved. Save them manually before undoing.",
            )
            # ABORTED, not FAILURE: CommandExecutor.undo() moves the command
            # to the redo stack regardless of result, so FAILURE would
            # record this load as undone (and installable via a later Redo)
            # even though nothing actually changed (see PR #352 review).
            return CommandResult.ABORTED

        # Capture loaded_project's dirty state (the flush above may have
        # just set it) before swapping away from it -- otherwise a later
        # redo() would reinstall this exact project via load_project(),
        # which unconditionally reports it as clean, silently discarding
        # that it actually has unsaved content.
        self.loaded_project_was_modified = self.app_state.is_modified

        if self.previous_project is not None:
            # load_project() unconditionally resets is_modified to False
            # (correct for a fresh disk load), so restore the dirty state
            # the previous project actually had before this command
            # replaced it.
            self.app_state.load_project(self.previous_project)
            if self.previous_was_modified:
                self.app_state.mark_modified()
        else:
            self.app_state.close_project()
        return CommandResult.SUCCESS

    def redo(self) -> CommandResult:
        """Redo the load project command."""
        if self.is_loading:
            self.logger.warning("Cannot redo load command while load is in progress")
            return CommandResult.FAILURE

        # Same race as undo(), on the cached-loaded_project fast path below
        # -- a note edited in the project that's about to be replaced must
        # be flushed first (see PR #352 review).
        if not flush_pending_edits(self.app_context):
            self.ui_controller.show_error_message(
                "Open Project",
                "One or more open notes could not be saved. Save them manually before redoing.",
            )
            # ABORTED, not FAILURE -- see the matching undo() comment above.
            return CommandResult.ABORTED

        # Refresh previous_was_modified in case this flush just dirtied
        # whatever project is currently active -- otherwise a later undo()
        # of this redo would restore a stale (pre-flush) dirty flag instead
        # of the current one.
        self.previous_was_modified = self.app_state.is_modified

        if self.loaded_project is not None:
            # We have a cached project, load it directly without file I/O
            self.app_state.load_project(self.loaded_project)
            if self.loaded_project_was_modified:
                self.app_state.mark_modified()
            return CommandResult.SUCCESS
        else:
            # Re-execute if we don't have the loaded project cached
            return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the whole-Project references held for undo/redo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.previous_project = None
        self.loaded_project = None
