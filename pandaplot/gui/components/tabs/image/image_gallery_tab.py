"""
Grid-view tab for browsing an ImageGallery: thumbnails for Image children,
folder-style tiles for nested ImageGallery children (albums), with
multi-select rename/delete/group-into-album and a double-click lightbox.
"""

from typing import Optional, override

from PySide6.QtCore import QMimeData, QSize, Qt
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.image import CreateImageGalleryCommand, ImportImagesCommand
from pandaplot.commands.project.item import DeleteItemCommand, MoveItemCommand, RenameItemCommand
from pandaplot.gui.components.common.image_thumbnail_tile import build_gallery_tile_icon
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.gui.components.tabs.image.image_lightbox_dialog import ImageLightboxDialog
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Image, ImageGallery
from pandaplot.models.state.app_context import AppContext

_TILE_SIZE = QSize(120, 120)

_IMAGE_MIME_TYPE = "application/x-pandaplot-image-ids"

# Fixed pixel width used to elide the Name column in list view. A
# fixed-width elision is acceptable for this pass rather than measuring the
# actual column width at render time.
_LIST_NAME_COLUMN_ELIDE_WIDTH = 200


class _ImageGalleryGrid(QListWidget):
    """
    QListWidget with custom drag-and-drop: dragging selected tiles produces
    a MIME payload of their ids (_IMAGE_MIME_TYPE); dropping that payload
    onto an ImageGallery (album) tile moves the dragged images into it via
    the owning ImageGalleryTab's move handler. Dropping onto anything else
    (an image tile, empty space) is a no-op.
    """

    def __init__(self, tab: "ImageGalleryTab"):
        super().__init__()
        self._tab = tab
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragDrop)

    def startDrag(self, supportedActions):  # noqa: N802 - Qt override
        selected_ids = self._tab._selected_ids()
        if not selected_ids:
            return
        mime = QMimeData()
        mime.setData(_IMAGE_MIME_TYPE, "\n".join(selected_ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 - Qt override
        target_item = self.itemAt(event.position().toPoint())
        if target_item is None or not event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.ignore()
            return
        self._handle_drop_on_item(target_item, event.mimeData())
        event.acceptProposedAction()

    def _handle_drop_on_item(self, target_item: QListWidgetItem, mime: QMimeData) -> None:
        """Testable core of dropEvent: given the drop target tile and the
        dragged MIME data, moves the dragged images into the target if
        it's an album, no-ops otherwise."""
        target_id = target_item.data(Qt.ItemDataRole.UserRole)
        target_child = self._tab.current_gallery.get_item_by_id(target_id)
        if not isinstance(target_child, ImageGallery):
            return

        raw = bytes(mime.data(_IMAGE_MIME_TYPE)).decode("utf-8")
        image_ids = [line for line in raw.split("\n") if line]
        self._tab._move_images_to(image_ids, target_child.id)


class _BreadcrumbSegmentButton(PButton):
    """PButton breadcrumb segment that also accepts a drop of dragged image
    ids, moving them into this segment's gallery."""

    def __init__(self, gallery: ImageGallery, tab: "ImageGalleryTab", **kwargs):
        super().__init__(**kwargs)
        self._gallery = gallery
        self._tab = tab
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 - Qt override
        if event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 - Qt override
        if not event.mimeData().hasFormat(_IMAGE_MIME_TYPE):
            event.ignore()
            return
        self._handle_breadcrumb_drop(event.mimeData())
        event.acceptProposedAction()

    def _handle_breadcrumb_drop(self, mime: QMimeData) -> None:
        raw = bytes(mime.data(_IMAGE_MIME_TYPE)).decode("utf-8")
        image_ids = [line for line in raw.split("\n") if line]
        self._tab._move_images_to(image_ids, self._gallery.id)


class ImageGalleryTab(PWidget):
    """Thumbnail-grid tab for browsing and managing one ImageGallery's contents."""

    def __init__(self, app_context: AppContext, gallery: ImageGallery, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.root_gallery = gallery
        self.current_gallery = gallery
        # Browser-style single history list + pointer. Navigating (breadcrumb
        # click or album double-click) truncates anything past the pointer
        # before appending, then moves the pointer to the new entry.
        self._history: list[str] = [gallery.id]
        self._history_index: int = 0
        # Session-lifetime cache of already-loaded/scaled thumbnails, keyed by
        # image id. A cached value of None means "failed to load this
        # session, don't retry" -- this avoids re-downloading external URL
        # images (or re-decoding bytes) on every grid repopulation, which
        # otherwise happens on every PROJECT_ITEM_ADDED/REMOVED/RENAMED/MOVED
        # event anywhere in the project.
        self._thumbnail_cache: dict[str, Optional[QPixmap]] = {}
        # Ids of the CURRENT gallery's children as of the last successful
        # _populate_grid() call. Some PROJECT_ITEM_REMOVED events (e.g.
        # undo of an import or of a gallery creation) fire *after* the item
        # has already been removed from self.current_gallery, carrying only
        # the removed item's own id and no parent_id -- so matching against
        # current children alone would miss them. Keeping this snapshot
        # lets _event_concerns_this_gallery still recognize such ids as
        # "was ours as of last populate". Reset whenever current_gallery
        # changes (a stale snapshot from a different gallery level must not
        # leak into this one's filter).
        self._last_child_ids: set[str] = set()
        self._sort_field: str = "name"
        self._sort_ascending: bool = True
        self._initialize()
        self._rebuild_breadcrumb()
        self._populate_grid()
        self.setup_connections()

    @override
    def _init_ui(self):
        layout = QVBoxLayout(self)

        breadcrumb_row = QHBoxLayout()
        self.back_button = PButton("◀", on_click=self._go_back, enabled=False)
        self.forward_button = PButton("▶", on_click=self._go_forward, enabled=False)
        self.breadcrumb_row_layout = QHBoxLayout()
        breadcrumb_row.addWidget(self.back_button)
        breadcrumb_row.addWidget(self.forward_button)
        breadcrumb_row.addLayout(self.breadcrumb_row_layout)
        breadcrumb_row.addStretch()
        self.view_toggle = SegmentedControl([("Grid", "grid"), ("List", "list")])
        self.view_toggle.currentValueChanged.connect(self._on_view_mode_changed)
        breadcrumb_row.addWidget(self.view_toggle)
        layout.addLayout(breadcrumb_row)

        toolbar = QHBoxLayout()
        self.import_button = PButton("Import Images...", on_click=self._on_import_clicked)
        self.rename_button = PButton("Rename", on_click=self._on_rename_clicked, enabled=False)
        self.delete_button = PButton("Delete", role="destructive", on_click=self._on_delete_clicked, enabled=False)
        self.group_into_album_button = PButton("Group into Album", on_click=self._on_group_into_album_clicked, enabled=False)
        self.move_button = PButton("Move...", on_click=self._on_move_clicked, enabled=False)
        self.copy_button = PButton("Copy to...", on_click=self._on_copy_clicked, enabled=False)
        for button in (
            self.import_button, self.rename_button, self.delete_button,
            self.group_into_album_button, self.move_button, self.copy_button,
        ):
            toolbar.addWidget(button)

        from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox

        self.sort_field_combo = DropDownComboBox()
        self._sort_field_values = ["name", "type", "dimensions", "size", "modified"]
        self.sort_field_combo.addItems(["Name", "Type", "Dimensions", "Size", "Date Modified"])
        self.sort_field_combo.currentIndexChanged.connect(
            lambda index: self._on_sort_field_changed(self._sort_field_values[index])
        )
        toolbar.addWidget(self.sort_field_combo)

        self.sort_direction_button = PButton("▲", on_click=self._on_sort_direction_toggled)
        toolbar.addWidget(self.sort_direction_button)

        layout.addLayout(toolbar)

        self.grid = _ImageGalleryGrid(self)
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(_TILE_SIZE)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.list_view = QTreeWidget()
        self.list_view.setHeaderLabels(["Name", "Type", "Dimensions", "Size", "Date Modified"])
        self.list_view.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        # Deliberately NOT setSortingEnabled(True): that would make Qt
        # natively re-sort rows on every insertion/toggle using
        # QTreeWidgetItem's own text-based column comparison, which
        # discards _sorted_children()'s numeric/canonical order (see
        # _populate_list_view). We only want the header's clickable
        # sort-indicator behavior, which is independent of the
        # sortingEnabled flag.
        self.list_view.header().setSectionsClickable(True)
        self.list_view.header().setSortIndicatorShown(True)
        self.list_view.header().sortIndicatorChanged.connect(self._on_list_header_sort_changed)
        self.list_view.itemDoubleClicked.connect(self._on_list_item_double_clicked)

        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.grid)
        self.view_stack.addWidget(self.list_view)
        layout.addWidget(self.view_stack)

        self.grid.itemSelectionChanged.connect(self._on_selection_changed)
        self.grid.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._on_grid_context_menu)

        self.list_view.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self._on_list_context_menu)

    @override
    def _apply_theme(self):
        if hasattr(self, "grid"):
            self._refresh_tile_icons()

    def setup_connections(self):
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_ADDED, self._on_project_item_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_REMOVED, self._on_project_item_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self._on_project_item_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_MOVED, self._on_project_item_changed)

    def get_tab_title(self) -> str:
        return self.root_gallery.name

    def _navigate_to(self, gallery: ImageGallery) -> None:
        """Drill into (or jump to) `gallery` within this same tab, pushing
        onto history and truncating any stale forward branch."""
        self._history = self._history[: self._history_index + 1]
        self._history.append(gallery.id)
        self._history_index = len(self._history) - 1
        self._set_current_gallery(gallery)

    def _go_back(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._set_current_gallery_by_id(self._history[self._history_index])

    def _go_forward(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._set_current_gallery_by_id(self._history[self._history_index])

    def _set_current_gallery_by_id(self, gallery_id: str) -> None:
        found = self.root_gallery if gallery_id == self.root_gallery.id else self._find_gallery(self.root_gallery, gallery_id)
        if found is not None:
            self._set_current_gallery(found)

    def _find_gallery(self, root: ImageGallery, gallery_id: str) -> Optional[ImageGallery]:
        for child in root.get_items():
            if isinstance(child, ImageGallery):
                if child.id == gallery_id:
                    return child
                found = self._find_gallery(child, gallery_id)
                if found is not None:
                    return found
        return None

    def _set_current_gallery(self, gallery: ImageGallery) -> None:
        self.current_gallery = gallery
        self._last_child_ids = set()
        self._rebuild_breadcrumb()
        self._populate_grid()

    def _rebuild_breadcrumb(self) -> None:
        chain: list[ImageGallery] = [self.current_gallery]
        cursor = self.current_gallery
        project = self.app_state.current_project
        while cursor.id != self.root_gallery.id and project is not None:
            parent = project.find_item(cursor.parent_id) if cursor.parent_id else None
            if not isinstance(parent, ImageGallery):
                break
            chain.append(parent)
            cursor = parent
        chain.reverse()
        self._clear_breadcrumb_segments()
        last_index = len(chain) - 1
        for index, gallery in enumerate(chain):
            if index == last_index:
                segment: QWidget = QLabel(gallery.name)
            else:
                segment = _BreadcrumbSegmentButton(
                    gallery, self, text=gallery.name, role="secondary",
                    on_click=lambda _checked=False, g=gallery: self._navigate_to(g),
                )
            self.breadcrumb_row_layout.addWidget(segment)
            if index != last_index:
                self.breadcrumb_row_layout.addWidget(QLabel(" > "))
        self.back_button.setEnabled(self._history_index > 0)
        self.forward_button.setEnabled(self._history_index < len(self._history) - 1)

    def _clear_breadcrumb_segments(self) -> None:
        while self.breadcrumb_row_layout.count():
            child = self.breadcrumb_row_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_project_item_changed(self, event_data: dict):
        if self._event_concerns_this_gallery(event_data):
            self._populate_grid()

    def _event_concerns_this_gallery(self, event_data: dict) -> bool:
        """
        Best-effort filter so this tab only repopulates for events that
        actually affect its currently-displayed gallery level, rather than
        on every project item add/remove/rename/move anywhere in the
        project (event payloads vary by command, so this checks every key
        we know commands use).
        """
        for key in ("source_folder", "target_folder"):
            value = event_data.get(key)
            if value is not None and value == self.current_gallery.id:
                return True

        parent_id = event_data.get("parent_id")
        if parent_id is not None:
            return parent_id == self.current_gallery.id

        item_data = event_data.get("item_data")
        if isinstance(item_data, dict) and "parent_id" in item_data:
            return item_data.get("parent_id") == self.current_gallery.id

        candidate_ids = {
            event_data.get(key)
            for key in ("item_id", "gallery_id", "image_id")
            if event_data.get(key)
        }
        if not candidate_ids:
            # No usable identifying info at all -- fall back to repopulating,
            # since we can't safely rule the event out.
            return True
        if self.current_gallery.id in candidate_ids:
            return True
        current_child_ids = {child.id for child in self.current_gallery.get_items()}
        return bool(candidate_ids & (current_child_ids | self._last_child_ids))

    def _on_sort_field_changed(self, field: str) -> None:
        self._sort_field = field
        self._populate_grid()

    def _on_sort_direction_toggled(self) -> None:
        self._sort_ascending = not self._sort_ascending
        self.sort_direction_button.setText("▲" if self._sort_ascending else "▼")
        self._populate_grid()

    def _on_list_header_sort_changed(self, column: int, order) -> None:
        from PySide6.QtCore import Qt as _Qt

        column_to_field = {0: "name", 1: "type", 2: "dimensions", 3: "size", 4: "modified"}
        field = column_to_field.get(column)
        if field is None:
            return
        self._sort_field = field
        self._sort_ascending = order == _Qt.SortOrder.AscendingOrder
        # Block signals: setCurrentIndex would otherwise emit
        # currentIndexChanged -> _on_sort_field_changed -> a redundant
        # _populate_grid() call, on top of the explicit one below.
        self.sort_field_combo.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
        self.sort_field_combo.setCurrentIndex(self._sort_field_values.index(field))
        self.sort_field_combo.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
        self.sort_direction_button.setText("▲" if self._sort_ascending else "▼")
        self._populate_grid()

    def _sorted_children(self) -> list:
        children = list(self.current_gallery.get_items())

        def _key(child):
            if self._sort_field == "name":
                return child.name.lower()
            if self._sort_field == "type":
                return (isinstance(child, ImageGallery), child.name.lower())
            if self._sort_field == "dimensions":
                if isinstance(child, Image):
                    return (child.width, child.height)
                return (0, 0)
            if self._sort_field == "size":
                if isinstance(child, Image):
                    return child.size_bytes if child.size_bytes is not None else -1
                return -1
            if self._sort_field == "modified":
                return child.modified_at
            return child.name.lower()

        children.sort(key=_key, reverse=not self._sort_ascending)
        return children

    def _elided_text(self, text: str, max_width: int) -> str:
        from PySide6.QtGui import QFontMetrics

        metrics = QFontMetrics(self.font())
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)

    def _populate_grid(self):
        self.grid.clear()
        tokens = self._current_tokens()
        for child in self._sorted_children():
            item = QListWidgetItem(self._elided_text(child.name, _TILE_SIZE.width() - 8))
            item.setToolTip(child.name)
            item.setData(Qt.ItemDataRole.UserRole, child.id)
            item.setIcon(self._tile_icon_for(child, is_selected=False, tokens=tokens))
            self.grid.addItem(item)
        self._last_child_ids = {child.id for child in self.current_gallery.get_items()}
        self._refresh_toolbar_state()
        if hasattr(self, "view_stack") and self.view_stack.currentWidget() is self.list_view:
            self._populate_list_view()

    def _current_tokens(self) -> dict:
        from pandaplot.services.theme.theme_manager import ThemeManager

        return self.app_context.get_manager(ThemeManager).get_design_tokens()

    def _thumbnail_for(self, image: Image) -> Optional[QPixmap]:
        """Load (or fetch) image bytes and downscale in memory; None on any failure.

        Results (including failures) are cached for the tab's lifetime, keyed
        by image id, so external URL images in particular are not
        re-downloaded on every grid repopulation within the same session.
        """
        if image.id in self._thumbnail_cache:
            return self._thumbnail_cache[image.id]

        try:
            data = image.get_bytes()
            if data is None and image.storage_mode == "external":
                data = self._load_external_bytes(image.source_file)
            if data is None:
                raise ValueError("no image data")

            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                raise ValueError("could not decode image data")
            scaled = pixmap.scaled(_TILE_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._thumbnail_cache[image.id] = scaled
            return scaled
        except Exception:
            self.logger.warning("Failed to load thumbnail for image '%s' (id=%s)", image.name, image.id)
            self._thumbnail_cache[image.id] = None
            return None

    def _load_external_bytes(self, source_file: str) -> Optional[bytes]:
        import os

        if source_file.startswith("http://") or source_file.startswith("https://"):
            import requests
            response = requests.get(source_file, timeout=10)
            response.raise_for_status()
            return response.content

        if os.path.isfile(source_file):
            with open(source_file, "rb") as f:
                return f.read()
        return None

    def _tile_icon_for(self, child, *, is_selected: bool, tokens: dict, size: QSize = _TILE_SIZE):
        """Build the themed tile icon for a gallery child (album/image/broken-image)."""
        if isinstance(child, ImageGallery):
            return build_gallery_tile_icon(
                None, "album", selected=is_selected, tokens=tokens, size=size
            )
        if isinstance(child, Image):
            thumbnail = self._thumbnail_for(child)
            if thumbnail is not None and (thumbnail.width() > size.width() or thumbnail.height() > size.height()):
                thumbnail = thumbnail.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            tile_type = "image" if thumbnail is not None else "broken"
            return build_gallery_tile_icon(
                thumbnail, tile_type, selected=is_selected, tokens=tokens, size=size
            )
        return build_gallery_tile_icon(None, "broken", selected=is_selected, tokens=tokens, size=size)

    def _active_view_widget(self):
        """The currently-visible of grid/list_view (falls back to grid before
        view_stack exists, e.g. during construction)."""
        if hasattr(self, "view_stack"):
            return self.view_stack.currentWidget()
        return self.grid

    def _selected_ids(self) -> list[str]:
        widget = self._active_view_widget()
        if widget is getattr(self, "list_view", None):
            return [item.data(0, Qt.ItemDataRole.UserRole) for item in self.list_view.selectedItems()]
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.grid.selectedItems()]

    def _selected_children(self):
        selected_ids = set(self._selected_ids())
        return [child for child in self.current_gallery.get_items() if child.id in selected_ids]

    def _refresh_toolbar_state(self):
        selected = self._selected_children()
        has_image = any(isinstance(c, Image) for c in selected)
        self.rename_button.setEnabled(len(selected) == 1)
        self.delete_button.setEnabled(len(selected) >= 1)
        self.move_button.setEnabled(has_image)
        self.copy_button.setEnabled(has_image)
        self.group_into_album_button.setEnabled(
            len(selected) >= 2 and all(isinstance(c, Image) for c in selected)
        )

    def _on_selection_changed(self):
        self._refresh_toolbar_state()
        self._refresh_tile_icons()

    def _refresh_tile_icons(self) -> None:
        tokens = self._current_tokens()
        selected_ids = set(self._selected_ids())
        for i in range(self.grid.count()):
            item = self.grid.item(i)
            child_id = item.data(Qt.ItemDataRole.UserRole)
            child = self.current_gallery.get_item_by_id(child_id)
            if child is None:
                continue
            is_selected = child_id in selected_ids
            item.setIcon(self._tile_icon_for(child, is_selected=is_selected, tokens=tokens))
        if hasattr(self, "list_view"):
            for i in range(self.list_view.topLevelItemCount()):
                row = self.list_view.topLevelItem(i)
                child_id = row.data(0, Qt.ItemDataRole.UserRole)
                child = self.current_gallery.get_item_by_id(child_id)
                if child is None:
                    continue
                row.setIcon(0, self._tile_icon_for(child, is_selected=False, tokens=tokens, size=QSize(16, 16)))

    def _on_grid_context_menu(self, position) -> None:
        item = self.grid.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.grid.clearSelection()
            item.setSelected(True)
        menu = self._build_context_menu(item)
        menu.exec(self.grid.viewport().mapToGlobal(position))

    def _on_list_context_menu(self, position) -> None:
        item = self.list_view.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.list_view.clearSelection()
            item.setSelected(True)
        menu = self._build_context_menu(item)
        menu.exec(self.list_view.viewport().mapToGlobal(position))

    def _child_id_for_item(self, item) -> str:
        """Read the stored child id from either a grid tile (QListWidgetItem)
        or a list-view row (QTreeWidgetItem, id stored on column 0)."""
        if isinstance(item, QTreeWidgetItem):
            return item.data(0, Qt.ItemDataRole.UserRole)
        return item.data(Qt.ItemDataRole.UserRole)

    def _build_context_menu(self, item):
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        selected = self._selected_children()
        has_image = any(isinstance(c, Image) for c in selected)

        rename_action = QAction("Rename", self)
        rename_action.setEnabled(len(selected) == 1)
        rename_action.triggered.connect(self._on_rename_clicked)
        menu.addAction(rename_action)

        delete_action = QAction("Delete", self)
        delete_action.setEnabled(len(selected) >= 1)
        delete_action.triggered.connect(self._on_delete_clicked)
        menu.addAction(delete_action)

        move_action = QAction("Move...", self)
        move_action.setEnabled(has_image)
        move_action.triggered.connect(self._on_move_clicked)
        menu.addAction(move_action)

        copy_action = QAction("Copy to...", self)
        copy_action.setEnabled(has_image)
        copy_action.triggered.connect(self._on_copy_clicked)
        menu.addAction(copy_action)

        child_id = self._child_id_for_item(item)
        child = self.current_gallery.get_item_by_id(child_id)
        if isinstance(child, ImageGallery) and len(selected) == 1:
            menu.addSeparator()
            open_new_tab_action = QAction("Open in New Tab", self)
            open_new_tab_action.triggered.connect(lambda: self._open_in_new_tab(child))
            menu.addAction(open_new_tab_action)

        return menu

    def _open_in_new_tab(self, gallery: ImageGallery) -> None:
        from pandaplot.models.events.event_data import TabOpenRequestedData
        from pandaplot.models.events.event_types import UIEvents

        self.app_state.event_bus.emit(UIEvents.TAB_OPEN_REQUESTED, TabOpenRequestedData(
            item_id=gallery.id, item_name=gallery.name
        ).to_dict())

    def _on_import_clicked(self):
        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.image.image_import_dialog import ImageImportDialog

        dialog = ImageImportDialog(self.app_context, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        command = ImportImagesCommand(
            self.app_context, gallery_id=self.current_gallery.id,
            sources=dialog.get_sources(), copy_into_project=dialog.get_copy_into_project(),
        )
        self.app_context.get_command_executor().execute_command(command)

    def _on_rename_clicked(self):
        selected = self._selected_children()
        if len(selected) != 1:
            return
        item = selected[0]
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=item.name)
        if not ok or not new_name.strip():
            return
        command = RenameItemCommand(self.app_context, item_id=item.id, new_name=new_name.strip())
        self.app_context.get_command_executor().execute_command(command)

    def _on_delete_clicked(self):
        selected = self._selected_children()
        if not selected:
            return
        names = ", ".join(c.name for c in selected)
        confirmed = QMessageBox.question(
            self, "Delete", f"Delete {len(selected)} item(s)? ({names})"
        ) == QMessageBox.StandardButton.Yes
        if not confirmed:
            return
        for item in selected:
            command = DeleteItemCommand(self.app_context, item_id=item.id, confirm=False)
            self.app_context.get_command_executor().execute_command(command)

    def _on_move_clicked(self) -> None:
        selected = [c for c in self._selected_children() if isinstance(c, Image)]
        if not selected:
            return

        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.image.gallery_destination_picker_dialog import (
            GalleryDestinationPickerDialog,
        )

        dialog = GalleryDestinationPickerDialog(
            self.app_context, self.app_state.current_project,
            current_gallery_id=self.current_gallery.id, parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target_gallery_id = dialog.get_selected_gallery_id()
        if target_gallery_id is None:
            return

        self._move_images_to([image.id for image in selected], target_gallery_id)

    def _move_images_to(self, image_ids: list[str], target_gallery_id: str) -> None:
        """Move each image (by id) from this tab's current gallery into target_gallery_id.

        Guards against data loss: an id is only ever moved if it is not the
        target itself (never move an item into itself) and it resolves to an
        Image instance (albums are never a valid drag/move payload here --
        moving an ImageGallery through MoveItemCommand would recursively
        strip and delete its descendants from the project index)."""
        for image_id in image_ids:
            if image_id == target_gallery_id:
                continue
            child = self.current_gallery.get_item_by_id(image_id)
            if not isinstance(child, Image):
                continue
            move_command = MoveItemCommand(
                self.app_context, item_id=image_id, item_type="image",
                source_folder_id=self.current_gallery.id, target_folder_id=target_gallery_id,
            )
            self.app_context.get_command_executor().execute_command(move_command)

    def _on_copy_clicked(self) -> None:
        selected = [c for c in self._selected_children() if isinstance(c, Image)]
        if not selected:
            return

        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.image.gallery_destination_picker_dialog import (
            GalleryDestinationPickerDialog,
        )

        dialog = GalleryDestinationPickerDialog(
            self.app_context, self.app_state.current_project,
            current_gallery_id=self.current_gallery.id, parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target_gallery_id = dialog.get_selected_gallery_id()
        if target_gallery_id is None:
            return

        from pandaplot.commands.project.image import CopyImagesCommand

        copy_command = CopyImagesCommand(
            self.app_context, image_ids=[image.id for image in selected], target_gallery_id=target_gallery_id,
        )
        self.app_context.get_command_executor().execute_command(copy_command)

    def _on_group_into_album_clicked(self):
        selected = [c for c in self._selected_children() if isinstance(c, Image)]
        if len(selected) < 2:
            return
        album_name, ok = QInputDialog.getText(self, "Group into Album", "Album name:")
        if not ok or not album_name.strip():
            return

        create_command = CreateImageGalleryCommand(
            self.app_context, gallery_name=album_name.strip(), parent_id=self.current_gallery.id
        )
        self.app_context.get_command_executor().execute_command(create_command)
        album_id = create_command.created_gallery_id
        if album_id is None:
            return

        self._move_images_to([image.id for image in selected], album_id)

    def _on_item_double_clicked(self, list_item: QListWidgetItem):
        child_id = list_item.data(Qt.ItemDataRole.UserRole)
        child = self.current_gallery.get_item_by_id(child_id)
        if child is None:
            return

        if isinstance(child, ImageGallery):
            self._navigate_to(child)
        elif isinstance(child, Image):
            self._open_lightbox_for(child)

    def _open_lightbox_for(self, image: Image) -> None:
        images = [c for c in self.current_gallery.get_items() if isinstance(c, Image)]
        if image not in images:
            return
        start_index = images.index(image)

        def _load(img: Image) -> Optional[QPixmap]:
            pixmap = QPixmap()
            data = img.get_bytes() or self._load_external_bytes(img.source_file)
            if data and pixmap.loadFromData(data):
                return pixmap
            return None

        ImageLightboxDialog(images, start_index, load_pixmap=_load, parent=self).exec()

    def _on_view_mode_changed(self, mode: str) -> None:
        # Switching views is a scope simplification that resets selection
        # entirely, rather than trying to sync selection between the two
        # widgets -- so the toolbar is correctly disabled immediately after
        # a switch, and stale selection in the hidden widget can never be
        # acted on by the toolbar/context menu.
        self.grid.clearSelection()
        self.list_view.clearSelection()
        if mode == "list":
            self._populate_list_view()
            self.view_stack.setCurrentWidget(self.list_view)
        else:
            self.view_stack.setCurrentWidget(self.grid)
        self._refresh_toolbar_state()

    _SORT_FIELD_TO_COLUMN = {"name": 0, "type": 1, "dimensions": 2, "size": 3, "modified": 4}

    def _populate_list_view(self) -> None:
        # setSortingEnabled is never turned on for self.list_view (see
        # _init_ui) -- native QTreeWidget sorting compares displayed
        # Qt::DisplayRole text (QTreeWidgetItem::operator<), which gives
        # wrong results for several of our columns (e.g. "10 B" < "2.4 MB"
        # lexically, or "Album" before "Image" for type), scrambling the
        # shared _sorted_children() order that both grid and list view are
        # supposed to agree on. So rows are simply inserted in
        # _sorted_children()'s order below, and the header's indicator is
        # resynced to the current shared sort field (signals blocked so
        # this doesn't loop back into _on_list_header_sort_changed) purely
        # to keep the header's arrow glyph accurate for the next genuine
        # user click.
        header = self.list_view.header()
        self.list_view.clear()
        tokens = self._current_tokens()
        for child in self._sorted_children():
            if isinstance(child, ImageGallery):
                dimensions, size_text = "", ""
                type_text = "Album"
            else:
                dimensions = f"{child.width}×{child.height}"
                size_text = self._format_size(child.size_bytes)
                type_text = "Image"
            row = QTreeWidgetItem([
                self._elided_text(child.name, _LIST_NAME_COLUMN_ELIDE_WIDTH),
                type_text, dimensions, size_text, child.modified_at,
            ])
            row.setToolTip(0, child.name)
            row.setData(0, Qt.ItemDataRole.UserRole, child.id)
            row.setIcon(0, self._tile_icon_for(child, is_selected=False, tokens=tokens, size=QSize(16, 16)))
            self.list_view.addTopLevelItem(row)

        header.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
        column = self._SORT_FIELD_TO_COLUMN.get(self._sort_field, 0)
        order = Qt.SortOrder.AscendingOrder if self._sort_ascending else Qt.SortOrder.DescendingOrder
        header.setSortIndicator(column, order)
        header.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args

    def _format_size(self, size_bytes: Optional[int]) -> str:
        if size_bytes is None:
            return "—"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _on_list_item_double_clicked(self, tree_item: QTreeWidgetItem, column: int) -> None:
        child_id = tree_item.data(0, Qt.ItemDataRole.UserRole)
        child = self.current_gallery.get_item_by_id(child_id)
        if child is None:
            return
        if isinstance(child, ImageGallery):
            self._navigate_to(child)
        elif isinstance(child, Image):
            self._open_lightbox_for(child)
