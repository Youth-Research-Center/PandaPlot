"""Dialog for viewing, inserting, refreshing and cleaning up a note's artefacts
(charts, tables and images), including orphaned chart-snapshot images."""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
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
from pandaplot.gui.components.tabs.note.note_editor import NoteArtefactRow, compute_note_artefact_rows
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Note
from pandaplot.models.state.app_context import AppContext

_KIND_LABELS = {"chart": "Live chart", "image": "Gallery image", "file": "Local file", "unknown": "Unknown"}
_STATUS_LABELS = {"ok": "OK", "unused": "Unused", "broken": "Broken"}


class NoteArtefactsDialog(PDialog):
    """Lists every chart/image reference in `text_edit`'s current text
    (plus orphaned chart-snapshot images), letting the user refresh a chart
    snapshot, delete any artefact, or insert a new chart/table."""

    def __init__(
        self,
        app_context: AppContext,
        note: Note,
        text_edit: QTextEdit,
        parent: QWidget | None = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.note = note
        self.text_edit = text_edit
        self._rows: list[NoteArtefactRow] = []
        self._initialize()
        self.refresh_rows()
        # A static chart insertion lands asynchronously, after the picker
        # returns, so rows are rebuilt whenever the note text changes.
        self.text_edit.textChanged.connect(self.refresh_rows)
        self.finished.connect(self._disconnect_text_changed)

    def _disconnect_text_changed(self, _result: int = 0) -> None:
        try:
            self.text_edit.textChanged.disconnect(self.refresh_rows)
        except (RuntimeError, TypeError):
            self.logger.debug("text_edit.textChanged already disconnected", exc_info=True)

    @override
    def _init_ui(self):
        self.setWindowTitle("Manage Note Artefacts")
        self.resize(520, 360)
        layout = QVBoxLayout(self)

        # Shown instead of the table while the note has no artefacts: says
        # what artefacts are and puts the insert actions front and centre.
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("📎")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 36px;")
        empty_icon.setAccessibleName("No artefacts")
        self.empty_title_label = QLabel("No artefacts yet")
        self.empty_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.empty_label = QLabel(
            "Charts, tables and images you add to this note are listed here, "
            "so you can refresh, review or remove them.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(self.empty_title_label)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()
        self.empty_widget.setVisible(False)
        layout.addWidget(self.empty_widget, stretch=1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Status", ""])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        insert_row = QHBoxLayout()
        insert_row.addStretch()
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
        self._rows = compute_note_artefact_rows(self.app_context, self.note, self.text_edit.toPlainText())
        self.empty_widget.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))
        # With nothing listed, the insert actions are the one thing to do,
        # so the first one is the dialog's primary action.
        self.insert_chart_button.set_role("primary" if not self._rows else "secondary")

        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            self.table.setItem(row_index, 0, QTableWidgetItem(row.name))
            self.table.setItem(row_index, 1, QTableWidgetItem(_KIND_LABELS.get(row.kind, row.kind)))
            self.table.setItem(row_index, 2, QTableWidgetItem(_STATUS_LABELS.get(row.status, row.status)))
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            if row.refreshable and row.item_id is not None:
                refresh_button = PButton(
                    "Refresh", role="secondary",
                    on_click=lambda _checked=False, image_id=row.item_id: self._on_refresh_snapshot(image_id),
                )
                refresh_button.setToolTip("Re-render this snapshot from its chart's current data and style")
                refresh_button.setAccessibleName(f"Refresh snapshot {row.name}")
                actions_layout.addWidget(refresh_button)
            delete_button = PButton(
                "Delete", role="destructive",
                on_click=lambda _checked=False, r=row: self._confirm_and_delete_row(r),
            )
            delete_button.setAccessibleName(f"Delete {row.name}")
            actions_layout.addWidget(delete_button)
            self.table.setCellWidget(row_index, 3, actions)
        self.table.resizeColumnsToContents()

    def _confirm_and_delete_row(self, row: NoteArtefactRow) -> None:
        confirmed = QMessageBox.question(
            self, "Delete Artefact", f"Remove this artefact from the note? ({row.name})"
        ) == QMessageBox.StandardButton.Yes
        if not confirmed:
            return
        self._on_delete_row(row)

    def _on_delete_row(self, row: NoteArtefactRow) -> None:
        """Apply one row's delete: remove its markdown text (if any) and,
        for a snapshot this note owns, delete the underlying Image too.
        Always refreshes afterward so remaining rows' offsets stay valid.
        """
        if row.match_start is not None and row.match_end is not None:
            cursor = self.text_edit.textCursor()
            cursor.setPosition(row.match_start)
            cursor.setPosition(row.match_end, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        # A snapshot Image can be referenced more than once in the note; only
        # delete it when this row held the last such reference.
        shared = any(other is not row and other.item_id == row.item_id and other.match_start is not None for other in self._rows)
        if row.is_snapshot and row.item_id is not None and not shared:
            command = DeleteItemCommand(self.app_context, item_id=row.item_id, confirm=False)
            self.app_context.get_command_executor().execute_command(command, track_undo=True)
        self.refresh_rows()

    def _on_refresh_snapshot(self, image_id: str) -> None:
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "refresh_chart_snapshot"):
            note_editor.refresh_chart_snapshot(image_id)

    def _on_insert_chart_clicked(self) -> None:
        self._move_cursor_to_end()
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_chart_from_picker"):
            note_editor.insert_chart_from_picker()

    def _on_insert_table_clicked(self) -> None:
        self._move_cursor_to_end()
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_table_from_picker"):
            note_editor.insert_table_from_picker()

    def _move_cursor_to_end(self) -> None:
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
