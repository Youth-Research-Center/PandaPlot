from typing import override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import NoteContentChangedData
from pandaplot.models.events.event_types import NoteEvents
from pandaplot.models.project.items import Note
from pandaplot.models.state import (AppState, AppContext)


class EditNoteCommand(Command):
    """
    Command to edit the content of a note.
    """

    def __init__(self, app_context: AppContext, note_id: str, new_content: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.note_id = note_id
        self.new_content = new_content

        # Store state for undo
        self.old_content = None

    @override
    def execute(self) -> bool:
        """Execute the edit note command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Edit Note",
                    "No project is currently loaded."
                )
                return False

            project = self.app_state.current_project
            if not project:
                return False

            item = project.find_item(self.note_id)
            if item is None or not isinstance(item, Note):
                self.ui_controller.show_warning_message(
                    "Edit Note",
                    f"Note '{self.note_id}' not found in the project."
                )
                return False

            note: Note = item
            # Store old content for undo
            self.old_content = note.content
            note.update_content(self.new_content)

            # Emit dotted content changed event only
            self.app_state.event_bus.emit(
                    NoteEvents.NOTE_CONTENT_CHANGED,
                    NoteContentChangedData(
                        note_id=self.note_id,
                        old_content=self.old_content,
                        new_content=self.new_content
                    ).to_dict()
            )

            self.logger.info(
                "Edited content of note '%s'", self.note_id
            )
            return True

        except Exception as e:
            error_msg = f"Failed to edit note: {e}"
            self.logger.error("EditNoteCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Edit Note Error", error_msg)
            return False

    def undo(self):
        """Undo the edit note command."""
        try:
            if self.old_content is not None and self.app_state.has_project:
                project = self.app_state.current_project

                if not project:
                    self.ui_controller.show_warning_message(
                        "Undo Edit Note",
                        "No project is currently loaded."
                    )
                    return False

                item = project.find_item(self.note_id)
                if item is None or not isinstance(item, Note):
                    self.ui_controller.show_warning_message(
                        "Undo Edit Note",
                        f"Note with ID '{self.note_id}' not found in the project."
                    )
                    return False

                note: Note = item
                note.update_content(self.old_content)

                # Emit dotted content changed event only (reversal)
                self.app_state.event_bus.emit(
                    NoteEvents.NOTE_CONTENT_CHANGED,
                    NoteContentChangedData(
                        note_id=self.note_id,
                        old_content=self.new_content,
                        new_content=self.old_content
                    ).to_dict()
                )

                self.logger.info(
                    "Restored note content for '%s'", self.note_id
                )
                return True

        except Exception as e:
            error_msg = f"Failed to undo edit note: {e}"
            self.logger.error("EditNoteCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return False

    def redo(self):
        """Redo the edit note command."""
        try:
            if self.old_content is not None and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return False

                item = project.find_item(self.note_id)
                if item is None or not isinstance(item, Note):
                    return False

                note: Note = item
                note.update_content(self.new_content)

                # Emit dotted content changed event only (redo)
                self.app_state.event_bus.emit(
                    NoteEvents.NOTE_CONTENT_CHANGED,
                    NoteContentChangedData(
                        note_id=self.note_id,
                        old_content=self.old_content,
                        new_content=self.new_content
                    ).to_dict()
                )

                self.logger.info(
                    "Redone edit of note '%s'", self.note_id
                )
                return True
            else:
                return False

        except Exception as e:
            error_msg = f"Failed to redo edit note: {e}"
            self.logger.error("EditNoteCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
