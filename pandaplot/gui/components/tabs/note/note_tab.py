"""
Note tab widget for displaying and editing notes in the main tab container.
"""

from typing import override

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.note.note_editor import NoteEditorWidget
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import NoteEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext


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
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED,
                                self.on_note_renamed_event)
        self.subscribe_to_event(
            NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)

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
                    pass

    def get_tab_title(self) -> str:
        """Get the title for this tab."""
        modified_indicator = " *" if self.note_editor.has_unsaved_changes() else ""
        return f"📝 {self.note.name}{modified_indicator}"

    def get_tab_data(self) -> dict:
        """Identify this tab to TabContainer for session/event bookkeeping."""
        return {"type": "note", "id": self.note.id}

    def can_close(self) -> bool:
        """Check if the tab can be closed."""
        if self.note_editor.has_unsaved_changes():
            # TODO(#221): Show save dialog
            return True  # For now, allow closing
        return True

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
        except Exception:
            return False

    def has_unsaved_changes(self) -> bool:
        """Whether this tab's note editor has an edit not yet committed to the
        project model (see NoteEditorWidget.has_unsaved_changes)."""
        return self.note_editor.has_unsaved_changes()

    def get_note(self) -> Note:
        """Get the note associated with this tab."""
        return self.note
