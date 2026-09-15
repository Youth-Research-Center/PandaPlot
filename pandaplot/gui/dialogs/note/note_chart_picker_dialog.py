"""Dialog for selecting a Chart from the project to insert into a note."""

from typing import Dict, Optional, override

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Chart, Folder, Item
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

_ICON_SIZE = QSize(24, 24)


class NoteChartPickerDialog(PDialog):
    """
    Dialog displaying all charts in the project, allowing the user
    to pick a chart to insert into a Markdown note.
    """

    def __init__(
        self,
        app_context: AppContext,
        project,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.project = project
        self._selected_chart: Optional[Chart] = None
        self._initialize()
        self._populate_tree()
        self._refresh_ok_enabled()

    @override
    def _init_ui(self):
        self.setWindowTitle("Insert Chart into Note")
        self.resize(400, 350)
        layout = QVBoxLayout(self)

        self.empty_label = QLabel("No charts found in the project.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(_ICON_SIZE)
        self.tree.itemSelectionChanged.connect(self._refresh_ok_enabled)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        self.sync_checkbox = QCheckBox("Keep synced with chart")
        self.sync_checkbox.setChecked(True)
        self.sync_checkbox.setToolTip(
            "On: the note always shows this chart's current data/style.\n"
            "Off: inserts a static snapshot image that never changes again."
        )
        layout.addWidget(self.sync_checkbox)

        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("Insert Chart", role="primary", on_click=self._on_ok_clicked, enabled=False)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def _get_tokens(self) -> dict:
        return self.app_context.get_manager(ThemeManager).get_design_tokens()

    def _populate_tree(self) -> None:
        self.tree.clear()
        if self.project is None:
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            return

        all_items = self.project.get_all_items()
        all_charts = [item for item in all_items if isinstance(item, Chart)]
        if not all_charts:
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.tree.setVisible(True)

        folders = [item for item in all_items if isinstance(item, Folder)]
        by_id: Dict[str, QTreeWidgetItem] = {}
        items_by_id: Dict[str, Item] = {i.id: i for i in all_items}

        # Build folder nodes
        for folder in folders:
            tree_item = QTreeWidgetItem([folder.name])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, folder.id)
            by_id[folder.id] = tree_item

        # Attach nested folders to parent
        for folder in folders:
            tree_item = by_id[folder.id]
            parent = items_by_id.get(folder.parent_id) if folder.parent_id else None
            if parent and parent.id in by_id:
                by_id[parent.id].addChild(tree_item)
            else:
                self.tree.addTopLevelItem(tree_item)

        # Attach chart nodes
        for chart in all_charts:
            tree_item = QTreeWidgetItem([f"📈 {chart.name}"])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, chart.id)
            by_id[chart.id] = tree_item

            parent = items_by_id.get(chart.parent_id) if chart.parent_id else None
            if parent and parent.id in by_id:
                by_id[parent.id].addChild(tree_item)
            else:
                self.tree.addTopLevelItem(tree_item)

        self.tree.expandAll()

    def _get_selected_item_object(self) -> Optional[object]:
        selected = self.tree.selectedItems()
        if not selected or self.project is None:
            return None
        item_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        return self.project.find_item(item_id)

    def _refresh_ok_enabled(self) -> None:
        item = self._get_selected_item_object()
        self.ok_button.setEnabled(isinstance(item, Chart))

    def _on_item_double_clicked(self, tree_item: QTreeWidgetItem, column: int) -> None:
        item = self._get_selected_item_object()
        if isinstance(item, Chart):
            self._selected_chart = item
            self.accept()

    def _on_ok_clicked(self) -> None:
        item = self._get_selected_item_object()
        if isinstance(item, Chart):
            self._selected_chart = item
            self.accept()

    def get_selected_chart(self) -> Optional[Chart]:
        """Return the selected Chart model, or None if dialog was cancelled/no selection."""
        return self._selected_chart

    def get_sync_mode(self) -> bool:
        """True (default) for a live chart reference that always shows the
        chart's current data/style; False for a one-time static snapshot."""
        return self.sync_checkbox.isChecked()
