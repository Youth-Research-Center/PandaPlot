import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.components.sidebar import CollapsibleSidebar

from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import ConditionalPanelManager

from pandaplot.gui.components.sidebar.panels.panel_setup_manager import PanelSetupManager
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.models.events.event_types import (
    AppEvents,
)
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.state.app_context import AppContext




class PandaMainWindow(EventBusComponentMixin, QMainWindow):
    def __init__(self, app_context: AppContext):
        super().__init__(event_bus=app_context.event_bus)
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("PandaPlot")

        # Initialize MVC components
        self.app_context = app_context

        # Initialize panels
        # TODO: move elsewhere
        self.panel_setup_manager = PanelSetupManager(self.app_context)
        self.panel_setup_manager.register_default_panels()
        
        # Get screen dimensions and set window to maximized
        screen = QScreen.availableGeometry(self.screen())
        self.setGeometry(screen)
        self.showMaximized()

        # Create central widget
        central_widget = QWidget()
        central_widget.setStyleSheet("QWidget { background-color: #F5F5F5; }")
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        main_layout.setSpacing(0)  # Remove spacing between widgets

        self.create_widgets(main_layout)
        self.setup_event_subscriptions()
        self.panel_setup_manager.add_panels(self.sidebar, self.conditional_panel_manager)
        self.logger.info("PandaMainWindow initialized.")

    def create_widgets(self, main_layout):
        # Create menu
        self.main_menu = MainMenu(self, self.app_context)
        # TODO: move menu styling into menu
        self.main_menu.setStyleSheet("""
            QMenuBar {
                background-color: #F0F0F0;
                color: black;
                border-bottom: 1px solid #D0D0D0;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
                margin: 2px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #4A90E2;
                color: white;
            }
            QMenuBar::item:pressed {
                background-color: #357ABD;
                color: white;
            }
            QMenu {
                background-color: white;
                border: 1px solid #C0C0C0;
                color: black;
                margin: 2px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                margin: 1px;
            }
            QMenu::item:selected {
                background-color: #4A90E2;
                color: white;
            }
            QMenu::item:pressed {
                background-color: #357ABD;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #C0C0C0;
                margin: 2px 10px;
            }
        """)
        self.setMenuBar(self.main_menu)

        # Create main horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Create project manager (left pane) with enhanced styling
        self.sidebar = CollapsibleSidebar(self.app_context, self.main_splitter, width=250)
        self.main_splitter.addWidget(self.sidebar)

        # Create main content area (right pane) with tab container
        self.tab_container = TabContainer(
            app_context=self.app_context, parent=self.main_splitter)
        self.tab_container.setStyleSheet(
            "background-color: white; border: 1px solid #ccc;")

        self.main_splitter.addWidget(self.tab_container)

        # Set initial splitter sizes: [sidebar_width, remaining_width]
        self.main_splitter.setSizes([250, 1000])

        # Initialize conditional panel manager for dynamic sidebar panels
        self.conditional_panel_manager = ConditionalPanelManager(
            self.sidebar, self.tab_container)

        # Connect tab changes to conditional panel manager (centralized)
        self.tab_container.tab_widget.currentChanged.connect(
            self.conditional_panel_manager.on_tab_changed)
    
    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        self.subscribe_to_event(AppEvents.APP_CLOSING,
                                self.on_app_closing_event)

        # React to theme changes if window-specific adjustments are needed
        # TODO: implement theme changed callback
        self.app_context.event_bus.subscribe('theme.changed', lambda _: self.logger.debug(
            "Theme changed event received in main window"))


    # --- Application Closing Handling -----------------------------------------------------
    # event_data required by event bus signature
    def on_app_closing_event(self, event_data: dict):
        """Handle app closing event from the internal event bus.

        This should initiate the normal Qt window close sequence which will emit a
        QCloseEvent and invoke the overridden closeEvent below with a proper event object.
        We avoid doing cleanup work here to prevent duplication and to ensure the
        correct event type is passed to the Qt closeEvent handler.
        """
        self.logger.debug(
            "Received app.closing event via event bus; initiating Qt close()")

        # Mark closing state to avoid re-entrancy if event bus emission triggers close()
        self._is_closing = True
        self.logger.info("Application close event triggered")
        try:
            # Close all documents and clean up
            self.logger.debug("Starting application cleanup process")

            # TODO: Implement cleanup logic here
            # we need to ask for saving open modified files/projects
            # we need to cleanup matplotlib charts to avoid memory leaks

            # Log cleanup completion
            self.logger.info("Application cleanup completed successfully")

        except Exception as e:
            self.logger.error("Error during cleanup: %s",
                              str(e), exc_info=True)
            # Force exit even if cleanup fails
            self.logger.warning(
                "Forcing application exit despite cleanup errors")
        finally:
            # Cleanup flag
            self._is_closing = False
        self.close()

