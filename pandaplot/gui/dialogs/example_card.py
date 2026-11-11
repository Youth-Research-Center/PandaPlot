"""Widgets of the examples browser: the example card and the level and tags row."""

from enum import StrEnum
from typing import override

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.flow_layout import FlowLayout
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.resources.themed_icons import IconRole, themed_icon
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.examples import ExampleProject

COVER_HEIGHT = 135
COVER_MIN_WIDTH = 240
PLACEHOLDER_ICON = "chart-line"
PLACEHOLDER_ICON_SIZE = 40
_OPEN_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


class CoverSource(StrEnum):
    """Where a card's cover picture comes from."""

    COVER_IMAGE = "cover_image"
    CHART_RENDER = "chart_render"
    PLACEHOLDER = "placeholder"


def describe_contents(example: ExampleProject) -> str:
    """Return "What's inside" text such as "2 datasets · 4 charts · 1 note", skipping zero counts."""
    parts = [
        f"{count} {singular if count == 1 else plural}"
        for count, singular, plural in (
            (example.dataset_count, "dataset", "datasets"),
            (example.chart_count, "chart", "charts"),
            (example.note_count, "note", "notes"),
        )
        if count > 0
    ]
    return " · ".join(parts)


class _CoverLabel(QWidget):
    """A fixed-height area that shows a picture scaled to fit, or a centred placeholder icon."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._fit = True
        self._background = QColor("#F4F5F8")
        self.setFixedHeight(COVER_HEIGHT)
        self.setMinimumWidth(COVER_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_pixmap(self, pixmap: QPixmap, *, fit: bool) -> None:
        """Show ``pixmap``, scaled to fit the area when ``fit`` is true and at its own size (an icon) otherwise."""
        self._pixmap = pixmap
        self._fit = fit
        self.update()

    def clear_pixmap(self) -> None:
        """Drop the picture (and so its memory); the area paints only its background until a new one is set."""
        self._pixmap = None
        self.update()

    def set_background(self, color: str) -> None:
        self._background = QColor(color)
        self.update()

    @property
    def pixmap(self) -> QPixmap | None:
        """The picture currently drawn, unscaled."""
        return self._pixmap

    @override
    def sizeHint(self) -> QSize:
        return QSize(COVER_MIN_WIDTH, COVER_HEIGHT)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self._background)
        if self._pixmap is not None and not self._pixmap.isNull():
            ratio = self._pixmap.devicePixelRatio()
            logical = QSize(round(self._pixmap.width() / ratio), round(self._pixmap.height() / ratio))
            target = logical.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio) if self._fit else logical
            x = (self.width() - target.width()) // 2
            y = (self.height() - target.height()) // 2
            painter.drawPixmap(QRect(x, y, target.width(), target.height()), self._pixmap)
        painter.end()


class ExampleMetaRow(QWidget):
    """The level of an example followed by its tags as small labels."""

    def __init__(self, example: ExampleProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = FlowLayout(self, spacing=6)
        self.level_label = QLabel(example.level.label, self)
        self.level_label.setProperty("exampleLevel", True)  # noqa: FBT003 -- Qt bound method, positional-only
        layout.addWidget(self.level_label)
        self.tag_labels: list[QLabel] = []
        for tag in example.tags:
            label = QLabel(tag.label, self)
            label.setProperty("exampleTag", True)  # noqa: FBT003 -- Qt bound method, positional-only
            self.tag_labels.append(label)
            layout.addWidget(label)

    def set_tokens(self, tokens: dict) -> None:
        """Style the level as bold text and the tags as small rounded labels."""
        level_color = tokens.get("text_secondary", "#3F4350")
        tag_color = tokens.get("text_muted", "#6B7280")
        tag_bg = tokens.get("surface_inset", "#F4F5F8")
        border = tokens.get("border_control", "#DCDEE4")
        self.level_label.setStyleSheet(f"border: none; background: transparent; font-size: 12px; font-weight: 600; color: {level_color};")
        for label in self.tag_labels:
            label.setStyleSheet(
                f"background-color: {tag_bg}; color: {tag_color}; border: 1px solid {border}; border-radius: 8px; padding: 1px 7px; font-size: 11px;"
            )


class ExampleCard(Card):
    """One example in the list: cover, title, summary, level and tags, what's inside and two actions.

    The card is keyboard-focusable and Enter requests the details. The dialog supplies a rendered cover with
    `set_cover_pixmap` when the example has no cover image. The owner forwards theme changes to `set_tokens`.

    Attributes:
        example: The example shown.
        cover_source: Where the cover picture currently comes from.
        details_requested: Emitted with the example when the user wants its details.
        open_requested: Emitted with the example when the user wants to open it.
    """

    details_requested = Signal(object)
    open_requested = Signal(object)

    def __init__(self, app_context: AppContext, example: ExampleProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_context = app_context
        self.example = example
        self.cover_source = CoverSource.PLACEHOLDER
        self.setObjectName("ExampleCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(example.name)
        self.setAccessibleDescription(example.summary)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.cover = _CoverLabel(self)
        layout.addWidget(self.cover)

        self.title_label = QLabel(example.name, self)
        self.title_label.setWordWrap(True)
        self.title_label.setAccessibleName(example.name)
        layout.addWidget(self.title_label)

        self.summary_label = QLabel(example.summary, self)
        self.summary_label.setWordWrap(True)
        self.summary_label.setVisible(bool(example.summary))
        layout.addWidget(self.summary_label)

        self.meta_row = ExampleMetaRow(example, self)
        layout.addWidget(self.meta_row)

        self.contents_label = QLabel(describe_contents(example), self)
        self.contents_label.setVisible(bool(self.contents_label.text()))
        layout.addWidget(self.contents_label)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.details_button = PButton("See details", role="secondary", on_click=lambda: self.details_requested.emit(self.example))
        self.open_button = PButton("Open example", role="primary", on_click=lambda: self.open_requested.emit(self.example))
        for button in (self.details_button, self.open_button):
            # A dialog would otherwise press the first auto-default button when Enter is pressed elsewhere; the
            # owning dialog gives the focused button its Enter activation instead.
            button.setAutoDefault(False)
            buttons.addWidget(button)
        self.details_button.setAccessibleName(f"See details of {example.name}")
        self.open_button.setAccessibleName(f"Open example {example.name}")
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.set_tokens(app_context.get_manager(ThemeManager).get_design_tokens())

    @property
    def has_summary(self) -> bool:
        """Whether the summary text is shown."""
        return not self.summary_label.isHidden()

    def set_cover_pixmap(self, pixmap: QPixmap, source: CoverSource) -> None:
        """Show a picture as the cover.

        Args:
            pixmap: The picture; it is scaled to fit when drawn.
            source: Where it comes from.
        """
        self.cover_source = source
        self.cover.set_pixmap(pixmap, fit=True)

    def release_cover(self) -> None:
        """Drop the cover picture to free its memory; the card is not meant to show a cover again afterwards."""
        self.cover_source = CoverSource.PLACEHOLDER
        self.cover.clear_pixmap()

    def set_tokens(self, tokens: dict) -> None:
        """Apply theme tokens to the card, its texts and the placeholder icon."""
        super().set_tokens(tokens)
        plain = "border: none; background: transparent;"
        self.title_label.setStyleSheet(f"{plain} font-size: 15px; font-weight: 700; color: {tokens.get('text_primary', '#1C1E26')};")
        self.summary_label.setStyleSheet(f"{plain} font-size: 12px; color: {tokens.get('text_muted', '#6B7280')};")
        self.contents_label.setStyleSheet(f"{plain} font-size: 12px; color: {tokens.get('text_muted', '#6B7280')};")
        self.meta_row.set_tokens(tokens)
        self.cover.set_background(tokens.get("surface_inset", "#F4F5F8"))
        if self.cover_source is CoverSource.PLACEHOLDER:
            icon = themed_icon(self._app_context, PLACEHOLDER_ICON, role=IconRole.MUTED, size=PLACEHOLDER_ICON_SIZE)
            self.cover.set_pixmap(icon.pixmap(QSize(PLACEHOLDER_ICON_SIZE, PLACEHOLDER_ICON_SIZE)), fit=False)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in _OPEN_KEYS:
            self.details_requested.emit(self.example)
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_focus_ring(self, *, focused: bool) -> None:
        """Outline the card in the accent colour (the shared "selected" card style) while it has keyboard focus."""
        self.setProperty("selected", focused)
        self.style().unpolish(self)
        self.style().polish(self)

    @override
    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self._set_focus_ring(focused=True)

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self._set_focus_ring(focused=False)
