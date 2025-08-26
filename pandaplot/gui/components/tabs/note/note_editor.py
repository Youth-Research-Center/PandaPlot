"""
Note tab widget for displaying and editing notes in the main tab container.
"""
import logging
from typing import Optional

from markdown import markdown
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.note.edit_note_command import EditNoteCommand
from pandaplot.models.events import NoteEvents
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext


class NoteEditorWidget(EventBusComponentMixin, QWidget):
    """
    A modern note editor widget with text editing capabilities.
    """

    # Local signal for immediate editor reactions
    content_changed = Signal(str)

    def __init__(self, app_context: AppContext, note: Note, parent: Optional[QWidget] = None):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.note = note
        self.is_modified = False
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.setSingleShot(True)

        # Since we can't check if the preview is connected, track it with a flag
        self.preview_connected = False

        self.setup_ui()
        self.load_note_content()
        self.setup_connections()

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Main content area
        self.create_content_section(layout)

        # Status bar
        self.create_status_section(layout)

    def create_content_section(self, layout: QLayout):
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

        # Apply theme-aware styling to the toolbar
        theme_manager = self.app_context.theme_manager
        palette = theme_manager.get_surface_palette()
        base_fg = palette.get('base_fg', '#495057')
        surface_bg = palette.get('surface', '#f8f9fa')
        border_color = palette.get('border', '#e9ecef')

        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {surface_bg};
                border-bottom: 1px solid {border_color};
                padding: 4px;
                color: {base_fg};
            }}
            QToolBar QToolButton {{
                color: {base_fg};
                background-color: transparent;
                border: none;
                padding: 6px 10px;
                margin: 1px;
                border-radius: 3px;
                font-weight: 500;
            }}
            QToolBar QToolButton:hover {{
                background-color: {border_color};
                color: {base_fg};
            }}
            QToolBar QToolButton:pressed {{
                background-color: {border_color};
                color: {base_fg};
            }}
            QToolBar::separator {{
                background-color: {border_color};
                width: 1px;
                margin: 4px 2px;
            }}
        """)

        # Add formatting actions
        self.create_toolbar_actions(toolbar)
        content_layout.addWidget(toolbar)

        # Create main editor and preview widgets
        self.text_edit = QTextEdit()
        font = QFont("Segoe UI", 11)
        self.text_edit.setFont(font)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)

        # Create container widgets for each mode

        # Edit mode container - just the text editor
        self.edit_container = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_container)
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_layout.addWidget(self.text_edit)

        # Preview mode container - just the preview
        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.addWidget(self.preview)

        # Split mode container - splitter with both widgets
        self.splitter = QSplitter(orientation=Qt.Orientation.Horizontal)

        # Stack for mode switching
        self.stack = QStackedWidget()
        self.stack.addWidget(self.edit_container)     # index 0
        self.stack.addWidget(self.preview_container)  # index 1
        self.stack.addWidget(self.splitter)    # index 2

        content_layout.addWidget(self.stack)
        layout.addWidget(content_frame)

        # Default mode
        self.set_mode("edit")

    def set_mode(self, mode: str):
        """Switch between edit, preview, and split modes."""
        if mode not in ["edit", "preview", "split"]:
            self.logger.warning(f"Unknown mode: {mode}")
            return

        if mode == "edit":
            self.text_edit.setParent(self.edit_container)
            self.edit_layout.addWidget(self.text_edit)
            self.stack.setCurrentIndex(0)
            self._changePreviewConnection(False)

        elif mode == "preview":
            self.preview.setParent(self.preview_container)
            self.preview_layout.addWidget(self.preview)
            self.update_preview()
            self.stack.setCurrentIndex(1)
            self._changePreviewConnection(False)

        elif mode == "split":
            self.text_edit.setParent(self.splitter)
            self.preview.setParent(self.splitter)
            self._changePreviewConnection(True)
            self.update_preview()
            self.stack.setCurrentIndex(2)

    def _changePreviewConnection(self, shouldBeConnected: bool):
        """Change the connection state of the preview."""
        self.logger.debug(
            f"Changing preview connection from {self.preview_connected} to {shouldBeConnected}")
        if shouldBeConnected and not self.preview_connected:
            self.text_edit.textChanged.connect(self.update_preview)
            self.preview_connected = True
        elif not shouldBeConnected and self.preview_connected:
            self.text_edit.textChanged.disconnect(self.update_preview)
            self.preview_connected = False

    def update_preview(self):
        """Render Markdown into preview panel."""
        md_text = self.text_edit.toPlainText()
        html = markdown(md_text, extensions=["tables", "fenced_code"])
        self.preview.setHtml(html)

    def create_toolbar_actions(self, toolbar: QToolBar):
        """Create toolbar actions for text formatting."""

        # Save action
        save_action = QAction("💾 Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_content)
        toolbar.addAction(save_action)

        # Clear action
        clear_action = QAction("🗑 Clear", self)
        clear_action.triggered.connect(self.clear_content)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()
        self.edit_mode_action = QAction("✍ Edit", self)
        self.edit_mode_action.triggered.connect(lambda: self.set_mode("edit"))
        toolbar.addAction(self.edit_mode_action)

        self.preview_mode_action = QAction("👁 Preview", self)
        self.preview_mode_action.triggered.connect(
            lambda: self.set_mode("preview"))
        toolbar.addAction(self.preview_mode_action)

        self.split_mode_action = QAction("⇔ Split", self)
        self.split_mode_action.triggered.connect(
            lambda: self.set_mode("split"))
        toolbar.addAction(self.split_mode_action)

    def create_status_section(self, layout: QLayout):
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
        self.status_label.setStyleSheet(
            "color: #28a745; font-size: 12px; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        layout.addWidget(status_frame)

    def setup_connections(self):
        """Set up signal connections and event subscriptions."""
        self.text_edit.textChanged.connect(self.on_content_changed)

        # Subscribe to external rename/content change events for this note
        self.subscribe_to_event(
            NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)

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
            self.status_label.setStyleSheet(
                "color: #ffc107; font-size: 12px; font-weight: bold;")
        elif "Saved" in status:
            self.status_label.setStyleSheet(
                "color: #28a745; font-size: 12px; font-weight: bold;")
        elif "Error" in status:
            self.status_label.setStyleSheet(
                "color: #dc3545; font-size: 12px; font-weight: bold;")
        else:
            self.status_label.setStyleSheet(
                "color: #6c757d; font-size: 12px; font-weight: bold;")

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

            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))

        except Exception as e:
            self.update_status(f"Error: {str(e)}")

    def auto_save(self):
        """Auto-save the content."""
        if self.is_modified:
            self.save_content()

    def on_note_content_changed_event(self, event_data: dict):
        """Handle external note content changes (undo/redo or other editors)."""
        if event_data.get('note_id') != self.note.id:
            return
        new_content = event_data.get('new_content')
        if new_content is not None and self.text_edit.toPlainText() != new_content:
            self.text_edit.blockSignals(True)
            self.text_edit.setMarkdown(new_content)
            self.text_edit.blockSignals(False)
            self.update_statistics()
            self.is_modified = False
            self.update_status("Synced ✓")

    def refresh_theme_styling(self):
        """Refresh all theme-dependent styling. Call this when theme changes."""
        theme_manager = self.app_context.theme_manager
        palette = theme_manager.get_surface_palette()
        base_fg = palette.get('base_fg', '#495057')
        surface_bg = palette.get('surface', '#f8f9fa')
        border_color = palette.get('border', '#e9ecef')

        # Find and update the toolbar styling
        for child in self.findChildren(QToolBar):
            child.setStyleSheet(f"""
                QToolBar {{
                    background-color: {surface_bg};
                    border-bottom: 1px solid {border_color};
                    padding: 4px;
                    color: {base_fg};
                }}
                QToolBar QToolButton {{
                    color: {base_fg};
                    background-color: transparent;
                    border: none;
                    padding: 6px 10px;
                    margin: 1px;
                    border-radius: 3px;
                    font-weight: 500;
                }}
                QToolBar QToolButton:hover {{
                    background-color: {border_color};
                    color: {base_fg};
                }}
                QToolBar QToolButton:pressed {{
                    background-color: {border_color};
                    color: {base_fg};
                }}
                QToolBar::separator {{
                    background-color: {border_color};
                    width: 1px;
                    margin: 4px 2px;
                }}
            """)
            break  # TODO: not sure why we break here

    def clear_content(self):
        """Clear all content."""
        self.text_edit.clear()

    def get_note(self) -> Note:
        """Get the current note object."""
        return self.note

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.is_modified
