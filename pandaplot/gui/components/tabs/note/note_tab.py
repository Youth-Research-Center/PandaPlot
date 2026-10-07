"""
Note tab widget for displaying and editing notes in the main tab container.
"""

from typing import override

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.project.save_project_command import SaveProjectCommand
from pandaplot.gui.components.tabs.note.note_editor import NoteEditorWidget
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import NoteEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry
from pandaplot.services.config import ConfigManager


class NoteTab(PWidget):
    """
    A tab widget for displaying and editing notes.
    """

    tab_close_requested = Signal()

    def __init__(self, app_context: AppContext, note: Note, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.app_context = app_context
        self.note = note

        self._initialize()
        self.setup_connections()
        self.register_unsaved_changes_source()

    @override
    def _init_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create note editor
        self.note_editor = NoteEditorWidget(self.app_context, self.note, self)
        layout.addWidget(self.note_editor)

    @override
    def _apply_theme(self):
        pass

    def setup_connections(self):
        """Set up event subscriptions instead of Qt rename signal."""
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self.on_note_renamed_event)
        self.subscribe_to_event(NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)

    def on_note_renamed_event(self, event_data: dict):
        """Update the tab title when the underlying note item is renamed."""
        if event_data.get("item_id") == self.note.id:
            self.refresh_tab_title()

    def on_note_content_changed_event(self, event_data: dict):
        if event_data.get("note_id") == self.note.id:
            self.refresh_tab_title()

    def refresh_tab_title(self):
        """Helper to update the tab title via parent tab widget."""
        parent_container = self.parent()
        # Climb up if needed
        while parent_container is not None and not hasattr(parent_container, "update_tab_title"):
            parent_container = parent_container.parent()
        if parent_container:
            update_fn = getattr(parent_container, "update_tab_title", None)
            if callable(update_fn):
                new_title = self.get_tab_title()
                try:
                    update_fn(self, new_title)
                except Exception:
                    self.logger.debug("Failed to update tab title on parent container", exc_info=True)

    def get_tab_title(self) -> str:
        """Get the title for this tab."""
        modified_indicator = " *" if self.note_editor.has_unsaved_changes() else ""
        return f"📝 {self.note.name}{modified_indicator}"

    def get_tab_data(self) -> dict:
        """Identify this tab to TabContainer for session/event bookkeeping."""
        return {"type": "note", "id": self.note.id}

    def can_close(self) -> bool:
        """Resolve dirty editor text before a user closes this tab/window."""
        if not self.note_editor.has_unsaved_changes():
            return True

        app_state = self.app_context.get_app_state()
        autosave_enabled = self.app_context.get_manager(ConfigManager).config.auto_save.enabled
        has_save_path = bool(app_state.project_file_path)

        # Auto-save can persist saved projects, but a new project has nowhere
        # to write yet. Let its owner choose Save (commit to model), Discard,
        # or Cancel rather than trapping the note behind a failed auto-save.
        if autosave_enabled and has_save_path:
            if app_state.is_saving:
                self.app_context.get_ui_controller().show_error_message(
                    "Save In Progress",
                    "The project is already being saved. Wait for it to finish, then close the note.",
                )
                return False
            if not self._commit_note(track_undo=False):
                return False
            return self._save_project_after_flush()

        choice = self.app_context.get_ui_controller().show_save_discard_cancel(
            "Unsaved Note",
            f"Save changes to '{self.note.name}' before closing?",
        )
        if choice == "discard":
            return True
        if choice != "save":
            return False
        if has_save_path and app_state.is_saving:
            self.app_context.get_ui_controller().show_error_message(
                "Save In Progress",
                "The project is already being saved. Wait for it to finish, then close the note.",
            )
            return False
        if not self._commit_note(track_undo=True):
            return False

        # With no path, committing the editor to the project model preserves
        # the edit for the normal project-level save/discard prompt.
        if not has_save_path:
            return True
        return self._save_project_after_flush()

    def _save_project_after_flush(self) -> bool:
        """Flush other local edits before starting the standard async save."""
        registry = self.app_context.get_manager(UnsavedChangesRegistry)
        if not registry.flush_all():
            self.app_context.get_ui_controller().show_error_message("Unsaved Changes", "An open note could not be saved. The tab will stay open.")
            return False
        return self._save_project()

    def _commit_note(self, *, track_undo: bool) -> bool:
        try:
            saved = self.note_editor.save_content(track_undo=track_undo)
        except Exception:  # noqa: BLE001 - a user close must leave the tab open on failure
            saved = False
        if not saved:
            self.app_context.get_ui_controller().show_error_message("Save Failed", "The note edit could not be applied; the tab will stay open.")
        return saved

    def _save_project(self) -> bool:
        """Start the standard async project-save command for the current path."""
        command = SaveProjectCommand(self.app_context)
        if self.app_context.get_command_executor().execute_command(command, track_undo=False):
            return True
        if self.app_context.get_app_state().is_saving:
            return False
        # SaveProjectCommand handles its own failures with UI feedback. A
        # command rejected before dispatch (e.g. no project) still keeps the
        # tab open and reports a failure here.
        self.app_context.get_ui_controller().show_error_message("Save Failed", "The project could not be saved; the note will stay open.")
        return False

    def save(self) -> bool:
        """Save the note for UnsavedChangesRegistry's flush. Returns whether
        the save actually committed (see NoteEditorWidget.save_content) --
        False means the note is still dirty and must not be treated as
        safely persisted.

        Commits without occupying an undo slot (track_undo=False) -- this
        is a forced, infrastructure-triggered commit (a project-lifecycle
        guard, or another command's own undo()/redo() swapping the current
        project out from under this note), not a user-initiated Save
        action, so it must not interleave with a command that already
        occupies a stack slot for an operation that hasn't finished yet
        (see PR #352 review)."""
        try:
            return self.note_editor.save_content(track_undo=False)
        except Exception:  # noqa: BLE001 -- GUI event-handler safety net -- an unexpected error here must not crash the UI
            return False

    def has_unsaved_changes(self) -> bool:
        """Whether this tab's note editor has an edit not yet committed to the
        project model (see NoteEditorWidget.has_unsaved_changes)."""
        return self.note_editor.has_unsaved_changes()

    def get_note(self) -> Note:
        """Get the note associated with this tab."""
        return self.note
