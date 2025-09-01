import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget

from pandaplot.gui.components import CollapsibleSidebar, MainMenu, TabContainer
from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import ConditionalPanelManager
from pandaplot.gui.components.sidebar.panels.panel_setup_manager import PanelSetupManager

from pandaplot.models.events import AppEvents
from pandaplot.models.events.event_types import ThemeEvents
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.state.app_context import AppContext


class PandaMainWindow(EventBusComponentMixin, QMainWindow):
    def __init__(self, app_context: AppContext):
        super().__init__(event_bus=app_context.event_bus)
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context

        self._init_ui()
        self.setup_event_subscriptions()
        self.logger.info("PandaMainWindow initialized.")

    def _init_ui(self):
        self.setWindowTitle("PandaPlot")

        # Get screen dimensions and set window to maximized
        screen = QScreen.availableGeometry(self.screen())
        self.setGeometry(screen)
        self.showMaximized()

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        main_layout.setSpacing(0)  # Remove spacing between widgets

        self.create_widgets(main_layout)
        
        # Apply initial theme
        self._apply_theme_to_main_window()

    def create_widgets(self, main_layout):
        # Create menu
        self.main_menu = MainMenu(self, self.app_context)
        self.setMenuBar(self.main_menu)

        # Create main horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # TODO: move panel setup somewhere else
        self.panel_setup_manager = PanelSetupManager(self.app_context)
        self.panel_setup_manager.register_default_panels()

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
        # TODO: move this outside of main window
        self.conditional_panel_manager = ConditionalPanelManager(
            self.sidebar, self.tab_container)
        self.panel_setup_manager.add_panels(self.sidebar, self.conditional_panel_manager)

        # Connect tab changes to conditional panel manager (centralized)
        self.tab_container.tab_widget.currentChanged.connect(
            self.conditional_panel_manager.on_tab_changed)
    
    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        self.subscribe_to_event(AppEvents.APP_CLOSING,
                                self.on_app_closing_event)

        # React to theme changes if window-specific adjustments are needed
        self.app_context.event_bus.subscribe(ThemeEvents.THEME_CHANGED, self._on_theme_changed)

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
            # this can happen by executing close all tabs command
            # consider moving the logic inside close command
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

    def _on_theme_changed(self, _data: dict):
        """Handle theme changes by applying appropriate background and font settings."""
        try:
            self._apply_theme_to_main_window()
        except Exception as e:
            self.logger.warning("Failed applying theme to main window: %s", e)

    def _apply_theme_to_main_window(self):
        """Apply theme-specific styling to the main window based on current theme."""
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate background color
        background_color = palette.get('card_bg', '#F5F5F5')
        
        # Apply background to central widget
        central_widget = self.centralWidget()
        central_widget.setStyleSheet(f"QWidget {{ background-color: {background_color}; }}")
            
        self.logger.debug("Applied theme")
            

