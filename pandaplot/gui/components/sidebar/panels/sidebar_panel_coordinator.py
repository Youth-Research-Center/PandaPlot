import logging

from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import (
    ConditionalPanelManager,
)
from pandaplot.gui.components.sidebar.panels.panel_setup_manager import PanelSetupManager
from pandaplot.gui.components.sidebar.sidebar import CollapsibleSidebar
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.models.state.app_context import AppContext


class SidebarPanelCoordinator:
    """Registers default sidebar panels and wires their conditional visibility.

    Keeps this bookkeeping out of the main window, which should only care
    about laying out the sidebar/tab container, not about panel registration.
    """

    def __init__(self, app_context: AppContext):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.panel_setup_manager = PanelSetupManager(app_context)
        self.conditional_panel_manager: ConditionalPanelManager | None = None

    def setup(self, sidebar: CollapsibleSidebar, tab_container: TabContainer) -> ConditionalPanelManager:
        """Register default panels and connect their visibility conditions.

        Returns the ConditionalPanelManager so callers that need it (e.g. for
        the current-tab lookup) don't have to know it's built here.
        """
        self.panel_setup_manager.register_default_panels()
        self.conditional_panel_manager = ConditionalPanelManager(sidebar, tab_container)
        self.panel_setup_manager.add_panels(sidebar, self.conditional_panel_manager)
        return self.conditional_panel_manager
