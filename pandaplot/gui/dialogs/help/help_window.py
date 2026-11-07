"""Modeless Help window with a searchable topic tree and a detail pane."""

import html
from typing import override

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.gui.dialogs.help.help_html import HELP_LINK_SCHEME, render_help_topic_html
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.help_catalog import HelpCatalog, get_help_catalog
from pandaplot.services.help.help_types import HelpCategory, HelpTopic
from pandaplot.services.theme.theme_manager import ThemeManager

_TOPIC_ID_ROLE = Qt.ItemDataRole.UserRole


class HelpWindow(PDialog):
    """Modeless window for browsing and searching help topics."""

    def __init__(self, app_context: AppContext, parent: QWidget | None = None, *, catalog: HelpCatalog | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self._catalog = catalog if catalog is not None else get_help_catalog()
        self._current_topic_id: str | None = None
        self._initialize()
        self._populate_tree(self._catalog.topics(), expand_all=False)
        self.show_topic(None)

    @override
    def _init_ui(self) -> None:
        self.setWindowTitle("PandaPlot Help")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.resize(880, 600)

        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search help…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName("Search help")
        self.search_edit.setAccessibleDescription("Type to filter the help topics by title, keyword or text")
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(200)
        self.tree.setAccessibleName("Help topics")
        self.tree.setAccessibleDescription("Help topics grouped by category. Select a topic to read it.")
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.splitter.addWidget(self.tree)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setAccessibleName("Help topic")
        self.browser.setAccessibleDescription("Explanation and instructions for the selected help topic")
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self.splitter.addWidget(self.browser)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([260, 620])
        layout.addWidget(self.splitter, stretch=1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = PButton("Close", role="secondary", on_click=self.close)
        self.close_btn.setAutoDefault(False)  # Enter in the search field must not close the window
        self.close_btn.setDefault(False)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)

    @override
    def _apply_theme(self) -> None:
        palette = self._palette()
        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QTreeWidget, QTextBrowser, QLineEdit {{
                background-color: {card_bg};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
        """)
        self._render_current_topic()

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Move focus from the search field to the topic list on Down arrow.

        Args:
            watched: The object the event was sent to.
            event: The event.

        Returns:
            True when the event was handled.
        """
        if (
            watched is self.search_edit
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Down
            and self._focus_topic_list()
        ):
            return True
        return super().eventFilter(watched, event)

    def show_topic(self, topic_id: str | None) -> None:
        """Select and display a topic.

        Args:
            topic_id: Id of the topic to show. ``None`` or an unknown id selects the
                first topic; an unknown id also logs a warning.
        """
        topic = self._catalog.get(topic_id) if topic_id is not None else None
        if topic_id is not None and topic is None:
            self.logger.warning("Unknown help topic id %r; showing the first topic", topic_id)

        if self.search_edit.text() and (topic is None or self._find_topic_item(topic.id) is None):
            self.search_edit.clear()  # the target is hidden by the current filter, or there is no target

        if topic is not None and self._select_topic(topic.id):
            return
        first_item = self._first_topic_item()
        if first_item is not None:
            self.tree.setCurrentItem(first_item)
            self._expand_parent(first_item)
        else:
            self._current_topic_id = None
            self._show_empty_state()

    # ------------------------------------------------------------------
    # Tree handling
    # ------------------------------------------------------------------

    def _palette(self) -> dict:
        return self.app_context.get_manager(ThemeManager).get_surface_palette()

    def _populate_tree(self, topics: tuple[HelpTopic, ...], *, expand_all: bool, ranked: bool = False) -> None:
        """Rebuild the tree from topics, grouped by category.

        Args:
            topics: Topics in display order.
            expand_all: Whether to expand every category.
            ranked: When True, categories follow the first appearance of their topics in
                ``topics`` (search ranking); otherwise they follow enum order.
        """
        with QSignalBlocker(self.tree):
            self.tree.clear()
            by_category: dict[HelpCategory, list[HelpTopic]] = {}
            for topic in topics:
                by_category.setdefault(topic.category, []).append(topic)
            categories = list(by_category) if ranked else sorted(by_category, key=lambda c: list(type(c)).index(c))
            for category in categories:
                category_item = QTreeWidgetItem(self.tree, [category.value])
                category_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                for topic in by_category[category]:
                    leaf = QTreeWidgetItem(category_item, [topic.title])
                    leaf.setData(0, _TOPIC_ID_ROLE, topic.id)
                category_item.setExpanded(expand_all)

    def _topic_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for i in range(self.tree.topLevelItemCount()):
            category_item = self.tree.topLevelItem(i)
            if category_item is None:
                continue
            for j in range(category_item.childCount()):
                child = category_item.child(j)
                if child is not None:
                    items.append(child)
        return items

    def _first_topic_item(self) -> QTreeWidgetItem | None:
        items = self._topic_items()
        return items[0] if items else None

    def _find_topic_item(self, topic_id: str) -> QTreeWidgetItem | None:
        return next((item for item in self._topic_items() if item.data(0, _TOPIC_ID_ROLE) == topic_id), None)

    def _expand_parent(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        self.tree.scrollToItem(item)

    def _select_topic(self, topic_id: str) -> bool:
        item = self._find_topic_item(topic_id)
        if item is None:
            return False
        self._expand_parent(item)
        self.tree.setCurrentItem(item)
        return True

    def _focus_topic_list(self) -> bool:
        """Focus the tree on the selected topic if it is listed, else on the first listed topic."""
        current = self.tree.currentItem()
        item = current if current is not None and current.data(0, _TOPIC_ID_ROLE) is not None else self._first_topic_item()
        if item is None:
            return False
        self._expand_parent(item)
        self.tree.setFocus()
        self.tree.setCurrentItem(item)
        return True

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        query = text.strip()
        matches = self._catalog.search(query) if query else self._catalog.topics()
        self._populate_tree(matches, expand_all=bool(query), ranked=bool(query))
        if self._current_topic_id is not None and self._select_topic(self._current_topic_id):
            return
        if matches and self._select_topic(matches[0].id):
            return
        first_item = self._first_topic_item()
        if first_item is not None:
            self._expand_parent(first_item)
            self.tree.setCurrentItem(first_item)
        else:
            self._current_topic_id = None
            self._show_empty_state()

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        topic_id = items[0].data(0, _TOPIC_ID_ROLE)
        if topic_id is None:
            return
        self._current_topic_id = topic_id
        self._render_current_topic()

    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() != HELP_LINK_SCHEME:
            return
        topic_id = url.path() or url.host()
        if topic_id and self._catalog.get(topic_id) is not None:
            self.show_topic(topic_id)
        else:
            self.logger.warning("Ignoring help link to unknown topic %r", topic_id)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _title_for(self, topic_id: str) -> str | None:
        topic = self._catalog.get(topic_id)
        return topic.title if topic is not None else None

    def _render_current_topic(self) -> None:
        topic = self._catalog.get(self._current_topic_id) if self._current_topic_id is not None else None
        if topic is None:
            self._show_empty_state()
            return
        self.browser.setHtml(render_help_topic_html(topic, self._palette(), self._title_for))

    def _show_empty_state(self) -> None:
        palette = self._palette()
        base_fg = palette.get("secondary_fg", "#666666")
        card_bg = palette.get("card_bg", "#ffffff")
        query = self.search_edit.text().strip()
        message = f"No topics match ‘{html.escape(query)}’." if query else "No help topics are available."
        self.browser.setHtml(f"<body style='background-color:{card_bg};'><p style='color:{base_fg};'>{message}</p></body>")
