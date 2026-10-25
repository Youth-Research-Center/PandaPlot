"""Dialog for picking a destination ImageGallery/album from a project-wide tree."""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import ImageGallery
from pandaplot.models.state.app_context import AppContext


class GalleryDestinationPickerDialog(PDialog):
    """
    Dialog showing every ImageGallery (and nested album) in the project as
    a tree, for choosing a Move/Copy destination.
    """

    def __init__(self, app_context: AppContext, project, current_gallery_id: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self.project = project
        self.current_gallery_id = current_gallery_id
        self._initialize()
        self._populate_tree()
        if current_gallery_id is not None:
            self._select_gallery(current_gallery_id)
        self._refresh_ok_enabled()

    @override
    def _init_ui(self):
        self.setWindowTitle("Choose Destination")
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self._refresh_ok_enabled)
        layout.addWidget(self.tree)

        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("OK", role="primary", on_click=self.accept, enabled=False)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def _populate_tree(self) -> None:
        self.tree.clear()
        galleries = [item for item in self.project.get_all_items() if isinstance(item, ImageGallery)]
        by_id: dict[str, ImageGallery] = {gallery.id: gallery for gallery in galleries}
        tree_items: dict[str, QTreeWidgetItem] = {}

        def _tree_item_for(gallery: ImageGallery) -> QTreeWidgetItem:
            if gallery.id in tree_items:
                return tree_items[gallery.id]
            item = QTreeWidgetItem([gallery.name])
            item.setData(0, Qt.ItemDataRole.UserRole, gallery.id)
            tree_items[gallery.id] = item
            parent_gallery = by_id.get(gallery.parent_id)
            if parent_gallery is not None:
                _tree_item_for(parent_gallery).addChild(item)
            else:
                self.tree.addTopLevelItem(item)
            return item

        for gallery in galleries:
            _tree_item_for(gallery)
        self.tree.expandAll()

    def _select_gallery(self, gallery_id: str) -> None:
        iterator_stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while iterator_stack:
            item = iterator_stack.pop()
            if item.data(0, Qt.ItemDataRole.UserRole) == gallery_id:
                item.setSelected(True)
                self.tree.scrollToItem(item)
                return
            iterator_stack.extend(item.child(i) for i in range(item.childCount()))

    def _refresh_ok_enabled(self) -> None:
        self.ok_button.setEnabled(bool(self.tree.selectedItems()))

    def get_selected_gallery_id(self) -> str | None:
        """Return the id of the selected gallery/album, or None if nothing is selected."""
        selected = self.tree.selectedItems()
        if not selected:
            return None
        return selected[0].data(0, Qt.ItemDataRole.UserRole)
