"""Dialog for browsing the bundled example projects as cards, with search, tag filters and a details page."""

from typing import TYPE_CHECKING, override

import shiboken6
from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QKeyEvent, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.core.widget_extension import PDialog, unsubscribe_widget_tree
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.project.example_info import EXAMPLE_TAGS, ExampleSection, TagGroup, example_tag
from pandaplot.models.project.items import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.example_project_loader import ExampleProjectLoader
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.example_filter import filter_examples, tag_counts
from pandaplot.utils.examples import ExampleProject, discover_example_projects

if TYPE_CHECKING:
    from pandaplot.gui.dialogs.example_card import ExampleCard, ExampleMetaRow

DEFAULT_SIZE = QSize(900, 640)
MINIMUM_SIZE = QSize(480, 420)
TWO_COLUMN_MIN_WIDTH = 820
PREVIEW_WIDTH = 260
PREVIEW_HEIGHT = 170
DESCRIPTION_FONT_SIZE = 11
SUBTITLE = "Browse what PandaPlot can do. Open an example to explore it; your copy won't change the original."
_ENTER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
_FILTERS_BUTTON_PADDING = 40  # room for the button's own padding and the gap between its icon and label
_EXTERNAL_LINK_SCHEMES = frozenset({"http", "https", "mailto"})
_GROUP_LABELS = {TagGroup.TOPIC: "Topic", TagGroup.TECHNIQUE: "Technique"}


class _AutoHeightTextBrowser(QTextBrowser):
    """A read-only rich text view that is as tall as its text, so a surrounding scroll area does the scrolling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Open web and mail links in the system's handler; any other link (relative, file) is ignored so the text stays."""
        if url.scheme().lower() in _EXTERNAL_LINK_SCHEMES:
            QDesktopServices.openUrl(url)

    def fit_height(self) -> None:
        """Resize to the height of the document at the current width."""
        document = self.document()
        document.setTextWidth(self.viewport().width())
        self.setFixedHeight(int(document.size().height()) + 2 * self.frameWidth() + 4)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit_height()


class ExamplesDialog(PDialog):
    """Lets the user browse bundled example projects and pick one to open.

    A list page shows the examples as cards grouped in sections, with a search box and tag filters. **See details**
    switches to a details page with the full description and live previews of the featured charts. On acceptance,
    `selected_path` holds the chosen project's file path.

    Attributes:
        selected_path: File path of the example the user chose to open, or None.
    """

    def __init__(self, app_context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(app_context=app_context, parent=parent)
        self.selected_path: str | None = None
        self._examples: list[ExampleProject] = discover_example_projects()
        self._loader = ExampleProjectLoader(app_context)
        self._chart_pixmaps: dict[tuple[str, str], QPixmap | None] = {}
        self._selected_tag_ids: frozenset[str] = frozenset()
        self._cover_requested: set[str] = set()
        self._details_example: ExampleProject | None = None
        self._details_token = 0
        self._origin_card: ExampleCard | None = None
        self._origin_focus: QWidget | None = None
        self._list_scroll_value = 0
        self._columns = 0
        self._laid_out_key: tuple[tuple[str, ...], int] | None = None
        self._released = False
        self._initialize()

    # ------------------------------------------------------------------ construction

    @override
    def _init_ui(self) -> None:
        self.setObjectName("ExamplesDialog")
        self.setWindowTitle("Examples")
        self.setModal(True)
        self.resize(DEFAULT_SIZE)
        self.setMinimumSize(MINIMUM_SIZE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack)
        self.list_page = self._build_list_page()
        self.details_page = self._build_details_page()
        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.details_page)
        self.search_edit.setFocus()
        self.list_scroll.verticalScrollBar().valueChanged.connect(self._schedule_visible_covers)
        self._refresh()

    def _build_list_page(self) -> QWidget:
        from pandaplot.gui.components.common.empty_state_panel import EmptyStatePanel
        from pandaplot.gui.components.common.p_button import PButton
        from pandaplot.gui.components.common.section_header import SectionHeader
        from pandaplot.gui.dialogs.example_card import ExampleCard

        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        self.title_label = QLabel("Examples", page)
        self.title_label.setAccessibleName("Examples")
        layout.addWidget(self.title_label)
        self.subtitle_label = QLabel(SUBTITLE, page)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QLineEdit(page)
        self.search_edit.setPlaceholderText("Search examples")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName("Search examples")
        self.search_edit.textChanged.connect(self._on_filters_changed)
        search_row.addWidget(self.search_edit, 1)
        self.filters_button = PButton("Filters", role="secondary")
        self.filters_button.setCheckable(True)
        self.filters_button.setAccessibleName("Filters")
        self.filters_button.toggled.connect(self._on_filters_toggled)
        self._enter_activates(self.filters_button)
        search_row.addWidget(self.filters_button)
        self.clear_button = PButton("Clear filters", role="secondary", on_click=self._clear_filters)
        self._enter_activates(self.clear_button)
        search_row.addWidget(self.clear_button)
        self.search_row = QWidget(page)
        self.search_row.setLayout(search_row)
        search_row.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.search_row)

        self.chips_widget = self._build_chips(page)
        layout.addWidget(self.chips_widget)
        self.filters_button.setVisible(bool(self.tag_chips))
        QWidget.setTabOrder(self.search_edit, self.filters_button)
        QWidget.setTabOrder(self.filters_button, self.clear_button)
        previous: QWidget = self.clear_button
        for chip in self.tag_chips.values():
            QWidget.setTabOrder(previous, chip)
            previous = chip

        self.no_examples_label = QLabel("No example projects were found.", page)
        self.no_examples_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_examples_label.setVisible(not self._examples)
        layout.addWidget(self.no_examples_label)

        self.list_scroll = QScrollArea(page)
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_scroll.viewport().setAutoFillBackground(False)
        self.list_scroll.setVisible(bool(self._examples))
        content = QWidget(self.list_scroll)
        content.setObjectName("ExamplesListContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(8)

        self.section_headers: dict[ExampleSection, SectionHeader] = {}
        self.section_grids: dict[ExampleSection, QGridLayout] = {}
        self.cards: list[ExampleCard] = []
        for section in ExampleSection:
            section_examples = [example for example in self._examples if example.section is section]
            if not section_examples:
                continue
            header = SectionHeader(section.label, content)
            header.setAccessibleName(section.label)
            content_layout.addWidget(header)
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            content_layout.addLayout(grid)
            self.section_headers[section] = header
            self.section_grids[section] = grid
            for example in section_examples:
                card = ExampleCard(self.app_context, example, content)
                card.details_requested.connect(self._show_details)
                card.open_requested.connect(self._open_example)
                self._enter_activates(card.details_button, card.open_button)
                self._apply_cover_image(card)
                self.cards.append(card)

        self.empty_panel: EmptyStatePanel = EmptyStatePanel(
            self.app_context,
            heading="No examples match",
            description="Try other words or fewer filters.",
            icon_name="magnifying-glass",
            actions=[("Clear filters", self._clear_filters)],
            parent=content,
        )
        self._enter_activates(self.empty_panel.action_buttons[0])
        self.empty_panel.setMinimumHeight(160)
        content_layout.addWidget(self.empty_panel)
        content_layout.addStretch(1)
        self.list_scroll.setWidget(content)
        layout.addWidget(self.list_scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_btn = PButton("Close", role="secondary", on_click=self.reject)
        self._enter_activates(self.close_btn)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)
        return page

    def _build_chips(self, parent: QWidget) -> QWidget:
        from pandaplot.gui.components.common.flow_layout import FlowLayout
        from pandaplot.gui.components.common.p_button import PButton

        used_tag_ids = {tag.id for example in self._examples for tag in example.tags}
        self.tag_chips: dict[str, PButton] = {}
        self.group_labels: dict[TagGroup, QLabel] = {}
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for group in TagGroup:
            group_tags = [tag for tag in EXAMPLE_TAGS if tag.group is group and tag.id in used_tag_ids]
            if not group_tags:
                continue
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(_GROUP_LABELS[group], widget)
            label.setFixedWidth(80)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            label.setContentsMargins(0, 5, 0, 0)
            self.group_labels[group] = label
            row.addWidget(label)
            chips_host = QWidget(widget)
            flow = FlowLayout(chips_host, spacing=6)
            for tag in group_tags:
                chip = PButton(tag.label, role="secondary", parent=chips_host)
                chip.setProperty("chip", True)  # noqa: FBT003 -- Qt bound method, positional-only
                chip.setCheckable(True)
                self._enter_activates(chip)
                chip.setAccessibleName(f"{_GROUP_LABELS[group]}: {tag.label}")
                chip.toggled.connect(lambda checked, tag_id=tag.id: self._on_chip_toggled(tag_id, checked=checked))
                self.tag_chips[tag.id] = chip
                flow.addWidget(chip)
            row.addWidget(chips_host, 1)
            layout.addLayout(row)
        widget.setVisible(False)  # collapsed until the Filters button is toggled; expanding needs tags
        return widget

    def _build_details_page(self) -> QWidget:
        from pandaplot.gui.components.common.flow_layout import FlowLayout
        from pandaplot.gui.components.common.p_button import PButton
        from pandaplot.gui.components.common.section_header import SectionHeader

        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.back_button = PButton("Back", role="secondary", on_click=self._show_list)
        self._enter_activates(self.back_button)
        self.back_button.setAccessibleName("Back to the list of examples")
        top.addWidget(self.back_button)
        top.addStretch(1)
        layout.addLayout(top)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        self.details_scroll = scroll
        content = QWidget(scroll)
        content.setObjectName("ExampleDetailsContent")
        self.details_layout = QVBoxLayout(content)
        self.details_layout.setContentsMargins(0, 0, 8, 0)
        self.details_layout.setSpacing(10)

        self.details_title = QLabel(content)
        self.details_title.setWordWrap(True)
        self.details_layout.addWidget(self.details_title)
        self.details_meta_slot = QVBoxLayout()
        self.details_meta_slot.setContentsMargins(0, 0, 0, 0)
        self.details_layout.addLayout(self.details_meta_slot)
        self.details_meta: ExampleMetaRow | None = None
        self.details_contents = QLabel(content)
        self.details_layout.addWidget(self.details_contents)

        self.description_browser = _AutoHeightTextBrowser(content)
        self.description_browser.setAccessibleName("Description")
        self.details_layout.addWidget(self.description_browser)

        self.previews_header = SectionHeader("Featured charts", content)
        self.details_layout.addWidget(self.previews_header)
        self.previews_host = QWidget(content)
        self.previews_flow = FlowLayout(self.previews_host, spacing=12)
        self.details_layout.addWidget(self.previews_host)
        self.preview_tiles: list[QWidget] = []
        self.preview_images: list[QLabel] = []
        self.preview_captions: list[QLabel] = []

        self.credit_header = SectionHeader("Data source and credit", content)
        self.details_layout.addWidget(self.credit_header)
        self.credit_label = QLabel(content)
        self.credit_label.setWordWrap(True)
        self.credit_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_layout.addWidget(self.credit_label)
        self.details_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.bottom_back_button = PButton("Back", role="secondary", on_click=self._show_list)
        self._enter_activates(self.bottom_back_button)
        self.details_open_button = PButton("Open example", role="primary", on_click=self._open_details_example)
        self._enter_activates(self.details_open_button)
        bottom.addStretch(1)
        bottom.addWidget(self.bottom_back_button)
        bottom.addWidget(self.details_open_button)
        layout.addLayout(bottom)
        return page

    # ------------------------------------------------------------------ list page

    @property
    def selected_tag_ids(self) -> frozenset[str]:
        """Ids of the tags currently selected as filters."""
        return self._selected_tag_ids

    @property
    def visible_cards(self) -> list["ExampleCard"]:
        """The cards that match the current filters, in display order."""
        matching = {example.path for example in self._matching_examples()}
        return [card for card in self.cards if card.example.path in matching]

    def _matching_examples(self) -> list[ExampleProject]:
        return filter_examples(self._examples, query=self.search_edit.text(), selected_tag_ids=self._selected_tag_ids)

    def _on_filters_changed(self, _text: str = "") -> None:
        self._refresh()

    def _on_chip_toggled(self, tag_id: str, *, checked: bool) -> None:
        self._selected_tag_ids = self._selected_tag_ids | {tag_id} if checked else self._selected_tag_ids - {tag_id}
        self._refresh()

    def _on_filters_toggled(self, checked: bool) -> None:  # noqa: FBT001 -- connected to QAbstractButton.toggled
        """Show or hide the tag chips; the cards below take or give back the space."""
        if not checked and self.chips_widget.isAncestorOf(self.focusWidget()):
            self.filters_button.setFocus()
        self.chips_widget.setVisible(checked and bool(self.tag_chips))
        self._sync_filters_button()
        self._schedule_visible_covers()

    def _sync_filters_button(self) -> None:
        """Update the Filters button's caret, label, accessible description and fixed width from the toggle and the selected tags."""
        count = len(self._selected_tag_ids)
        button = self.filters_button
        button.setText(f"Filters ({count})" if count else "Filters")
        button.setAccessibleDescription(f"{count} {'filter' if count == 1 else 'filters'} active" if count else "No filters active")
        button.setIcon(themed_icon(self.app_context, "caret-up" if button.isChecked() else "caret-down"))
        widest = button.fontMetrics().horizontalAdvance("Filters (99)")
        button.setMinimumWidth(widest + button.iconSize().width() + _FILTERS_BUTTON_PADDING)

    def _clear_filters(self) -> None:
        """Clear the search text and every tag chip."""
        for chip in self.tag_chips.values():
            chip.blockSignals(True)  # noqa: FBT003 -- Qt method, no keyword args
            chip.setChecked(False)
            chip.blockSignals(False)  # noqa: FBT003 -- Qt method, no keyword args
        self._selected_tag_ids = frozenset()
        self.search_edit.blockSignals(True)  # noqa: FBT003 -- Qt method, no keyword args
        self.search_edit.clear()
        self.search_edit.blockSignals(False)  # noqa: FBT003 -- Qt method, no keyword args
        self._refresh()
        self.search_edit.setFocus()

    def _refresh(self) -> None:
        """Update the chips, the Clear filters button and the visible cards from the current filters."""
        query = self.search_edit.text()
        counts = tag_counts(self._examples, query=query, selected_tag_ids=self._selected_tag_ids)
        for tag_id, chip in self.tag_chips.items():
            selected = tag_id in self._selected_tag_ids
            tag = example_tag(tag_id)
            chip.setText(f"{tag.label if tag is not None else tag_id} ({counts[tag_id]})")
            chip.setEnabled(selected or counts[tag_id] > 0)
            chip.setProperty("selected", selected)
            chip.style().unpolish(chip)
            chip.style().polish(chip)
        self.clear_button.setEnabled(bool(query.strip()) or bool(self._selected_tag_ids))
        self._sync_filters_button()
        self._layout_cards(self._matching_examples())

    def _desired_columns(self) -> int:
        return 2 if self.width() >= TWO_COLUMN_MIN_WIDTH else 1

    def _layout_cards(self, matching_examples: list[ExampleProject]) -> None:
        """Place the matching cards in the section grids, hide the rest and show the empty state when none match.

        Nothing is rebuilt when the matching set and the column count are the same as the last time.
        """
        self._columns = self._desired_columns()
        matching = {example.path for example in matching_examples}
        key = (tuple(example.path for example in matching_examples), self._columns)
        if key == self._laid_out_key:
            return
        self._laid_out_key = key
        for section, grid in self.section_grids.items():
            while grid.count():
                grid.takeAt(0)
            visible = [card for card in self.cards if card.example.section is section and card.example.path in matching]
            for card in self.cards:
                if card.example.section is section and card.example.path not in matching:
                    card.setVisible(False)
            for index, card in enumerate(visible):
                grid.addWidget(card, index // self._columns, index % self._columns)
                card.setVisible(True)
            for column in range(2):
                grid.setColumnStretch(column, 1 if column < self._columns else 0)
            self.section_headers[section].setVisible(bool(visible))
        self.empty_panel.setVisible(bool(self._examples) and not matching)
        self._schedule_visible_covers()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._columns and self._desired_columns() != self._columns:
            self._layout_cards(self._matching_examples())
        self._schedule_visible_covers()

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._released = False
        self._schedule_visible_covers()

    def _schedule_visible_covers(self, _value: int = 0) -> None:
        """Request covers for the cards in view once the layout has settled."""
        QTimer.singleShot(0, self._request_visible_covers)

    def _request_visible_covers(self) -> None:
        """Request the live cover render of every shown card that intersects the scroll viewport."""
        if not shiboken6.isValid(self) or not self.list_scroll.isVisible():
            return
        content = self.list_scroll.widget()
        layout = content.layout() if content is not None else None
        if layout is not None:
            layout.activate()
        viewport = self.list_scroll.viewport()
        view_rect = viewport.rect()
        for card in self.cards:
            if card.isHidden() or card.example.path in self._cover_requested:
                continue
            top_left = card.mapTo(viewport, QPoint(0, 0))
            if view_rect.intersects(card.rect().translated(top_left)):
                self._request_cover(card)

    # ------------------------------------------------------------------ rendering

    def _render_chart_pixmap(self, example: ExampleProject, chart_id: str) -> QPixmap | None:
        """Render one chart of an example live, or None when it cannot be rendered. Cached per dialog, failures included."""
        key = (example.path, chart_id)
        if key in self._chart_pixmaps:
            return self._chart_pixmaps[key]
        pixmap: QPixmap | None = None
        try:
            # Imported here: the chart editor module pulls in the whole chart stack, which is not needed until a preview is drawn.
            from pandaplot.gui.components.tabs.chart import chart_editor

            project = self._loader.load(example)
            chart = project.find_item(chart_id) if project is not None else None
            if isinstance(chart, Chart):
                ratio = self.devicePixelRatioF()
                image = chart_editor.render_chart_to_qimage(
                    chart,
                    chart_editor.resolve_chart_series_data(project, chart),
                    chart_editor.resolve_chart_size_defaults(self.app_context),
                    max_size_px=(round(PREVIEW_WIDTH * ratio), round(PREVIEW_HEIGHT * ratio)),
                )
                if isinstance(image, QImage) and not image.isNull():
                    pixmap = QPixmap.fromImage(image)
                    pixmap.setDevicePixelRatio(ratio)
            if pixmap is None:
                self.logger.warning("Chart '%s' of example '%s' could not be rendered", chart_id, example.path)
        except Exception:
            self.logger.exception("Rendering chart '%s' of example '%s' failed", chart_id, example.path)
            pixmap = None
        self._chart_pixmaps[key] = pixmap
        return pixmap

    def _apply_cover_image(self, card: "ExampleCard") -> None:
        """Use the example's cover image for the card when it has one that can be decoded."""
        from pandaplot.gui.dialogs.example_card import CoverSource

        data = card.example.cover_image
        if not data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            card.set_cover_pixmap(pixmap, CoverSource.COVER_IMAGE)
            self._cover_requested.add(card.example.path)
        else:
            self.logger.warning("Cover image of example '%s' could not be decoded", card.example.path)

    def _request_cover(self, card: "ExampleCard") -> None:
        """Schedule the live render of the first featured chart as the cover of a card that has no cover image."""
        example = card.example
        if example.path in self._cover_requested or not example.featured_chart_ids:
            return
        self._cover_requested.add(example.path)
        QTimer.singleShot(0, lambda: self._load_cover(card))

    def _load_cover(self, card: "ExampleCard") -> None:
        from pandaplot.gui.dialogs.example_card import CoverSource

        if not shiboken6.isValid(self) or self._released or not shiboken6.isValid(card):
            return
        pixmap = self._render_chart_pixmap(card.example, card.example.featured_chart_ids[0])
        if pixmap is not None:
            card.set_cover_pixmap(pixmap, CoverSource.CHART_RENDER)

    # ------------------------------------------------------------------ details page

    def _show_details(self, example: ExampleProject) -> None:
        """Switch to the details page for an example."""
        self._list_scroll_value = self.list_scroll.verticalScrollBar().value()
        self._origin_card = next((card for card in self.cards if card.example.path == example.path), None)
        focused = self.focusWidget()
        # The card's own button (See details) when it was pressed with focus on it; the card itself otherwise.
        self._origin_focus = focused if focused is not None and self._origin_card is not None and self._origin_card.isAncestorOf(focused) else None
        self._details_example = example
        self._populate_details(example)
        self.stack.setCurrentWidget(self.details_page)
        self.details_scroll.verticalScrollBar().setValue(0)
        self.details_open_button.setFocus()
        self._start_preview_renders()

    def _show_list(self) -> None:
        """Go back to the list with the same search, chips and scroll position."""
        self._details_token += 1
        self._details_example = None
        self.stack.setCurrentWidget(self.list_page)
        self.list_scroll.verticalScrollBar().setValue(self._list_scroll_value)
        # A resize while the list was hidden can bring cards into view without moving the scroll bar.
        self._schedule_visible_covers()
        for widget in (self._origin_focus, self._origin_card):
            if widget is not None and shiboken6.isValid(widget) and widget.isVisible() and widget.isEnabled():
                widget.setFocus()
                return
        self.search_edit.setFocus()

    def _populate_details(self, example: ExampleProject) -> None:
        from pandaplot.gui.dialogs.example_card import ExampleMetaRow, describe_contents

        self._details_token += 1
        self.details_title.setText(example.name)
        self.details_title.setAccessibleName(example.name)
        if self.details_meta is not None:
            self._discard(self.details_meta)
        self.details_meta = ExampleMetaRow(example, self.details_scroll.widget())
        self.details_meta_slot.addWidget(self.details_meta)
        contents = describe_contents(example)
        self.details_contents.setText(f"What's inside: {contents}" if contents else "")
        self.details_contents.setVisible(bool(contents))
        self._render_description(example)

        for tile in self.preview_tiles:
            self.previews_flow.removeWidget(tile)
            self._discard(tile)
        self.preview_tiles.clear()
        self.preview_images.clear()
        self.preview_captions.clear()
        for number, _chart_id in enumerate(example.featured_chart_ids, start=1):
            self._add_preview_tile(f"Chart {number}")
        self.previews_header.setVisible(bool(example.featured_chart_ids))
        self.previews_host.setVisible(bool(example.featured_chart_ids))

        self.credit_label.setText(example.data_credit)
        self.credit_header.setVisible(bool(example.data_credit))
        self.credit_label.setVisible(bool(example.data_credit))
        self._apply_details_tokens(self._tokens())

    def _render_description(self, example: ExampleProject) -> None:
        # Imported here: the renderer pulls in the markdown package, which is only needed once details are shown.
        from pandaplot.services.note_render.latex_markdown_renderer import render_body_html, wrap_document

        tokens = self._tokens()
        color = tokens.get("text_primary", "#1C1E26")
        background = tokens.get("surface_chrome", "#FBFBFC")
        body = render_body_html(example.description.strip() or example.summary, color=color, fontsize=DESCRIPTION_FONT_SIZE)
        html = wrap_document(
            body, color=color, background=background, border=tokens.get("border_control", "#DCDEE4"), fontsize=DESCRIPTION_FONT_SIZE
        )
        self.description_browser.setHtml(html)
        self.description_browser.fit_height()

    def _add_preview_tile(self, caption: str) -> None:
        tile = QWidget(self.previews_host)
        image = QLabel("Loading preview...", tile)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        image.setProperty("previewImage", True)  # noqa: FBT003 -- Qt bound method, positional-only
        caption_label = QLabel(caption, tile)
        caption_label.setWordWrap(True)
        caption_label.setFixedWidth(PREVIEW_WIDTH)
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setSpacing(4)
        tile_layout.addWidget(image)
        tile_layout.addWidget(caption_label)
        tile.setAccessibleName(caption)
        self.preview_tiles.append(tile)
        self.preview_images.append(image)
        self.preview_captions.append(caption_label)
        self.previews_flow.addWidget(tile)

    def _start_preview_renders(self) -> None:
        """Render the previews one event-loop turn at a time, after the details page is shown."""
        example = self._details_example
        if example is None:
            return
        token = self._details_token
        for index, chart_id in enumerate(example.featured_chart_ids):
            QTimer.singleShot(0, lambda index=index, chart_id=chart_id: self._load_preview(token, example, index, chart_id))

    def _load_preview(self, token: int, example: ExampleProject, index: int, chart_id: str) -> None:
        if not shiboken6.isValid(self) or self._released or token != self._details_token or index >= len(self.preview_images):
            return
        image_label = self.preview_images[index]
        caption_label = self.preview_captions[index]
        pixmap = self._render_chart_pixmap(example, chart_id)
        project = self._loader.load(example)
        chart = project.find_item(chart_id) if project is not None else None
        if chart is not None:
            caption_label.setText(chart.name)
            self.preview_tiles[index].setAccessibleName(chart.name)
        if pixmap is None:
            image_label.setText("Preview not available")
            return
        ratio = self.devicePixelRatioF()
        scaled = pixmap.scaled(
            round(PREVIEW_WIDTH * ratio),
            round(PREVIEW_HEIGHT * ratio),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        image_label.setPixmap(scaled)

    @staticmethod
    def _discard(widget: QWidget) -> None:
        """Remove a widget from view at once (a plain deleteLater can still paint for a frame) and delete it."""
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()

    # ------------------------------------------------------------------ opening and keys

    def _enter_activates(self, *buttons: QPushButton) -> None:
        """Make Enter/Return press these buttons when they have focus.

        They are not auto-default buttons, so Enter in the search box does not press the first one; this filter gives the
        focused button the keyboard activation a default button would have had.
        """
        for button in buttons:
            button.setAutoDefault(False)
            button.installEventFilter(self)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress and event.key() in _ENTER_KEYS and isinstance(
            watched, QAbstractButton
        ):
            watched.click()
            return True
        return super().eventFilter(watched, event)

    @override
    def done(self, result: int) -> None:
        """Close, then release the cached projects and pictures and leave the event bus; the dialog is not reused after it closes."""
        super().done(result)
        self._release_caches()
        self._released = True
        # The bus holds the dialog's bound handlers, which would keep it (and its theme handler) alive after deleteLater().
        unsubscribe_widget_tree(self)

    def _release_caches(self) -> None:
        self._details_token += 1
        self._loader.clear()
        self._chart_pixmaps.clear()
        self._cover_requested.clear()
        for card in self.cards:
            card.release_cover()
        for label in self.preview_images:
            label.clear()

    def _open_example(self, example: ExampleProject) -> None:
        self.selected_path = example.path
        self.accept()

    def _open_details_example(self) -> None:
        if self._details_example is not None:
            self._open_example(self._details_example)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self.stack.currentWidget() is self.details_page:
            self._show_list()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ theme

    def _tokens(self) -> dict:
        return self.app_context.get_manager(ThemeManager).get_design_tokens()

    @override
    def _apply_theme(self) -> None:
        tokens = self._tokens()
        text_primary = tokens["text_primary"]
        text_muted = tokens["text_muted"]
        plain = "border: none; background: transparent;"
        self.setStyleSheet(
            f"QDialog#ExamplesDialog {{ background-color: {tokens['surface_chrome']}; }}"
            f"QWidget#ExamplesListContent, QWidget#ExampleDetailsContent {{ background-color: transparent; }}"
            f"QScrollArea {{ background: transparent; }}"
            f'QPushButton[chip="true"]:disabled {{ color: {tokens['text_disabled']}; border-color: {tokens['border_subtle']}; }}'
        )
        self._sync_filters_button()
        self.title_label.setStyleSheet(f"{plain} font-size: 20px; font-weight: 700; color: {text_primary};")
        self.subtitle_label.setStyleSheet(f"{plain} color: {text_muted};")
        self.no_examples_label.setStyleSheet(f"{plain} color: {text_muted};")
        for label in self.group_labels.values():
            label.setStyleSheet(f"{plain} font-weight: 600; color: {tokens['text_secondary']};")
        for header in self.section_headers.values():
            header.set_tokens(tokens)
        for card in self.cards:
            card.set_tokens(tokens)
        self.empty_panel.set_tokens(tokens)
        self._apply_details_tokens(tokens)
        if self._details_example is not None:
            self._render_description(self._details_example)

    def _apply_details_tokens(self, tokens: dict) -> None:
        plain = "border: none; background: transparent;"
        self.details_title.setStyleSheet(f"{plain} font-size: 20px; font-weight: 700; color: {tokens['text_primary']};")
        self.details_contents.setStyleSheet(f"{plain} color: {tokens['text_muted']};")
        self.credit_label.setStyleSheet(f"{plain} color: {tokens['text_muted']};")
        self.previews_header.set_tokens(tokens)
        self.credit_header.set_tokens(tokens)
        if self.details_meta is not None:
            self.details_meta.set_tokens(tokens)
        for image in self.preview_images:
            image.setStyleSheet(
                f"background-color: {tokens['surface_white']}; color: {tokens['text_muted']};"
                f" border: 1px solid {tokens['border_control']}; border-radius: 4px;"
            )
        for caption in self.preview_captions:
            caption.setStyleSheet(f"{plain} color: {tokens['text_secondary']};")
