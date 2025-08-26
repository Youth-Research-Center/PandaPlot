"""
Note tab widget for displaying and editing notes in the main tab container.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.note.note_editor import NoteEditorWidget
from pandaplot.models.events import NoteEvents, UIEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext


class NoteTab(EventBusComponentMixin, QWidget):
    """
    A tab widget for displaying and editing notes.
    """

    tab_close_requested = Signal()

    def __init__(self, app_context: AppContext, note: Note, parent=None):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self.app_context = app_context
        self.note = note

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create note editor
        self.note_editor = NoteEditorWidget(self.app_context, self.note)
        layout.addWidget(self.note_editor)

    def setup_connections(self):
        """Set up event subscriptions instead of Qt rename signal."""
        self.subscribe_to_event(
            UIEvents.TAB_TITLE_CHANGED, self.on_tab_title_changed_event)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED,
                                self.on_note_renamed_event)
        self.subscribe_to_event(
            NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)

    def on_tab_title_changed_event(self, event_data: dict):
        """Update tab title when UI tab title changed event is emitted for this note."""
        if event_data.get('tab_type') == 'note' and event_data.get('note_id') == self.note.id:
            self.refresh_tab_title()

    def on_note_renamed_event(self, event_data: dict):
        """Fallback in case UI event wasn't published (should be) - ensures title refresh."""
        if event_data.get('note_id') == self.note.id:
            self.refresh_tab_title()

    def on_note_content_changed_event(self, event_data: dict):
        if event_data.get('note_id') == self.note.id:
            self.refresh_tab_title()

    def refresh_tab_title(self):
        """Helper to update the tab title via parent tab widget."""
        parent_container = self.parent()
        # Climb up if needed
        while parent_container is not None and not hasattr(parent_container, 'update_tab_title'):
            parent_container = parent_container.parent()
        if parent_container:
            update_fn = getattr(parent_container, 'update_tab_title', None)
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

    def can_close(self) -> bool:
        """Check if the tab can be closed."""
        if self.note_editor.has_unsaved_changes():
            # TODO: Show save dialog
            return True  # For now, allow closing
        return True

    def save(self) -> bool:
        """Save the note."""
        try:
            self.note_editor.save_content()
            return True
        except Exception:
            return False

    def get_note(self) -> Note:
        """Get the note associated with this tab."""
        return self.note
