"""Regression test for the duplicate `active_tab_changed` connection bug.

`main_window.py` used to explicitly connect
`tab_container.active_tab_changed` to `conditional_panel_manager.on_tab_changed`
even though `ConditionalPanelManager.__init__` already does this itself via
`_connect_tab_events()`. That meant the connection happened twice, so every
panel-visibility condition was evaluated twice per tab switch. The explicit
connect in main_window was removed as the fix; this test locks in that
`ConditionalPanelManager` itself only ever connects once to whatever
`tab_container.active_tab_changed` signal-like object it's given.
"""
from unittest.mock import Mock

from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import (
    ConditionalPanelManager,
)


class _FakeTabContainer:
    """Minimal stand-in exposing just the attribute
    `_connect_tab_events` reads: `active_tab_changed`, a Qt-signal-shaped
    object whose `.connect` we can assert on."""

    def __init__(self):
        self.active_tab_changed = Mock()


def test_connects_to_active_tab_changed_exactly_once():
    sidebar = Mock()
    tab_container = _FakeTabContainer()

    manager = ConditionalPanelManager(sidebar, tab_container)

    tab_container.active_tab_changed.connect.assert_called_once_with(manager.on_tab_changed)
