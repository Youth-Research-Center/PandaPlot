"""Modal dialog showing one image at a time from an ordered list, with
Previous/Next navigation across the list without closing the dialog."""

from typing import Callable, List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QKeyEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from pandaplot.gui.components.common.image_thumbnail_tile import build_gallery_tile_icon
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.models.project.items import Image

_INITIAL_WIDTH = 1200
_INITIAL_HEIGHT = 900
_TITLE_ELIDE_WIDTH = 500


class ImageLightboxDialog(QDialog):
    """
    Modal full-size image preview over an ordered list of sibling Images,
    with Previous/Next buttons and Left/Right arrow keys to move between
    them without closing the dialog. Disabled (not wrapped) at either end.

    Opens at a fixed initial size so Previous/Next never move as you step
    between images of different native dimensions -- each image scales to
    fit the dialog's current content area (letterboxed via
    KeepAspectRatio). The dialog itself remains a normal, user-resizable
    QDialog (no setFixedSize); if the user manually resizes the window,
    subsequent images scale to fit the new size instead of the original
    fixed constants.
    """

    def __init__(self, images: List[Image], start_index: int,
                 load_pixmap: Callable[[Image], Optional[QPixmap]],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._images = images
        self._index = start_index
        self._load_pixmap = load_pixmap

        self.resize(_INITIAL_WIDTH, _INITIAL_HEIGHT)
        self._user_has_resized = False

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.mousePressEvent = lambda event: self.close()  # noqa: ARG005 - Qt event signature
        self.image_label.setMinimumSize(1, 1)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        self.previous_button = PButton("◀ Previous", on_click=self._go_previous)
        self.next_button = PButton("Next ▶", on_click=self._go_next)
        nav_row = QHBoxLayout()
        nav_row.addWidget(self.previous_button)
        nav_row.addStretch()
        nav_row.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_label, stretch=1)
        layout.addLayout(nav_row)

        self._render_current()

    def _current_image(self) -> Image:
        return self._images[self._index]

    def _content_area_size(self) -> QSize:
        """The available space to scale an image into. Before a real user
        resize, use the known initial size, not the label's reported size --
        Qt's pre-layout QLabel default (640x480) isn't (0, 0), so it can't
        signal "not laid out yet". A real resize is distinguished from our
        own constructor-time self.resize() via resizeEvent by checking the
        size actually changed from the initial constants."""
        if not self._user_has_resized:
            nav_row_height = self.previous_button.sizeHint().height()
            return QSize(_INITIAL_WIDTH, _INITIAL_HEIGHT - nav_row_height)
        return self.image_label.size()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.size() != QSize(_INITIAL_WIDTH, _INITIAL_HEIGHT):
            self._user_has_resized = True

    def _elided_title(self, name: str) -> str:
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(name, Qt.TextElideMode.ElideRight, _TITLE_ELIDE_WIDTH)

    def _render_current(self) -> None:
        image = self._current_image()
        self.setWindowTitle(self._elided_title(image.name))

        pixmap = self._load_pixmap(image)
        target_size = self._content_area_size()
        if pixmap is None:
            tokens = {}
            icon = build_gallery_tile_icon(None, "broken", False, tokens, size=QSize(300, 300))
            self.image_label.setPixmap(icon.pixmap(icon.availableSizes()[0]))
        else:
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)

        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(self._images) - 1)

    def _go_previous(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._render_current()

    def _go_next(self) -> None:
        if self._index >= len(self._images) - 1:
            return
        self._index += 1
        self._render_current()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Left:
            self._go_previous()
        elif event.key() == Qt.Key.Key_Right:
            self._go_next()
        else:
            super().keyPressEvent(event)
