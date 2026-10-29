"""Group header rows shared by every grouped list (the New Chart wizard's
type list and GroupedValueComboBox's popup).

A header is a disabled row with no value. Arrow keys already skip disabled
rows, but Home, End and PageUp/PageDown target a fixed row; when that row is
a header, Qt refuses the move and the highlight doesn't change at all. The
list views here step on to the nearest enabled row instead.
"""
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem


def configure_group_header(item: QListWidgetItem | QStandardItem, title: str) -> None:
    """Make `item` a group header: not selectable or enabled, bold, and
    described to assistive technology as the start of the `title` group."""
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    font = item.font()
    font.setBold(True)
    item.setFont(font)
    description = f"{title} group"
    # The two item classes take setData's arguments in opposite order.
    if isinstance(item, QStandardItem):
        item.setData(description, Qt.ItemDataRole.AccessibleDescriptionRole)
    else:
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, description)


def _skip_headers(view: QAbstractItemView, index: QModelIndex) -> QModelIndex:
    """`index`, or the nearest enabled row after it (then before it) when it
    is a header. Falls back to the view's current index so a cursor move
    never lands on a header."""
    if not index.isValid() or index.flags() & Qt.ItemFlag.ItemIsEnabled:
        return index
    model = view.model()
    rows = model.rowCount(index.parent())
    for row in [*range(index.row() + 1, rows), *range(index.row() - 1, -1, -1)]:
        candidate = model.index(row, index.column(), index.parent())
        if candidate.flags() & Qt.ItemFlag.ItemIsEnabled:
            return candidate
    return view.currentIndex()


class GroupedListView(QListView):
    """QListView whose cursor moves never stop on a group header."""

    def moveCursor(self, cursorAction: QAbstractItemView.CursorAction, modifiers: Qt.KeyboardModifier) -> QModelIndex:
        return _skip_headers(self, super().moveCursor(cursorAction, modifiers))


class GroupedListWidget(QListWidget):
    """QListWidget whose cursor moves never stop on a group header."""

    def moveCursor(self, cursorAction: QAbstractItemView.CursorAction, modifiers: Qt.KeyboardModifier) -> QModelIndex:
        return _skip_headers(self, super().moveCursor(cursorAction, modifiers))
