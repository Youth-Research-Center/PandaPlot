"""Tests for the Help window."""

import logging
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest

from pandaplot.gui.dialogs.help.help_window import HelpWindow
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.help_catalog import HelpCatalog
from pandaplot.services.help.help_types import HelpCategory, HelpTopic
from pandaplot.services.theme.theme_manager import ThemeManager

_PALETTE = {"card_bg": "#FFFFFF", "base_fg": "#000000", "card_border": "#DDDDDD", "accent": "#4A90E2", "secondary_fg": "#555555"}


def _topics() -> list[HelpTopic]:
    return [
        HelpTopic(
            id="stats.t",
            title="Alpha test",
            category=HelpCategory.STATISTICS,
            summary="Compares means.",
            related=("fit.line",),
        ),
        HelpTopic(id="stats.u", title="Beta test", category=HelpCategory.STATISTICS, summary="Compares ranks.", keywords=("nonparametric",)),
        HelpTopic(id="fit.line", title="Linear fit", category=HelpCategory.FITTING, summary="Fits a straight line."),
    ]


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = dict(_PALETTE)
    ctx.get_manager.side_effect = lambda manager_type, *a, **k: theme_manager if manager_type is ThemeManager else Mock()
    return ctx


@pytest.fixture
def window(qtbot, app_context):
    win = HelpWindow(app_context, catalog=HelpCatalog(_topics()))
    qtbot.addWidget(win)
    return win


def _category_titles(win: HelpWindow) -> list[str]:
    return [win.tree.topLevelItem(i).text(0) for i in range(win.tree.topLevelItemCount())]


def _leaf_titles(win: HelpWindow) -> list[str]:
    return [item.text(0) for item in win._topic_items()]


def test_tree_is_grouped_by_category_in_enum_order(window):
    assert _category_titles(window) == [HelpCategory.STATISTICS.value, HelpCategory.FITTING.value]
    assert _leaf_titles(window) == ["Alpha test", "Beta test", "Linear fit"]


def test_category_nodes_are_not_selectable(window):
    category_item = window.tree.topLevelItem(0)

    assert not category_item.flags() & Qt.ItemFlag.ItemIsSelectable


def test_window_is_modeless_top_level_window(window):
    assert not window.isModal()
    assert window.windowFlags() & Qt.WindowType.Window
    assert window.windowTitle() == "PandaPlot Help"
    assert window.search_edit.placeholderText() == "Search help…"
    assert window.search_edit.isClearButtonEnabled()


def test_first_topic_is_shown_initially(window):
    assert "Alpha test" in window.browser.toPlainText()


def test_search_filters_tree_and_expands_categories(window):
    window.search_edit.setText("ranks")

    assert _leaf_titles(window) == ["Beta test"]
    assert _category_titles(window) == [HelpCategory.STATISTICS.value]
    assert window.tree.topLevelItem(0).isExpanded()
    assert "Beta test" in window.browser.toPlainText()


def test_search_matches_keywords(window):
    window.search_edit.setText("nonparametric")

    assert _leaf_titles(window) == ["Beta test"]


def test_search_with_no_match_shows_empty_state(window):
    window.search_edit.setText("zzzz")

    assert window.tree.topLevelItemCount() == 0
    assert "No topics match ‘zzzz’" in window.browser.toPlainText()


def test_empty_state_escapes_query(window):
    window.search_edit.setText("<b>zz")

    assert "No topics match ‘<b>zz’" in window.browser.toPlainText()


def test_clearing_search_restores_tree_and_keeps_current_topic(window):
    window.show_topic("fit.line")
    window.search_edit.setText("straight")
    assert _leaf_titles(window) == ["Linear fit"]

    window.search_edit.clear()

    assert _leaf_titles(window) == ["Alpha test", "Beta test", "Linear fit"]
    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "fit.line"
    assert "Linear fit" in window.browser.toPlainText()


def test_clearing_after_no_match_restores_a_topic(window):
    window.search_edit.setText("zzzz")

    window.search_edit.clear()

    assert len(_leaf_titles(window)) == 3
    assert "Alpha test" in window.browser.toPlainText()


def test_show_topic_selects_expands_and_renders(window):
    window.show_topic("fit.line")

    item = window.tree.currentItem()
    assert item.data(0, Qt.ItemDataRole.UserRole) == "fit.line"
    assert item.parent().isExpanded()
    assert "Fits a straight line." in window.browser.toPlainText()


def test_show_topic_none_selects_first_topic(window):
    window.show_topic("fit.line")

    window.show_topic(None)

    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "stats.t"


def test_unknown_topic_id_falls_back_to_first_and_logs_warning(window, caplog):
    window.show_topic("fit.line")

    with caplog.at_level(logging.WARNING):
        window.show_topic("nope.nothing")

    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "stats.t"
    assert any("nope.nothing" in record.getMessage() for record in caplog.records)


def test_none_topic_id_does_not_log_warning(window, caplog):
    with caplog.at_level(logging.WARNING):
        window.show_topic(None)

    assert not caplog.records


def test_show_topic_clears_filter_that_hides_target(window):
    window.search_edit.setText("ranks")
    assert _leaf_titles(window) == ["Beta test"]

    window.show_topic("fit.line")

    assert window.search_edit.text() == ""
    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "fit.line"
    assert "Linear fit" in window.browser.toPlainText()


def test_help_link_navigates_to_related_topic(window):
    window.show_topic("stats.t")

    window._on_anchor_clicked(QUrl("help:fit.line"))

    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "fit.line"
    assert "Fits a straight line." in window.browser.toPlainText()


def test_rendered_related_link_is_present(window):
    window.show_topic("stats.t")

    assert "help:fit.line" in window.browser.toHtml()


def test_help_link_clears_filter_hiding_target(window):
    window.show_topic("stats.t")
    window.search_edit.setText("means")
    assert _leaf_titles(window) == ["Alpha test"]

    window._on_anchor_clicked(QUrl("help:fit.line"))

    assert window.search_edit.text() == ""
    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "fit.line"


def test_non_help_link_is_ignored(window):
    window.show_topic("stats.t")

    window._on_anchor_clicked(QUrl("https://example.com/"))

    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "stats.t"


def test_unknown_help_link_is_ignored_with_warning(window, caplog):
    window.show_topic("stats.t")

    with caplog.at_level(logging.WARNING):
        window._on_anchor_clicked(QUrl("help:missing.topic"))

    assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "stats.t"
    assert any("missing.topic" in record.getMessage() for record in caplog.records)


def test_escape_closes_window(qtbot, window):
    window.show()
    qtbot.waitExposed(window)

    QTest.keyClick(window, Qt.Key.Key_Escape)

    assert not window.isVisible()


def test_close_button_closes_window(qtbot, window):
    window.show()
    qtbot.waitExposed(window)

    window.close_btn.click()

    assert not window.isVisible()


def test_window_is_not_deleted_on_close(qtbot, window):
    window.show()
    window.close()

    assert not window.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    window.show()
    assert window.isVisible()


def test_down_arrow_in_search_focuses_first_visible_topic(qtbot, window):
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    window.search_edit.setText("fit")
    window.search_edit.setFocus()

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    handled = window.eventFilter(window.search_edit, event)

    assert handled
    qtbot.waitUntil(window.tree.hasFocus, timeout=2000)
    assert window.tree.currentItem().text(0) == "Linear fit"


def test_down_arrow_with_no_results_is_not_consumed(window):
    window.search_edit.setText("zzzz")
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)

    assert not window.eventFilter(window.search_edit, event)


def test_accessible_names_are_set(window):
    assert window.search_edit.accessibleName()
    assert window.tree.accessibleName()
    assert window.browser.accessibleName()
    assert window.search_edit.accessibleDescription()
    assert window.tree.accessibleDescription()
    assert window.browser.accessibleDescription()


def test_browser_does_not_open_links_itself(window):
    assert not window.browser.openLinks()
    assert not window.browser.openExternalLinks()


def test_theme_change_rerenders_current_topic(window, app_context):
    window.show_topic("fit.line")
    app_context.get_manager(ThemeManager).get_surface_palette.return_value = {**_PALETTE, "card_bg": "#101010", "base_fg": "#eeeeee"}

    window._on_theme_changed({})

    assert "#101010" in window.browser.toHtml().lower()
    assert "Linear fit" in window.browser.toPlainText()


def test_empty_catalog_works(qtbot, app_context):
    win = HelpWindow(app_context, catalog=HelpCatalog([]))
    qtbot.addWidget(win)

    win.show_topic(None)

    assert win.tree.topLevelItemCount() == 0
    assert "No help topics are available." in win.browser.toPlainText()


def test_default_catalog_is_get_help_catalog(qtbot, app_context, monkeypatch):
    monkeypatch.setattr("pandaplot.gui.dialogs.help.help_window.get_help_catalog", lambda: HelpCatalog(_topics()))
    win = HelpWindow(app_context)
    qtbot.addWidget(win)

    assert _leaf_titles(win) == ["Alpha test", "Beta test", "Linear fit"]
