"""ProjectViewPanelContextManager is a persistent, reused QMenu instance
(unlike the dataset cell/column/row context menus, which are built fresh per
right-click) -- it must rebuild its stylesheet from current theme tokens
each time it's shown, or it stays stuck at whatever theme was active when
the panel first constructed it."""
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

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
