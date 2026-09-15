"""Dialog for selecting an Image from project galleries to insert into a note."""

import os
from typing import Dict, List, Optional, Tuple, override

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.image_thumbnail_tile import build_gallery_tile_icon
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Folder, Image, ImageGallery, Item
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.qtasks import TaskScheduler
from pandaplot.services.theme.theme_manager import ThemeManager

_ICON_SIZE = QSize(24, 24)


class NoteImagePickerDialog(PDialog):
    """
    Dialog displaying all gallery images in the project, allowing the user
    to pick an image to insert into a Markdown note.
    """

    def __init__(
        self,
        app_context: AppContext,
        project,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(app_context=app_context, parent=parent)
        self.project = project
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()
        self._selected_image: Optional[Image] = None
        # Memoises decoded thumbnails by image id so re-populating the tree
        # (or a future dialog instance reusing this one) doesn't re-fetch.
        self._pixmap_cache: Dict[str, Optional[QPixmap]] = {}
        self._pending_thumbnails: List[Tuple[QTreeWidgetItem, Image]] = []
        self._initialize()
        self._populate_tree()
        self._refresh_ok_enabled()
        # Thumbnails (which may block on external file/network reads) decode
        # on a background thread via TaskScheduler instead of synchronously
        # before exec() -- a single slow/unavailable image no longer blocks
        # the UI thread at all, let alone makes the whole dialog appear hung.
        self._start_thumbnail_loading()

    @override
    def _init_ui(self):
        self.setWindowTitle("Insert Image from Gallery")
        self.resize(400, 350)
        layout = QVBoxLayout(self)

        self.empty_label = QLabel("No images found in the project gallery.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(_ICON_SIZE)
        self.tree.itemSelectionChanged.connect(self._refresh_ok_enabled)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        button_row = QHBoxLayout()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("Insert Image", role="primary", on_click=self._on_ok_clicked, enabled=False)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    @override
    def _apply_theme(self):
        pass

    def _get_tokens(self) -> dict:
        return self.app_context.get_manager(ThemeManager).get_design_tokens()

    def _load_pixmap_for_image(self, image: Image) -> Optional[QPixmap]:
        """Synchronous decode+scale, on whatever thread calls it.

        Only safe to call from the GUI thread (it builds a QPixmap). The tree
        icons instead go through the async `_start_thumbnail_loading` path,
        which decodes on a worker thread and only touches QPixmap back on the
        GUI thread -- QPixmap, unlike QImage, isn't thread-safe to create.
        """
        if image.id in self._pixmap_cache:
            return self._pixmap_cache[image.id]
        pixmap = self._load_pixmap_uncached(image)
        self._pixmap_cache[image.id] = pixmap
        return pixmap

    def _load_pixmap_uncached(self, image: Image) -> Optional[QPixmap]:
        data = self._fetch_image_bytes(image)
        if not data:
            return None
        pix = QPixmap()
        if not pix.loadFromData(data):
            return None
        return pix.scaled(
            _ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    @staticmethod
    def _fetch_image_bytes(image: Image) -> Optional[bytes]:
        """Read an Image item's raw bytes: in-memory, else source_file (local
        disk or, for a URL, a network fetch). Pure I/O -- safe to run on a
        background thread."""
        try:
            data = image.get_bytes()
            if data is None and image.source_file:
                source = image.source_file
                if source.startswith("http://") or source.startswith("https://"):
                    import requests
                    resp = requests.get(source, timeout=5)
                    resp.raise_for_status()
                    data = resp.content
                elif os.path.isfile(source):
                    with open(source, "rb") as f:
                        data = f.read()
            return data
        except Exception:
            return None

    def _tile_icon_for(self, item, *, placeholder: bool = False) -> QIcon:
        tokens = self._get_tokens()
        if isinstance(item, (ImageGallery, Folder)):
            return build_gallery_tile_icon(None, "album", selected=False, tokens=tokens, size=_ICON_SIZE)
        if isinstance(item, Image):
            if placeholder:
                # Deferred to _load_next_thumbnail; don't decode/fetch here.
                return build_gallery_tile_icon(None, "broken", selected=False, tokens=tokens, size=_ICON_SIZE)
            pix = self._load_pixmap_for_image(item)
            tile_type = "image" if pix is not None else "broken"
            return build_gallery_tile_icon(pix, tile_type, selected=False, tokens=tokens, size=_ICON_SIZE)
        return build_gallery_tile_icon(None, "broken", selected=False, tokens=tokens, size=_ICON_SIZE)

    def _start_thumbnail_loading(self) -> None:
        """Kick off a background decode for every pending thumbnail.

        Each decode runs on a TaskScheduler worker thread and returns a
        QImage (thread-safe to create off the GUI thread); the result
        callback -- which Qt delivers back on the GUI thread -- is what
        converts it to a QPixmap and sets the icon. Unlike loading every
        thumbnail synchronously before the dialog is shown, a slow or
        unavailable external image no longer blocks the UI thread at all.
        """
        pending, self._pending_thumbnails = self._pending_thumbnails, []
        for tree_item, image in pending:
            self.task_scheduler.run_task(
                task=self._decode_qimage_task,
                task_arguments={"image": image},
                on_result=lambda qimg, item=tree_item, img=image: self._on_thumbnail_decoded(item, img, qimg),
                on_error=lambda _err, item=tree_item: self._on_thumbnail_error(item),
            )

    def _decode_qimage_task(self, progress_callback, image: Image) -> Optional[QImage]:
        """Runs on a TaskScheduler worker thread; see `_start_thumbnail_loading`."""
        del progress_callback  # unused; required by the Worker call signature
        data = self._fetch_image_bytes(image)
        if not data:
            return None
        qimg = QImage()
        return qimg if qimg.loadFromData(data) else None

    def _on_thumbnail_decoded(self, tree_item: QTreeWidgetItem, image: Image, qimg: Optional[QImage]) -> None:
        pix = None
        if qimg is not None and not qimg.isNull():
            pix = QPixmap.fromImage(qimg).scaled(
                _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        self._pixmap_cache[image.id] = pix
        self._apply_thumbnail_icon(tree_item, pix)

    def _on_thumbnail_error(self, tree_item: QTreeWidgetItem) -> None:
        self._apply_thumbnail_icon(tree_item, None)

    def _apply_thumbnail_icon(self, tree_item: QTreeWidgetItem, pix: Optional[QPixmap]) -> None:
        tile_type = "image" if pix is not None else "broken"
        icon = build_gallery_tile_icon(pix, tile_type, selected=False, tokens=self._get_tokens(), size=_ICON_SIZE)
        try:
            tree_item.setIcon(0, icon)
        except RuntimeError:
            # The dialog (and its tree items) was already closed/destroyed
            # before this background decode finished; nothing to update.
            pass

    def _populate_tree(self) -> None:
        self.tree.clear()
        self._pending_thumbnails = []
        if self.project is None:
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            return

        all_items = self.project.get_all_items()
        all_images = [item for item in all_items if isinstance(item, Image)]
        if not all_images:
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.tree.setVisible(True)

        # Both kinds of collection are tree nodes here, not just galleries:
        # an ImageGallery can be created underneath an ordinary Folder, and
        # gallery names aren't required to be unique, so a gallery whose
        # Folder ancestors were dropped could become an indistinguishable
        # duplicate top-level entry (e.g. two different folders each holding
        # a gallery named "Gallery 1"). Showing the real hierarchy avoids
        # that ambiguity instead of trying to disambiguate the label text.
        collections = [item for item in all_items if isinstance(item, (ImageGallery, Folder))]
        by_id: Dict[str, QTreeWidgetItem] = {}
        items_by_id: Dict[str, Item] = {i.id: i for i in all_items}

        # First, build collection nodes (folders and galleries)
        for collection in collections:
            tree_item = QTreeWidgetItem([collection.name])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, collection.id)
            tree_item.setIcon(0, self._tile_icon_for(collection))
            by_id[collection.id] = tree_item

        # Attach nested collections to their parent collection or root tree
        for collection in collections:
            tree_item = by_id[collection.id]
            parent = items_by_id.get(collection.parent_id) if collection.parent_id else None
            if parent and parent.id in by_id:
                by_id[parent.id].addChild(tree_item)
            else:
                self.tree.addTopLevelItem(tree_item)

        # Attach image nodes
        for img in all_images:
            tree_item = QTreeWidgetItem([img.name])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, img.id)
            tree_item.setIcon(0, self._tile_icon_for(img, placeholder=True))
            self._pending_thumbnails.append((tree_item, img))
            by_id[img.id] = tree_item

            parent = items_by_id.get(img.parent_id) if img.parent_id else None
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
        self.ok_button.setEnabled(isinstance(item, Image))

    def _on_item_double_clicked(self, tree_item: QTreeWidgetItem, column: int) -> None:
        item = self._get_selected_item_object()
        if isinstance(item, Image):
            self._selected_image = item
            self.accept()

    def _on_ok_clicked(self) -> None:
        item = self._get_selected_item_object()
        if isinstance(item, Image):
            self._selected_image = item
            self.accept()

    def get_selected_image(self) -> Optional[Image]:
        """Return the selected Image model, or None if dialog was cancelled/no selection."""
        return self._selected_image
