"""Sidebar panel for searching across all notes in the project.

Type a query to find matches in every note's title and content. Results are
grouped by note; double-clicking a match opens that note and jumps the editor
to the matched text.
"""

from typing import Optional, override

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events.event_types import NoteEvents, ProjectEvents, UIEvents
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.note_search.note_search_service import (
    NoteMatch,
    QueryError,
    build_snippet,
    search_notes,
)
from pandaplot.services.theme.theme_manager import ThemeManager

# Roles for stashing match metadata on result rows.
_ROLE_NOTE_ID = Qt.ItemDataRole.UserRole + 1
_ROLE_MATCH = Qt.ItemDataRole.UserRole + 2
_ROLE_SNIPPET = Qt.ItemDataRole.UserRole + 3  # (text, hl_start, hl_end)


class _HighlightDelegate(QStyledItemDelegate):
    """Renders match rows with the matched substring highlighted.

    The highlight colour is supplied by the panel so it tracks the theme.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight = "#ffe08a"
        self.highlight_fg = "#000000"

    def _document(self, index) -> Optional[QTextDocument]:
        snippet = index.data(_ROLE_SNIPPET)
        if not snippet:
            return None
        text, hl_start, hl_end = snippet
        before = _escape(text[:hl_start])
        hit = _escape(text[hl_start:hl_end])
        after = _escape(text[hl_end:])
        doc = QTextDocument()
        doc.setDocumentMargin(2)
        # Keep each snippet on a single line so the height sizeHint reports
        # matches what paint draws; overly long snippets are clipped, not
        # wrapped (build_snippet already trims around the match).
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.NoWrap)
        doc.setDefaultTextOption(option)
        doc.setHtml(
            f'<span>{before}</span>'
            f'<span style="background-color:{self.highlight};color:{self.highlight_fg};">{hit}</span>'
            f'<span>{after}</span>'
        )
        return doc

    @override
    def paint(self, painter, option, index):
        doc = self._document(index)
        if doc is None:
            super().paint(painter, option, index)
            return

        # Draw the normal row background/selection, then the rich text on top,
        # vertically centred within the row.
        self.initStyleOption(option, index)
        option.text = ""
        widget = option.widget
        if widget:
            widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, widget)

        doc_height = doc.size().height()
        y_offset = option.rect.top() + max(0, (option.rect.height() - doc_height) / 2)

        painter.save()
        painter.setClipRect(option.rect)
        painter.translate(option.rect.left() + 4, y_offset)
        doc.drawContents(painter)
        painter.restore()

    @override
    def sizeHint(self, option, index) -> QSize:
        doc = self._document(index)
        if doc is None:
            return super().sizeHint(option, index)
        size = doc.size()
        return QSize(int(size.width()) + 8, int(size.height()))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_dark(hex_color: str) -> bool:
    """Rough luminance test so highlight colours adapt to the theme."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return False
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


class SearchPanel(SidebarPanel):
    """Search-across-notes panel shown in the sidebar."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.app_state = app_context.get_app_state()

        # Debounce search-as-you-type so we don't re-scan on every keystroke.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.run_search)

        self._initialize()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(ProjectEvents.PROJECT_LOADED, self._on_project_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_CLOSED, self._on_project_changed)
        # Keep results live as notes are edited / added / removed.
        self.subscribe_to_event(NoteEvents.NOTE_CONTENT_CHANGED, self._on_project_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_STRUCTURE_CHANGED, self._on_project_changed)

    @override
    def _init_ui(self):
        self._init_panel_layout()

        self._set_title("🔍 Search Notes")

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search across all notes…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(lambda _: self._debounce.start())
        self.search_input.returnPressed.connect(self.run_search)
        self.main_layout.addWidget(self.search_input)

        # Option toggles
        options_row = QHBoxLayout()
        options_row.setSpacing(4)
        self.case_button = self._make_toggle("Aa", "Match case")
        self.word_button = self._make_toggle("W", "Whole word")
        self.regex_button = self._make_toggle(".*", "Regular expression")
        for btn in (self.case_button, self.word_button, self.regex_button):
            btn.toggled.connect(self.run_search)
            options_row.addWidget(btn)
        options_row.addStretch()
        self.main_layout.addLayout(options_row)

        # Summary line
        self.summary_label = QLabel("")
        self.main_layout.addWidget(self.summary_label)

        # Results tree
        self.results = QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setUniformRowHeights(False)
        self.delegate = _HighlightDelegate(self.results)
        self.results.setItemDelegate(self.delegate)
        self.results.itemActivated.connect(self._on_item_activated)
        self.main_layout.addWidget(self.results, 1)

    def _make_toggle(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("chip", True)  # noqa: FBT003 - Qt method rejects keyword args
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.toggled.connect(lambda checked, b=btn: self._sync_chip_selected(b, checked=checked))
        return btn

    @staticmethod
    def _sync_chip_selected(button: QPushButton, *, checked: bool) -> None:
        button.setProperty("selected", checked)
        button.style().unpolish(button)
        button.style().polish(button)

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        accent = palette.get("accent", "#4A90E2")
        card_hover = palette.get("card_hover", "#e9ecef")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        self.setStyleSheet(f"""
            SearchPanel {{
                background-color: {card_bg};
                color: {base_fg};
            }}
        """)

        self.title_label.setStyleSheet(self.title_stylesheet(base_fg, card_border))
        self.summary_label.setStyleSheet(f"color: {secondary_fg}; font-size: 11px; background-color: transparent;")

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                color: {base_fg};
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px;
            }}
        """)

        self.results.setStyleSheet(f"""
            QTreeWidget {{
                color: {base_fg};
                background-color: {card_bg};
                selection-background-color: {accent};
                selection-color: white;
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QTreeWidget::item:hover {{
                background-color: {card_hover};
                color: {base_fg};
            }}
        """)

        # Match-highlight colours: soft amber in both themes, chosen from the
        # panel background's brightness so it reads in light and dark.
        if _is_dark(palette.get("card_bg", "#ffffff")):
            self.delegate.highlight = "#5a4a1e"
            self.delegate.highlight_fg = "#ffe08a"
        else:
            self.delegate.highlight = "#ffe08a"
            self.delegate.highlight_fg = "#000000"
        if self.results.topLevelItemCount():
            self.results.viewport().update()

    # ------------------------------------------------------------------ search

    def _on_project_changed(self, _event_data: dict):
        """Re-run the current query when the project or a note changes."""
        if self.search_input.text().strip():
            self._debounce.start()
        else:
            self._clear_results()

    def run_search(self):
        query = self.search_input.text()
        self._clear_results()

        if not query.strip():
            self.summary_label.setText("")
            return

        if not self.app_state.has_project or not self.app_state.current_project:
            self.summary_label.setText("No project loaded")
            return

        notes = [
            item
            for item in self.app_state.current_project.get_all_items()
            if isinstance(item, Note)
        ]

        try:
            results = search_notes(
                notes,
                query,
                case_sensitive=self.case_button.isChecked(),
                whole_word=self.word_button.isChecked(),
                use_regex=self.regex_button.isChecked(),
            )
        except QueryError as exc:
            self.summary_label.setText(f"Invalid regex: {exc}")
            return

        self._populate(results)

    def _populate(self, results):
        total_matches = sum(r.match_count for r in results)
        if not results:
            self.summary_label.setText("No matches")
            return

        note_word = "note" if len(results) == 1 else "notes"
        match_word = "match" if total_matches == 1 else "matches"
        self.summary_label.setText(f"{total_matches} {match_word} in {len(results)} {note_word}")

        for result in results:
            count = f" ({result.match_count}{'+' if result.truncated else ''})"
            note_item = QTreeWidgetItem([f"📝 {result.note_name}{count}"])
            note_item.setData(0, _ROLE_NOTE_ID, result.note_id)
            # Store the first match so activating the note row still jumps somewhere.
            note_item.setData(0, _ROLE_MATCH, result.matches[0])
            self.results.addTopLevelItem(note_item)

            for match in result.matches:
                child = QTreeWidgetItem(note_item)
                child.setData(0, _ROLE_NOTE_ID, result.note_id)
                child.setData(0, _ROLE_MATCH, match)
                child.setData(0, _ROLE_SNIPPET, self._snippet_for(match))
            note_item.setExpanded(True)

    def _snippet_for(self, match: NoteMatch):
        text, hl_start, hl_end = build_snippet(match)
        label = "title" if match.in_title else f"L{match.line_number}"
        prefix = f"{label}: "
        return (prefix + text, hl_start + len(prefix), hl_end + len(prefix))

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int):
        note_id = item.data(0, _ROLE_NOTE_ID)
        match: Optional[NoteMatch] = item.data(0, _ROLE_MATCH)
        if not note_id:
            return

        # Open (or focus) the note's tab, then ask its editor to reveal the match.
        self.publish_event(UIEvents.TAB_OPEN_REQUESTED, {"item_id": note_id})
        if match is not None and not match.in_title:
            self.publish_event(
                UIEvents.NOTE_REVEAL_MATCH,
                {
                    "note_id": note_id,
                    "line_number": match.line_number,
                    "match_start": match.match_start,
                    "match_end": match.match_end,
                },
            )

    def _clear_results(self):
        self.results.clear()

    def focus_search_input(self):
        """Give keyboard focus to the search box (used when the panel opens)."""
        self.search_input.setFocus()
        self.search_input.selectAll()
