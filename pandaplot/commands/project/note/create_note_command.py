import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.require_project import ensure_project_or_offer_create
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Note
from pandaplot.models.state import AppContext, AppState


class CreateNoteCommand(Command):
    """
    Command to create a new note in the project.
    """

    def __init__(self, app_context: AppContext, note_name: Optional[str] = None,
                 content: str = "", folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.note_name = note_name
        self.content = content
        self.folder_id = folder_id

        # Store state for undo
        self.created_note_id = None
        self.created_note = None
        self.project = None

    @override
    def execute(self) -> CommandResult:
        """Execute the create note command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project or not self.app_state.current_project:
                self.logger.warning(
                    "CreateNoteCommand.execute: no project is currently loaded, note '%s'",
                    self.note_name,
                )
                if not ensure_project_or_offer_create(
                    self.app_context, "New Note",
                    "Creating a note requires a project. Create a new project to continue?",
                ):
                    return CommandResult.FAILURE

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning(
                    "CreateNoteCommand.execute: has_project is True but current_project is None"
                )
                return CommandResult.FAILURE

            # Get note name if not provided
            if not self.note_name:
                note_name = "New Note"
            else:
                note_name = self.note_name

            # Create note ID
            self.created_note_id = str(uuid.uuid4())
            self.created_note = Note(
                id=self.created_note_id,
                name=note_name,
                content=self.content
            )

            # Add note to project using hierarchical structure
            self.project.add_item(self.created_note, parent_id=self.folder_id)

            # Emit dotted event only (legacy underscore events removed)
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": self.project,
                "note_id": self.created_note_id,
                "note_name": note_name,
                "folder_id": self.folder_id,
                "note": self.created_note
            })
            self.logger.info(
                "CreateNoteCommand: Created note '%s' (id=%s) in folder %s",
                note_name,
                self.created_note_id,
                self.folder_id or "root"
            )

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to create note: {str(e)}"
            self.logger.error("CreateNoteCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Create Note Error", error_msg)
            return CommandResult.FAILURE

    def undo(self) -> CommandResult:
        """Undo the create note command."""
        try:
            if self.created_note_id and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    self.logger.warning(
                        "CreateNoteCommand.undo: has_project is True but current_project is None (note id=%s)",
                        self.created_note_id,
                    )
                    return CommandResult.FAILURE

                note = project.find_item(self.created_note_id)
                if note is None:
                    self.logger.warning(
                        "CreateNoteCommand.undo: note '%s' not found", self.created_note_id
                    )
                    return CommandResult.FAILURE

                project.remove_item(note)

                # Emit dotted delete event
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                    "project": project,
                    "note_id": self.created_note_id,
                    "note": self.created_note
                })
                self.logger.info(
                    "CreateNoteCommand: Undo creation of note id=%s (name=%s)",
                    self.created_note_id,
                    getattr(self.created_note, "name", "<unknown>")
                )
                return CommandResult.SUCCESS
            else:
                # The note was never actually created (execute() failed or
                # was never called), so there's nothing to undo.
                return CommandResult.NOOP

        except Exception as e:
            error_msg = f"Failed to undo create note: {str(e)}"
            self.logger.error("CreateNoteCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the create note command."""
        try:
            if self.created_note_id and self.created_note is not None and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    self.logger.warning(
                        "CreateNoteCommand.redo: has_project is True but current_project is None for note id=%s",
                        self.created_note_id,
                    )
                    return CommandResult.FAILURE

                # Re-add the same note object to the project
                project.add_item(self.created_note, parent_id=self.folder_id)

                # Emit dotted event only
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": project,
                    "note_id": self.created_note_id,
                    "note_name": self.created_note.name,
                    "folder_id": self.folder_id,
                    "note": self.created_note
                })
                self.logger.info(
                    "CreateNoteCommand: Redo creation of item '%s' (id=%s) in folder %s",
                    self.created_note.name,
                    self.created_note_id,
                    self.folder_id or "root"
                )
                return CommandResult.SUCCESS
            else:
                return CommandResult.FAILURE

        except Exception as e:
            error_msg = f"Failed to redo create note: {str(e)}"
            self.logger.error("CreateNoteCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the cached project reference held during creation once
        this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.project = None
