"""
Note tab widget for displaying and editing notes in the main tab container.
"""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.item.rename_item_command import RenameItemCommand
from pandaplot.commands.project.note.edit_note_command import EditNoteCommand
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext


from pandaplot.models.events.event_types import NoteEvents, UIEvents
from pandaplot.models.events.mixins import EventBusComponentMixin


class NoteEditorWidget(EventBusComponentMixin, QWidget):
    """
    A modern note editor widget with text editing capabilities.
    """
    
    content_changed = Signal(str)  # Local signal for immediate editor reactions
    
    def __init__(self, app_context: AppContext, note: Note, parent=None):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self.app_context = app_context
        self.note = note
        self.is_modified = False
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.setSingleShot(True)
        
        self.setup_ui()
        self.load_note_content()
        self.setup_connections()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Header section with note title and info
        self.create_header_section(layout)
        
        # Main content area
        self.create_content_section(layout)
        
        # Status bar
        self.create_status_section(layout)
    
    def create_header_section(self, layout):
        """Create the header section with note title and metadata."""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        # Title row
        title_layout = QHBoxLayout()
        
        # Note title label
        title_label = QLabel("📝 Note:")
        title_label.setStyleSheet("font-weight: bold; color: #495057;")
        title_layout.addWidget(title_label)
        
        # Editable note name
        self.title_edit = QLineEdit(self.note.name)
        self.title_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #80bdff;
            }
        """)
        title_layout.addWidget(self.title_edit)
        
        # Save title button
        self.save_title_btn = QPushButton("💾 Save Title")
        self.save_title_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.save_title_btn.clicked.connect(self.save_title)
        title_layout.addWidget(self.save_title_btn)
        
        header_layout.addLayout(title_layout)
        
        # Metadata row
        metadata_layout = QHBoxLayout()
        
        self.created_label = QLabel(f"Created: {self.note.created_at[:19] if self.note.created_at else 'Unknown'}")
        self.created_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        metadata_layout.addWidget(self.created_label)
        
        metadata_layout.addStretch()
        
        self.modified_label = QLabel(f"Modified: {self.note.modified_at[:19] if self.note.modified_at else 'Unknown'}")
        self.modified_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        metadata_layout.addWidget(self.modified_label)
        
        header_layout.addLayout(metadata_layout)
        
        layout.addWidget(header_frame)
    
    def create_content_section(self, layout):
        """Create the main content editing section."""
        # Content frame
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
                padding: 4px;
            }
            QToolBar::separator {
                background-color: #e9ecef;
                width: 1px;
                margin: 4px 2px;
            }
        """)
        
        # Add formatting actions
        self.create_toolbar_actions(toolbar)
        content_layout.addWidget(toolbar)
        
        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        
        # Set a nice font
        font = QFont("Segoe UI", 11)
        self.text_edit.setFont(font)
        
        content_layout.addWidget(self.text_edit)
        
        layout.addWidget(content_frame)
    
    def create_toolbar_actions(self, toolbar):
        """Create toolbar actions for text formatting."""
        # Bold action
        bold_action = QAction("🅱 Bold", self)
        bold_action.setShortcut(QKeySequence.StandardKey.Bold)
        bold_action.triggered.connect(self.toggle_bold)
        toolbar.addAction(bold_action)
        
        # Italic action
        italic_action = QAction("🇮 Italic", self)
        italic_action.setShortcut(QKeySequence.StandardKey.Italic)
        italic_action.triggered.connect(self.toggle_italic)
        toolbar.addAction(italic_action)
        
        # Underline action
        underline_action = QAction("🇺 Underline", self)
        underline_action.setShortcut(QKeySequence.StandardKey.Underline)
        underline_action.triggered.connect(self.toggle_underline)
        toolbar.addAction(underline_action)
        
        toolbar.addSeparator()
        
        # Save action
        save_action = QAction("💾 Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_content)
        toolbar.addAction(save_action)
        
        # Clear action
        clear_action = QAction("🗑 Clear", self)
        clear_action.triggered.connect(self.clear_content)
        toolbar.addAction(clear_action)
    
    def create_status_section(self, layout):
        """Create the status section with statistics."""
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 4, 12, 4)
        
        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        status_layout.addWidget(self.word_count_label)
        
        self.char_count_label = QLabel("Characters: 0")
        self.char_count_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        status_layout.addWidget(self.char_count_label)
        
        status_layout.addStretch()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        layout.addWidget(status_frame)
    
    def setup_connections(self):
        """Set up signal connections and event subscriptions."""
        self.text_edit.textChanged.connect(self.on_content_changed)
        self.title_edit.textChanged.connect(self.on_title_changed)
        # Subscribe to external rename/content change events for this note
        self.subscribe_to_event(NoteEvents.NOTE_RENAMED, self.on_note_renamed_event)
        self.subscribe_to_event(NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)
    
    def load_note_content(self):
        """Load the note content into the editor."""
        self.text_edit.setPlainText(self.note.content)
        self.update_statistics()
        self.is_modified = False
        self.update_status("Ready")
    
    def on_content_changed(self):
        """Handle content changes."""
        self.is_modified = True
        self.update_status("Modified *")
        self.update_statistics()
        
        # Start auto-save timer (save after 2 seconds of inactivity)
        self.auto_save_timer.start(2000)
        
        # Emit content changed signal
        content = self.text_edit.toPlainText()
        self.content_changed.emit(content)
    
    def on_title_changed(self):
        """Handle title changes."""
        # Enable save button when title changes
        current_title = self.title_edit.text().strip()
        self.save_title_btn.setEnabled(current_title != self.note.name and bool(current_title))
    
    def update_statistics(self):
        """Update word and character count."""
        content = self.text_edit.toPlainText()
        word_count = len(content.split()) if content.strip() else 0
        char_count = len(content)
        
        self.word_count_label.setText(f"Words: {word_count}")
        self.char_count_label.setText(f"Characters: {char_count}")
    
    def update_status(self, status: str):
        """Update the status label."""
        self.status_label.setText(status)
        
        # Update color based on status
        if "Modified" in status:
            self.status_label.setStyleSheet("color: #ffc107; font-size: 12px; font-weight: bold;")
        elif "Saved" in status:
            self.status_label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
        elif "Error" in status:
            self.status_label.setStyleSheet("color: #dc3545; font-size: 12px; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #6c757d; font-size: 12px; font-weight: bold;")
    
    def save_content(self):
        """Save the note content."""
        try:
            content = self.text_edit.toPlainText()
            
            # Execute save command
            command = EditNoteCommand(self.app_context, self.note.id, content)
            self.app_context.get_command_executor().execute_command(command)
            
            # Local model already updated by command; avoid duplicate mutation
            
            # Update UI
            self.is_modified = False
            self.update_status("Saved ✓")
            self.update_metadata()
            
            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
    
    def save_title(self):
        """Save the note title."""
        try:
            new_title = self.title_edit.text().strip()
            if not new_title:
                self.update_status("Error: Title cannot be empty")
                return
            
            if new_title == self.note.name:
                return
            
            old_name = self.note.name
            
            # Execute rename command
            command = RenameItemCommand(self.app_context, self.note.id, new_title)
            self.app_context.get_command_executor().execute_command(command)
            
            # Local model already updated by command
            
            # Update UI
            self.save_title_btn.setEnabled(False)
            self.update_status("Title saved ✓")
            self.update_metadata()
            
            # Publish UI tab title changed event for tab container
            self.publish_event(UIEvents.TAB_TITLE_CHANGED, {
                'old_title': old_name,
                'new_title': new_title,
                'tab_type': 'note',
                'note_id': self.note.id
            })
            
            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
    
    def auto_save(self):
        """Auto-save the content."""
        if self.is_modified:
            self.save_content()
    
    def update_metadata(self):
        """Update the metadata labels."""
        self.modified_label.setText(f"Modified: {self.note.modified_at[:19] if self.note.modified_at else 'Unknown'}")

    # --- Event handlers ---
    def on_note_renamed_event(self, event_data: dict):
        """Handle external note rename events (including undo/redo)."""
        if event_data.get('note_id') != self.note.id:
            return
        new_title = event_data.get('new_name')
        if new_title and self.title_edit.text().strip() != new_title:
            # Update UI field without triggering save button enable logic incorrectly
            self.title_edit.blockSignals(True)
            self.title_edit.setText(new_title)
            self.title_edit.blockSignals(False)
            self.save_title_btn.setEnabled(False)
            # Fire UI title changed event for tab container consistency
            self.publish_event(UIEvents.TAB_TITLE_CHANGED, {
                'old_title': event_data.get('old_name'),
                'new_title': new_title,
                'tab_type': 'note',
                'note_id': self.note.id
            })

    def on_note_content_changed_event(self, event_data: dict):
        """Handle external note content changes (undo/redo or other editors)."""
        if event_data.get('note_id') != self.note.id:
            return
        new_content = event_data.get('new_content')
        if new_content is not None and self.text_edit.toPlainText() != new_content:
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(new_content)
            self.text_edit.blockSignals(False)
            self.update_statistics()
            self.is_modified = False
            self.update_status("Synced ✓")
    
    def toggle_bold(self):
        """Toggle bold formatting."""
        cursor = self.text_edit.textCursor()
        char_format = cursor.charFormat()
        
        if char_format.fontWeight() == QFont.Weight.Bold:
            char_format.setFontWeight(QFont.Weight.Normal)
        else:
            char_format.setFontWeight(QFont.Weight.Bold)
        
        cursor.setCharFormat(char_format)
        self.text_edit.setTextCursor(cursor)
    
    def toggle_italic(self):
        """Toggle italic formatting."""
        cursor = self.text_edit.textCursor()
        char_format = cursor.charFormat()
        char_format.setFontItalic(not char_format.fontItalic())
        cursor.setCharFormat(char_format)
        self.text_edit.setTextCursor(cursor)
    
    def toggle_underline(self):
        """Toggle underline formatting."""
        cursor = self.text_edit.textCursor()
        char_format = cursor.charFormat()
        char_format.setFontUnderline(not char_format.fontUnderline())
        cursor.setCharFormat(char_format)
        self.text_edit.setTextCursor(cursor)
    
    def clear_content(self):
        """Clear all content."""
        self.text_edit.clear()
    
    def get_note(self) -> Note:
        """Get the current note object."""
        return self.note
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.is_modified


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
        self.subscribe_to_event(UIEvents.TAB_TITLE_CHANGED, self.on_tab_title_changed_event)
        self.subscribe_to_event(NoteEvents.NOTE_RENAMED, self.on_note_renamed_event)
        self.subscribe_to_event(NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)
    
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
