"""Regression tests for CustomTabBar context-menu lifetime."""

import sys
from unittest.mock import patch

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QMenu, QTabWidget, QWidget

from pandaplot.gui.components.tabs.tab_bar import CustomTabBar, TabHeaderContextMenu


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_tab_header_context_menu_is_deleted_after_closing():
    tab_widget = QTabWidget()
    tab_bar = CustomTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    tab_widget.addTab(QWidget(), "Tab 1")
    position = tab_bar.tabRect(0).center()

    opened: list[TabHeaderContextMenu] = []

    def _exec_returns_immediately(menu: TabHeaderContextMenu, *_args) -> None:
        opened.append(menu)

    with patch.object(TabHeaderContextMenu, "exec", _exec_returns_immediately):
        tab_bar.show_context_menu(position)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(opened) == 1
    assert not shiboken6.isValid(opened[0])
    assert tab_bar.findChildren(QMenu) == []


def test_tab_header_context_menu_real_exec_and_parent_teardown():
    tab_widget = QTabWidget()
    tab_bar = CustomTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    tab_widget.addTab(QWidget(), "Tab 1")
    position = tab_bar.tabRect(0).center()

    closed_tabs: list[int] = []
    tab_bar.tab_close_requested.connect(closed_tabs.append)

    def _trigger_close_and_destroy_menu_during_exec() -> None:
        menus = tab_bar.findChildren(TabHeaderContextMenu)
        assert len(menus) == 1
        menu = menus[0]
        close_action = next(a for a in menu.actions() if a.text() == "Close Tab")
        close_action.trigger()
        menu.close()
        menu.deleteLater()
        QCoreApplication.sendPostedEvents(menu, QEvent.Type.DeferredDelete)

    QTimer.singleShot(0, _trigger_close_and_destroy_menu_during_exec)
    tab_bar.show_context_menu(position)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert closed_tabs == [0]
    assert tab_bar.findChildren(QMenu) == []
