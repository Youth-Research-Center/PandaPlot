from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.note.note_finder import NoteFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import NoteContentChangedData
from pandaplot.models.events.event_types import NoteEvents
from pandaplot.models.state import AppContext, AppState


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
    def execute(self) -> CommandResult:
        """Execute the edit note command."""
        try:
            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning(
                    "EditNoteCommand.execute: cannot edit note '%s', no project is loaded",
                    self.note_id,
                )
                self.ui_controller.show_warning_message(
                    "Edit Note",
                    "No project is currently loaded."
                )
                return CommandResult.FAILURE

            note = NoteFinder.find(project, self.note_id)
            if note is None:
                self.logger.warning(
                    "EditNoteCommand.execute: note '%s' not found", self.note_id,
                )
                self.ui_controller.show_warning_message(
                    "Edit Note",
                    f"Note '{self.note_id}' not found in the project."
                )
                return CommandResult.FAILURE
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
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to edit note: {e}"
            self.logger.error("EditNoteCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Edit Note Error", error_msg)
            return CommandResult.FAILURE

    def undo(self) -> CommandResult:
        """Undo the edit note command."""
        try:
            if self.old_content is None:
                self.logger.warning(
                    "EditNoteCommand.undo: cannot undo for note '%s', no prior content recorded",
                    self.note_id,
                )
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning(
                    "EditNoteCommand.undo: cannot undo note '%s', no project is loaded",
                    self.note_id,
                )
                self.ui_controller.show_warning_message(
                    "Undo Edit Note",
                    "No project is currently loaded."
                )
                return CommandResult.FAILURE

            note = NoteFinder.find(project, self.note_id)
            if note is None:
                self.logger.warning(
                    "EditNoteCommand.undo: note '%s' not found", self.note_id,
                )
                self.ui_controller.show_warning_message(
                    "Undo Edit Note",
                    f"Note with ID '{self.note_id}' not found in the project."
                )
                return CommandResult.FAILURE
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
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to undo edit note: {e}"
            self.logger.error("EditNoteCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the edit note command."""
        try:
            if self.old_content is None:
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning(
                    "EditNoteCommand.redo: cannot redo note '%s', no project is loaded",
                    self.note_id,
                )
                return CommandResult.FAILURE

            note = NoteFinder.find(project, self.note_id)
            if note is None:
                self.logger.warning(
                    "EditNoteCommand.redo: note '%s' not found", self.note_id,
                )
                return CommandResult.FAILURE
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
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to redo edit note: {e}"
            self.logger.error("EditNoteCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the pre-edit content snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.old_content = None
