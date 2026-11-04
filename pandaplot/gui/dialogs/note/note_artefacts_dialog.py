"""Dialog for viewing, inserting, refreshing and cleaning up a note's artefacts
(charts, tables and images), including orphaned chart-snapshot images."""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
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
from shiboken6 import isValid

from pandaplot.commands.project.item.delete_item_command import DeleteItemCommand
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.snapshot_dpi_combo_box import CHART_DEFAULT_LABEL
from pandaplot.gui.components.tabs.note.note_editor import NoteArtefactRow, compute_note_artefact_rows
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.gui.dialogs.note.snapshot_dpi_dialog import SnapshotDpiDialog
from pandaplot.models.project.items import Note
from pandaplot.models.project.items.image import KEEP_RENDER_DPI, KeepRenderDpi
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry

_KIND_LABELS = {"image": "Gallery image", "file": "Local file", "unknown": "Unknown"}
_STATUS_LABELS = {"ok": "OK", "unused": "Unused", "broken": "Broken"}
_ACTIONS_COLUMN = 4


def _dpi_text(row: NoteArtefactRow) -> str:
    """The DPI column text: a chart snapshot's stored DPI or the chart-default
    label, and "-" for anything that is not a chart snapshot."""
    if not row.is_chart_snapshot:
        return "-"
    return CHART_DEFAULT_LABEL if row.render_dpi is None else str(row.render_dpi)


def _text_cursor_position(text: str, index: int) -> int:
    """The QTextCursor position of Python string index `index` in `text`.
    Qt counts UTF-16 code units, so each character outside the Basic
    Multilingual Plane (e.g. most emoji) before `index` shifts it by one."""
    return len(text[:index].encode("utf-16-le")) // 2


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

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Status", "DPI", ""])
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
        the table. Deleting one row's markdown text shifts the match offsets
        of every row after it in the text, so the rows are rebuilt from
        scratch after every delete (see `_on_delete_row`). A snapshot's Refresh
        and DPI buttons are disabled while the note editor is still rendering it."""
        self._rows = compute_note_artefact_rows(self.app_context, self.note, self.text_edit.toPlainText())
        is_refreshing = getattr(self.parent(), "is_refreshing_snapshot", None)
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
            self.table.setItem(row_index, 3, QTableWidgetItem(_dpi_text(row)))
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            if row.refreshable and row.item_id is not None:
                busy = is_refreshing is not None and is_refreshing(row.item_id)
                refresh_button = PButton("Refresh", role="secondary")
                refresh_button.clicked.connect(
                    lambda _checked=False, image_id=row.item_id: self._on_refresh_snapshot(image_id))
                refresh_button.setEnabled(not busy)
                refresh_button.setToolTip(
                    "Refresh in progress" if busy
                    else "Re-render this snapshot from its chart's current data and style")
                refresh_button.setAccessibleName(f"Refresh snapshot {row.name}")
                actions_layout.addWidget(refresh_button)
                dpi_button = PButton("DPI...", role="secondary")
                dpi_button.clicked.connect(lambda _checked=False, r=row: self._on_change_dpi(r))
                dpi_button.setEnabled(not busy)
                dpi_button.setToolTip("Refresh in progress" if busy else "Re-render this snapshot at a different DPI")
                dpi_button.setAccessibleName(f"Change DPI of snapshot {row.name}")
                actions_layout.addWidget(dpi_button)
            delete_button = PButton(
                "Delete", role="destructive",
                on_click=lambda _checked=False, r=row: self._confirm_and_delete_row(r),
            )
            delete_button.setAccessibleName(f"Delete {row.name}")
            actions_layout.addWidget(delete_button)
            self.table.setCellWidget(row_index, _ACTIONS_COLUMN, actions)
        self.table.resizeColumnsToContents()

    def _confirm_and_delete_row(self, row: NoteArtefactRow) -> None:
        # A chart insertion can land while the confirmation is open and shift
        # every reference offset, so `row` may no longer point at its text.
        revision = self.text_edit.document().revision()
        confirmed = QMessageBox.question(
            self, "Delete Artefact", f"Remove this artefact from the note? ({row.name})"
        ) == QMessageBox.StandardButton.Yes
        if not confirmed:
            return
        if self.text_edit.document().revision() != revision:
            self.refresh_rows()
            self.app_context.get_ui_controller().show_warning_message(
                "Delete Artefact", "The note changed while waiting for confirmation. Select the artefact again to delete it.")
            return
        self._on_delete_row(row)

    def _on_delete_row(self, row: NoteArtefactRow) -> None:
        """Apply one row's delete. A row with a reference in the note text
        removes just that text (undoable from the editor), so a snapshot it
        pointed at becomes an "Unused" row; an unused snapshot's row deletes
        the image (undoable from the project). Each action therefore has a
        single, independent undo. The rows are rebuilt afterward so remaining
        rows' offsets stay valid: by the textChanged connection for a text
        edit, explicitly for an image delete.
        """
        if row.match_start is not None and row.match_end is not None:
            text = self.text_edit.toPlainText()
            cursor = self.text_edit.textCursor()
            cursor.setPosition(_text_cursor_position(text, row.match_start))
            cursor.setPosition(_text_cursor_position(text, row.match_end), QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        elif row.is_snapshot and row.item_id is not None:
            self._delete_unused_snapshot(row.item_id)

    def _delete_unused_snapshot(self, image_id: str) -> None:
        """Delete a snapshot Image project-wide, unless a note still refers to it.

        Other open notes may hold a reference that is still inside their
        auto-save delay, so their pending edits are committed first and the
        row is re-checked against them. If they can't be committed the
        check can't be trusted and nothing is deleted.
        """
        if not self.app_context.get_manager(UnsavedChangesRegistry).flush_all():
            self.app_context.get_ui_controller().show_warning_message(
                "Delete Artefact", "Other notes have unsaved changes that could not be saved, so it can't be checked whether they use this snapshot.")
            return
        self.refresh_rows()
        if not any(row.item_id == image_id and row.match_start is None for row in self._rows):
            self.app_context.get_ui_controller().show_warning_message(
                "Delete Artefact", "Another note now uses this snapshot, so it was not deleted.")
            return
        command = DeleteItemCommand(self.app_context, item_id=image_id, confirm=False)
        self.app_context.get_command_executor().execute_command(command, track_undo=True)
        self.refresh_rows()

    def _on_refresh_snapshot(self, image_id: str, *, dpi: int | None | KeepRenderDpi = KEEP_RENDER_DPI) -> None:
        note_editor = self.parent()
        if note_editor is None or not hasattr(note_editor, "refresh_chart_snapshot"):
            return
        note_editor.refresh_chart_snapshot(image_id, on_done=self._on_refresh_finished, dpi=dpi)
        self.refresh_rows()  # shows the Refresh and DPI buttons disabled while the render runs

    def _on_change_dpi(self, row: NoteArtefactRow) -> None:
        if row.item_id is None:
            return
        dialog = SnapshotDpiDialog(self.app_context, current_dpi=row.render_dpi, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_refresh_snapshot(row.item_id, dpi=dialog.get_dpi())

    def _on_refresh_finished(self) -> None:
        if isValid(self):
            self.refresh_rows()

    def _on_insert_chart_clicked(self) -> None:
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_chart_from_picker"):
            note_editor.insert_chart_from_picker()

    def _on_insert_table_clicked(self) -> None:
        note_editor = self.parent()
        if note_editor is not None and hasattr(note_editor, "insert_table_from_picker"):
            note_editor.insert_table_from_picker()
