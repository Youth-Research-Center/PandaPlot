"""Command to close the current project."""
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.project.unsaved_changes import confirm_discard_unsaved_changes
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.session import SessionPersistenceManager


class CloseProjectCommand(Command):
    """Command to close the currently loaded project."""

    def __init__(self, app_context: AppContext):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()

    @override
    def marks_project_modified(self) -> bool:
        """Closing sets AppState's modified flag explicitly (close_project
        always resets it) -- not a project edit itself."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Close the current project if one is loaded."""
        try:
            app_state = self.app_context.get_app_state()

            if not app_state.has_project:
                self.logger.info("No project is currently loaded")
                return CommandResult.SUCCESS

            project_name = app_state.current_project.name if app_state.current_project else "Unknown"

            # Give the user a chance to save/cancel if there are unsaved
            # changes -- previously this closed silently and discarded them.
            if not confirm_discard_unsaved_changes(self.app_context):
                self.logger.info("Close project cancelled by user (unsaved changes)")
                return CommandResult.NOOP

            self.logger.info(f"Closing project: {project_name}")

            # Close the project - this will emit PROJECT_CLOSED event
            app_state.close_project()

            # Explicit close means don't reopen this project/its tabs next launch
            try:
                session_manager = self.app_context.get_manager(SessionPersistenceManager)
                session_manager.reset()
            except Exception as e:  # noqa: BLE001
                self.logger.warning("Failed to clear session state: %s", e)

            self.logger.info("Project closed successfully")
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error(f"Failed to close project: {e}")
            self.ui_controller.show_error_message("Close Project Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        """Undo is not supported for project closing."""
        self.logger.warning("Cannot undo project close operation")
        return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        """Redo is not supported for project closing."""
        self.logger.warning("Cannot redo project close operation")
        return CommandResult.FAILURE

    @override
    def occupies_undo_slot(self) -> bool:
        """undo()/redo() are both documented no-ops (closing a project isn't
        undoable/redoable), so this command should never occupy an undo
        slot or clear redo history when executed."""
        return False

    @override
    def cleanup(self) -> None:
        """No undo state to release -- this command does not support
        undo/redo."""
        return