"""Tests for TabContainer._create_tab delegating to TabFactory."""
from unittest.mock import Mock, sentinel

from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.components.tabs.tab_factory import TabFactory


def test_create_tab_delegates_to_the_tab_factory_manager():
    tab_factory = Mock()
    tab_factory.create_tab.return_value = sentinel.tab_widget

    app_context = Mock()
    app_context.get_manager.return_value = tab_factory

    container = TabContainer.__new__(TabContainer)
    container.app_context = app_context

    item = Mock()
    result = container._create_tab(item)

    app_context.get_manager.assert_called_once_with(TabFactory)
    tab_factory.create_tab.assert_called_once_with(app_context, item, parent=container)
    assert result is sentinel.tab_widget
