"""Dialog for viewing, inserting, and cleaning up a note's chart/image
references, including orphaned chart-snapshot images."""

from typing import List, Optional, override

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.item.delete_item_command import DeleteItemCommand
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.tabs.note.note_editor import NoteLinkRow, compute_note_link_rows
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Note
from pandaplot.models.state.app_context import AppContext

_KIND_LABELS = {"chart": "Live chart", "image": "Gallery image", "file": "Local file", "unknown": "Unknown"}
_STATUS_LABELS = {"ok": "OK", "unused": "Unused", "broken": "Broken"}


class NoteLinksDialog(PDialog):
    """Lists every chart/image reference in `text_edit`'s current text
    (plus orphaned chart-snapshot images), letting the user delete any of
    them or insert a new chart/table reference."""

    def __init__(
        self,
        app_context: AppContext,
        note: Note,
        text_edit: QTextEdit,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.note = note
        self.text_edit = text_edit
        self._rows: List[NoteLinkRow] = []
        self._initialize()
        self.refresh_rows()

    @override
    def _init_ui(self):
        self.setWindowTitle("Manage Note Links")
        self.resize(520, 360)
        layout = QVBoxLayout(self)

        self.empty_label = QLabel("No chart or image references in this note.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Status", ""])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table)

        insert_row = QHBoxLayout()
        self.insert_chart_button = PButton(
            "📊 Insert Chart...", role="secondary", on_click=self._on_insert_chart_clicked)
        self.insert_table_button = PButton(
            "📋 Insert Table...", role="secondary", on_click=self._on_insert_table_clicked)
        insert_row.addWidget(self.insert_chart_button)
        insert_row.addWidget(self.insert_table_button)
        insert_row.addStretch()
        layout.addLayout(insert_row)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.close_button = PButton("Close", role="secondary", on_click=self.accept)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def refresh_rows(self) -> None:
        """Recompute rows from the text_edit's current content and rebuild
        the table. Must be called after every delete, since deleting one
        row's markdown text shifts the match offsets of every row after it
        in the text -- rebuilding from scratch keeps them all valid."""
        self._rows = compute_note_link_rows(self.app_context, self.note, self.text_edit.toPlainText())
        self.empty_label.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            self.table.setItem(row_index, 0, QTableWidgetItem(row.name))
            self.table.setItem(row_index, 1, QTableWidgetItem(_KIND_LABELS.get(row.kind, row.kind)))
            self.table.setItem(row_index, 2, QTableWidgetItem(_STATUS_LABELS.get(row.status, row.status)))
            delete_button = PButton(
                "Delete", role="destructive",
                on_click=lambda _checked=False, r=row: self._confirm_and_delete_row(r),
            )
            self.table.setCellWidget(row_index, 3, delete_button)
        self.table.resizeColumnsToContents()

    def _confirm_and_delete_row(self, row: NoteLinkRow) -> None:
        confirmed = QMessageBox.question(
            self, "Delete Link", f"Remove this reference from the note? ({row.name})"
        ) == QMessageBox.StandardButton.Yes
        if not confirmed:
            return
        self._on_delete_row(row)

    def _on_delete_row(self, row: NoteLinkRow) -> None:
        """Apply one row's delete: remove its markdown text (if any) and,
        for a snapshot this note owns, delete the underlying Image too.
        Always refreshes afterward so remaining rows' offsets stay valid.
        """
        if row.match_start is not None and row.match_end is not None:
            cursor = self.text_edit.textCursor()
            cursor.setPosition(row.match_start)
            cursor.setPosition(row.match_end, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        if row.is_snapshot and row.item_id is not None:
            command = DeleteItemCommand(self.app_context, item_id=row.item_id, confirm=False)
            self.app_context.get_command_executor().execute_command(command, track_undo=True)
        self.refresh_rows()

    def _on_insert_chart_clicked(self) -> None:
        self._move_cursor_to_end()
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_chart_from_picker"):
            note_editor.insert_chart_from_picker()
        self.refresh_rows()

    def _on_insert_table_clicked(self) -> None:
        self._move_cursor_to_end()
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_table_from_picker"):
            note_editor.insert_table_from_picker()
        self.refresh_rows()

    def _move_cursor_to_end(self) -> None:
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
