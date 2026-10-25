"""ProjectViewPanelContextManager is a persistent, reused QMenu instance
(unlike the dataset cell/column/row context menus, which are built fresh per
right-click) -- it must rebuild its stylesheet from current theme tokens
each time it's shown, or it stays stuck at whatever theme was active when
the panel first constructed it."""
import sys
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QWidget

from pandaplot.gui.components.sidebar.project.project_context_manager import (
    ProjectViewPanelContextManager,
)
from pandaplot.services.theme.theme_manager import ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_show_context_menu_restyles_from_current_theme():
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.side_effect = [
        "QMenu { background-color: #FFFFFF; }",
        "QMenu { background-color: #2A2C2E; }",
    ]
    app_context = Mock()
    app_context.get_manager.return_value = theme_manager
    app_state = Mock()
    app_state.has_project = False  # short-circuits before .exec() is reached
    app_context.get_app_state.return_value = app_state

    parent = QWidget()
    menu = ProjectViewPanelContextManager(
        parent, app_context, Mock(), lambda pos: None, lambda pos: pos)

    menu.show_context_menu(None)
    assert menu.styleSheet() == "QMenu { background-color: #FFFFFF; }"

    menu.show_context_menu(None)
    assert menu.styleSheet() == "QMenu { background-color: #2A2C2E; }"


@pytest.mark.parametrize(
    ("item_type", "visible"),
    [("dataset", True), ("folder", False)],
)
def test_measurement_analysis_action_is_available_only_for_datasets(item_type, visible):
    app_context = Mock()
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = ""
    app_context.get_manager.return_value = theme_manager
    app_state = Mock()
    app_state.has_project = True
    app_context.get_app_state.return_value = app_state

    item = QTreeWidgetItem()
    item.setData(0, Qt.ItemDataRole.UserRole, {"type": item_type})
    parent = QWidget()
    menu = ProjectViewPanelContextManager(
        parent, app_context, Mock(), lambda _position: item, lambda position: position,
    )

    with patch.object(menu, "exec"):
        menu.show_context_menu(None)

    assert menu.analyze_measurements_action.isVisible() is visible


def test_measurement_analysis_action_is_hidden_when_tree_item_has_no_data():
    app_context = Mock()
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = ""
    app_context.get_manager.return_value = theme_manager
    app_state = Mock()
    app_state.has_project = True
    app_context.get_app_state.return_value = app_state

    item = QTreeWidgetItem()
    parent = QWidget()
    menu = ProjectViewPanelContextManager(
        parent, app_context, Mock(), lambda _position: item, lambda position: position,
    )

    with patch.object(menu, "exec"):
        menu.show_context_menu(None)

    assert not menu.analyze_measurements_action.isVisible()
