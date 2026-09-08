from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.project.unsaved_changes import flush_pending_edits
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.session import SessionPersistenceManager


class NewProjectCommand(Command):
    """
    Command to create a new project.
    This will clear the current project (with user confirmation if needed) and create a fresh project.
    """

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        # Store previous state for undo
        self.previous_project = None
        self.previous_file_path = None
        # Whether the previous project had unsaved changes, so undo() can
        # restore that dirty state rather than letting load_project() reset
        # it to "no changes" -- see undo().
        self.previous_was_modified = False
        # The Project created by execute()'s first run, cached so redo() can
        # restore that exact object instead of calling execute() again --
        # see redo().
        self.created_project: Optional[Project] = None
        # Whether created_project had unsaved changes when undo() last swapped
        # away from it (e.g. a note edit flushed during that same undo()),
        # so redo() can restore that dirty state rather than letting
        # load_project() reset it to "no changes" -- see undo()/redo().
        self.created_project_was_modified = False

    @override
    def marks_project_modified(self) -> bool:
        """Creates a fresh project via load_project, which resets AppState's
        modified flag itself -- not a project edit."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Execute the new project command."""
        try:
            if not flush_pending_edits(self.app_context):
                self.ui_controller.show_error_message(
                    "Create New Project",
                    "One or more open notes could not be saved. Save them manually before continuing.",
                )
                return CommandResult.FAILURE

            # Only prompt if closing the current project would actually
            # discard something -- an unmodified project has nothing to lose.
            if self.app_state.has_project and self.app_state.is_modified:
                response = self.ui_controller.show_question(
                    "Create New Project",
                    "The current project has unsaved changes.\n"
                    "Creating a new project will discard them.\n\nDo you want to continue?"
                )
                if not response:
                    return CommandResult.FAILURE  # User cancelled

            # Store current state for undo
            if self.app_state.has_project:
                self.previous_project = self.app_state.current_project
                self.previous_file_path = self.app_state.project_file_path
                self.previous_was_modified = self.app_state.is_modified

            name = self.ui_controller.show_new_project_dialog()
            if not name:
                return CommandResult.NOOP  # User cancelled the naming dialog

            # Create new project
            new_project = Project(
                name=name, description="A new project created with PandaPlot")
            self.created_project = new_project

            # Update app state - use load_project method
            self.app_state.load_project(new_project)

            # A brand new project has no file yet; don't restore the previous
            # project's path next launch until this one is saved.
            try:
                session_manager = self.app_context.get_manager(SessionPersistenceManager)
                session_manager.update_project(None)
            except Exception as e:  # noqa: BLE001
                self.logger.warning("Failed to clear last_project_path: %s", e)

            self.logger.info(
                "Created new project '%s'", new_project.name
            )
            return CommandResult.SUCCESS
        except Exception as e:
            error_msg = f"Failed to create new project: {e}"
            self.logger.error("NewProjectCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "New Project Error", error_msg)
            raise

    def undo(self) -> CommandResult:
        """Undo the new project command by restoring the previous project."""
        # A note edited in the newly-created project, right before this
        # undo, can still be mid-debounce -- no EditNoteCommand has run yet
        # to invalidate anything, so nothing else protects this swap (see
        # PR #352 review).
        if not flush_pending_edits(self.app_context):
            self.ui_controller.show_error_message(
                "Create New Project",
                "One or more open notes could not be saved. Save them manually before undoing.",
            )
            # ABORTED, not FAILURE: CommandExecutor.undo() moves the command
            # to the redo stack regardless of result, so FAILURE would
            # record this creation as undone (and installable via a later
            # Redo) even though nothing actually changed (see PR #352 review).
            return CommandResult.ABORTED

        try:
            # Capture created_project's dirty state (the flush above may
            # have just set it) before swapping away from it -- otherwise a
            # later redo() would reinstall this exact project via
            # load_project(), which unconditionally reports it as clean,
            # silently discarding that it actually has unsaved content.
            self.created_project_was_modified = self.app_state.is_modified

            if self.previous_project:
                # Restore previous project. load_project() unconditionally
                # resets is_modified to False (correct for a fresh disk
                # load), so restore the dirty state it actually had before
                # this command replaced it.
                self.app_state.load_project(self.previous_project)
                if self.previous_was_modified:
                    self.app_state.mark_modified()
                self.logger.info(
                    "Restored previous project '%s'", self.previous_project.name
                )
            else:
                # No previous project, close current project
                self.app_state.close_project()
                self.logger.info(
                    "Closed project (no previous project to restore)"
                )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to undo new project: {e}"
            self.logger.error("NewProjectCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the new project command.

        Restores the exact `Project` object execute() created the first
        time, rather than calling execute() again -- which would re-prompt
        for unsaved-changes confirmation and re-open the naming dialog,
        building a *different* Project if the user typed a different name
        (or making redo fail outright if they cancelled). Mirrors
        CreateNoteCommand/CreateChartCommand's redo(), which re-add their
        cached created object instead of re-running execute()."""
        if self.created_project is None:
            self.logger.warning(
                "NewProjectCommand.redo: no cached project to restore (execute() "
                "never completed successfully)"
            )
            return CommandResult.FAILURE

        # Same race as undo() -- a note edited in the project that's about
        # to be replaced (by redoing the creation) must be flushed first
        # (see PR #352 review).
        if not flush_pending_edits(self.app_context):
            self.ui_controller.show_error_message(
                "Create New Project",
                "One or more open notes could not be saved. Save them manually before redoing.",
            )
            # ABORTED, not FAILURE -- see the matching undo() comment above.
            return CommandResult.ABORTED

        try:
            # Refresh previous_was_modified in case this flush just dirtied
            # whatever project is currently active -- otherwise a later
            # undo() of this redo would restore a stale (pre-flush) dirty
            # flag instead of the current one.
            self.previous_was_modified = self.app_state.is_modified

            self.app_state.load_project(self.created_project)
            if self.created_project_was_modified:
                self.app_state.mark_modified()

            # A brand new project has no file yet; don't restore the previous
            # project's path next launch until this one is saved (mirrors
            # execute()).
            try:
                session_manager = self.app_context.get_manager(SessionPersistenceManager)
                session_manager.update_project(None)
            except Exception as e:  # noqa: BLE001
                self.logger.warning("Failed to clear last_project_path: %s", e)

            self.logger.info(
                "Redid new project '%s'", self.created_project.name
            )
            return CommandResult.SUCCESS
        except Exception as e:
            error_msg = f"Failed to redo new project: {e}"
            self.logger.error("NewProjectCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the previous/created-Project references held for
        undo/redo once this command is dropped from the stacks for good
        (see Command.cleanup)."""
        self.previous_project = None
        self.created_project = None
