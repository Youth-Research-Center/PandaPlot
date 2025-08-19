from typing import override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class RenameItemCommand(Command):
    """
    Command to rename a note in the project.
    """

    def __init__(self, app_context: AppContext, note_id: str, new_name: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.note_id = note_id
        self.new_name = new_name

        # Store state for undo
        self.old_name = None

    @override
    def execute(self) -> bool:
        """Execute the rename item command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Rename Item",
                    "No project is currently loaded."
                )
                return False

            project = self.app_state.current_project
            if not project:
                return False

            # Check in metadata notes
            note = project.find_item(self.note_id)

            if note is None:
                self.ui_controller.show_warning_message(
                    "Rename Item",
                    f"Item with ID '{self.note_id}' not found."
                )
                return False

            self.old_name = note.name
            note.update_name(self.new_name)

            # Emit dotted event only
            self.app_state.event_bus.emit('note.renamed', {
                'project': project,
                'note_id': self.note_id,
                'old_name': self.old_name,
                'new_name': self.new_name
            })

            self.logger.info(
                "Renamed note '%s' -> '%s' (id=%s)", self.old_name, self.new_name, self.note_id
            )
            return True
        except Exception as e:
            error_msg = f"Failed to rename note: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Rename Note Error", error_msg)
            raise

    def undo(self):
        """Undo the rename note command."""
        try:
            if self.old_name and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return

                note = project.find_item(self.note_id)
                if note is None:
                    self.ui_controller.show_warning_message(
                        "Undo Rename Note",
                        f"Note with ID '{self.note_id}' not found."
                    )
                    return

                # Perform restore
                note.update_name(self.old_name)

                # Emit event for UI update
                self.app_state.event_bus.emit('note.renamed', {
                    'project': project,
                    'note_id': self.note_id,
                    'old_name': self.new_name,
                    'new_name': self.old_name
                })

                self.logger.info(
                    "Restored note name to '%s' (id=%s)", self.old_name, self.note_id
                )

        except Exception as e:
            error_msg = f"Failed to undo rename note: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the rename note command."""
        self.execute()
