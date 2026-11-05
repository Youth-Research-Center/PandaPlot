from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit,
    QStyledItemDelegate,
)

from pandaplot.utils.item_labels import item_label, strip_item_prefix


class ItemNameDelegate(QStyledItemDelegate):
    """Custom delegate to handle editing only the name portion of tree items, not the icon."""

    @override
    def createEditor(self, parent, option, index):
        """Create editor that only shows the name part."""
        editor = QLineEdit(parent)

        # Get the full text and extract just the name part
        full_text = index.data(Qt.ItemDataRole.DisplayRole)
        if isinstance(full_text, str):
            editor.setText(strip_item_prefix(full_text))
            editor.selectAll()

        return editor

    @override
    def setEditorData(self, editor, index):
        """Set the editor data to just the name portion."""
        # This is handled in createEditor

    @override
    def setModelData(self, editor, model, index):
        """Set the model data with the icon prefix preserved."""
        new_name = editor.text().strip()
        if new_name:
            item_data = index.data(Qt.ItemDataRole.UserRole)
            item_type = item_data.get("type", "") if isinstance(item_data, dict) else ""
            model.setData(index, item_label(item_type, new_name), Qt.ItemDataRole.DisplayRole)
