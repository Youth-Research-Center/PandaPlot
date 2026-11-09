"""Regression tests for CustomTabBar context-menu lifetime."""

import sys
from unittest.mock import patch

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
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
