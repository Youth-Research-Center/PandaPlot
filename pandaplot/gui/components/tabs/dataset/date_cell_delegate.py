"""Text entry and calendar selection for pandas datetime cells."""

from typing import override

import pandas as pd
from PySide6.QtCore import QAbstractItemModel, QDate, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.utils.datetime import parse_timestamp_or_nat


class DateCellEditor(QWidget):
    commitRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.text = QLineEdit(self)
        self.text.setPlaceholderText("YYYY-MM-DD (blank clears)")
        self.button = QToolButton(self)
        self.button.setText("...")
        self.button.setAccessibleName("Choose date")
        self.button.setToolTip("Pick a date; keep the existing time and timezone")
        self.button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.text)
        layout.addWidget(self.button)
        self.setFocusProxy(self.text)
        self.text.returnPressed.connect(self.commitRequested.emit)
        self.button.clicked.connect(self.open_calendar)
        self.calendar_dialog: QDialog | None = None

    def open_calendar(self) -> None:
        if self.calendar_dialog is not None:
            self.calendar_dialog.close()
            self.calendar_dialog.deleteLater()
        popup = QDialog(self, Qt.WindowType.Popup)
        calendar = QCalendarWidget(popup)
        value = parse_timestamp_or_nat(self.text.text())
        if not pd.isna(value):
            calendar.setSelectedDate(QDate(value.year, value.month, value.day))
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(calendar)
        calendar.clicked.connect(lambda date: self.select_date(date, popup))
        calendar.activated.connect(lambda date: self.select_date(date, popup))
        self.calendar_dialog = popup
        popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        popup.show()

    def select_date(self, date: QDate, popup: QDialog) -> None:
        # Change only the date portion, preserving local time and fractional
        # seconds. The model resolves the column timezone/DST on commit.
        current = self.text.text().strip()
        value = parse_timestamp_or_nat(current)
        if not pd.isna(value) and value.tzinfo is not None:
            value = value.tz_localize(None)
        suffix = str(value)[10:] if not pd.isna(value) else ""
        self.text.setText(date.toString("yyyy-MM-dd") + suffix)
        popup.close()
        self.text.setFocus()
        self.commitRequested.emit()


class DateCellDelegate(QStyledItemDelegate):
    @override
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        model = index.model()
        dtype = model.column_dtype(index.column())
        if not pd.api.types.is_datetime64_any_dtype(dtype):
            return super().createEditor(parent, option, index)
        editor = DateCellEditor(parent)
        editor.commitRequested.connect(lambda: self.commitData.emit(editor))
        return editor

    @override
    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        if not isinstance(editor, DateCellEditor):
            super().setEditorData(editor, index)
            return
        editor.text.setText(index.data(Qt.ItemDataRole.EditRole))
        timezone = getattr(index.model().column_dtype(index.column()), "tz", None)
        if timezone is not None:
            editor.text.setToolTip(f"Dates without an offset use {timezone}; blank clears the cell.")
        editor.text.selectAll()

    @override
    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex) -> None:
        if not isinstance(editor, DateCellEditor):
            super().setModelData(editor, model, index)
            return
        if model.setData(index, editor.text.text(), Qt.ItemDataRole.EditRole):
            self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
        else:
            editor.text.setToolTip("Enter a valid date/time for this column's timezone, or leave blank to clear.")
            editor.text.setFocus()
