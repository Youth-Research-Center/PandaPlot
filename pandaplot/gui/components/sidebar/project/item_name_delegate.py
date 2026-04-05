from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit,
    QStyledItemDelegate,
)


class ItemNameDelegate(QStyledItemDelegate):
    """Custom delegate to handle editing only the name portion of tree items, not the icon."""

    @override
    def createEditor(self, parent, option, index):
        """Create editor that only shows the name part."""
        editor = QLineEdit(parent)

        # Get the full text and extract just the name part
        full_text = index.data(Qt.ItemDataRole.DisplayRole)
        if isinstance(full_text, str):
            # Remove emoji prefix
            if full_text.startswith("📁 "):
                name_only = full_text[2:].strip()
            elif full_text.startswith("📝 "):
                name_only = full_text[2:].strip()
            elif full_text.startswith("📊 "):
                name_only = full_text[2:].strip()
            elif full_text.startswith("📈 "):
                name_only = full_text[2:].strip()
            else:
                name_only = full_text.strip()

            editor.setText(name_only)
            editor.selectAll()

        return editor

    @override
    def setEditorData(self, editor, index):
        """Set the editor data to just the name portion."""
        # This is handled in createEditor
        pass

    @override
    def setModelData(self, editor, model, index):
        """Set the model data with the icon prefix preserved."""
        new_name = editor.text().strip()
        if new_name:
            # Get the current full text to determine the icon
            full_text = index.data(Qt.ItemDataRole.DisplayRole)
            if isinstance(full_text, str):
                # Preserve the emoji prefix
                if full_text.startswith("📁 "):
                    new_full_text = f"📁 {new_name}"
                elif full_text.startswith("📝 "):
                    new_full_text = f"📝 {new_name}"
                elif full_text.startswith("📊 "):
                    new_full_text = f"📊 {new_name}"
                elif full_text.startswith("📈 "):
                    new_full_text = f"📈 {new_name}"
                else:
                    new_full_text = new_name

                model.setData(index, new_full_text,
                              Qt.ItemDataRole.DisplayRole)
