"""Tests for SidebarPanelCoordinator.setup wiring.

SidebarPanelCoordinator.setup() is the single place that (a) registers the
default sidebar panels via PanelSetupManager and (b) builds the
ConditionalPanelManager that wires their conditional visibility to tab
changes. PanelSetupManager is patched out here since register_default_panels
constructs real panel widgets (needs a live AppContext/QWidget tree) that
are irrelevant to verifying the coordinator's own wiring.
"""
from unittest.mock import Mock, patch

from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import (
    ConditionalPanelManager,
)
from pandaplot.gui.components.sidebar.panels.sidebar_panel_coordinator import (
    SidebarPanelCoordinator,
)


class _FakeTabContainer:
    def __init__(self):
        self.active_tab_changed = Mock()


@patch("pandaplot.gui.components.sidebar.panels.sidebar_panel_coordinator.PanelSetupManager")
def test_setup_registers_default_panels_and_returns_connected_manager(mock_setup_manager_cls):
    mock_setup_manager = mock_setup_manager_cls.return_value

    app_context = Mock()
    sidebar = Mock()
    tab_container = _FakeTabContainer()

    coordinator = SidebarPanelCoordinator(app_context)
    result = coordinator.setup(sidebar, tab_container)

    mock_setup_manager.register_default_panels.assert_called_once_with()
    assert isinstance(result, ConditionalPanelManager)
    mock_setup_manager.add_panels.assert_called_once_with(sidebar, result)
    assert coordinator.conditional_panel_manager is result

    # The regression this guards against: main_window.py used to also
    # explicitly connect tab_container.active_tab_changed to
    # conditional_panel_manager.on_tab_changed, on top of the connection
    # ConditionalPanelManager already makes itself -- double-evaluating
    # every panel visibility condition per tab switch. Since the
    # coordinator is the only thing constructing ConditionalPanelManager
    # here, exactly one connection must exist on the signal.
    tab_container.active_tab_changed.connect.assert_called_once_with(result.on_tab_changed)
