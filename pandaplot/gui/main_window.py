import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.components.sidebar import CollapsibleSidebar
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import (
    ChartPropertiesPanel,
)
from pandaplot.gui.components.sidebar.conditional_panel_manager import (
    ConditionalPanelManager,
)
from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.sidebar.panel_conditions import (
    is_dataset_tab_active,
    is_dataset_with_analysis_data,
    should_show_chart_properties,
    should_show_fit_panel,
)
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.models.events.event_types import (
    AppEvents,
    DatasetOperationEvents,
    UIEvents,
)
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.state.app_context import AppContext


class PanelSetupManager:
    def __init__(self):
        self.panels : list[dict] = []

    def register_panel(self, panel:QWidget, name, icon, visibility_condition):
        self.panels.append({
            "panel": panel,
            "name": name,
            "icon": icon,
            "visibility_condition": visibility_condition
        })

    def add_panels(self, sidebar:CollapsibleSidebar, panel_manager:ConditionalPanelManager):
        for priority, panel_info in enumerate(self.panels):
            sidebar.add_panel(panel_info["name"], panel_info["icon"], panel_info["panel"])
            panel_manager.register_conditional_panel(panel_info["name"], panel_info["visibility_condition"], priority)
        panel_manager.evaluate_panel_visibility()

class PandaMainWindow(EventBusComponentMixin, QMainWindow):
    def __init__(self, app_context: AppContext):
        super().__init__(event_bus=app_context.event_bus)
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("PandaPlot")

        # Initialize MVC components
        self.app_context = app_context

        # Initialize panels
        # TODO: move elsewhere
        self.panel_setup_manager = PanelSetupManager()
        
        # Create project view panel and connect it to app state
        self.panel_setup_manager.register_panel(ProjectViewPanel(self.app_context), "explorer", "📁", lambda _: True)
        self.panel_setup_manager.register_panel(TransformPanel(self.app_context), "transform", "🔧", is_dataset_tab_active)
        self.panel_setup_manager.register_panel(AnalysisPanel(self.app_context), "analysis", "📊", is_dataset_with_analysis_data) # probably should just be dataset tab
        self.panel_setup_manager.register_panel(ChartPropertiesPanel(self.app_context), "chart_properties", "📈", should_show_chart_properties)
        self.panel_setup_manager.register_panel(FitPanel(self.app_context), "fit", "📐", should_show_fit_panel)
        
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
        
    def on_transform_applied(self, dataset_id: str, new_column_name: str):
        """Handle successful transform application."""
        # TODO: transform applied callback should be handled differently
        self.logger.info(
            "Transform applied to dataset %s: new column '%s'", dataset_id, new_column_name)

        # Find and refresh the dataset tab
        current_widget = self.tab_container.tab_widget.currentWidget()
        if current_widget and type(current_widget).__name__ == 'DatasetTab':
            # Use getattr for safe attribute access
            dataset = getattr(current_widget, 'dataset', None)
            if dataset and getattr(dataset, 'id', None) == dataset_id:
                load_method = getattr(
                    current_widget, 'load_dataset_data', None)
                if callable(load_method):
                    load_method()
                    self.logger.debug(
                        "Refreshed dataset tab for dataset %s", dataset_id)

                    # Also update the transform panel to show new columns
                    if hasattr(self, 'transform_panel'):
                        self.transform_panel.update_column_list()

    def on_transform_error(self, error_message: str):
        """Handle transform error."""
        # TODO: transform error callback should be handled differently
        self.logger.error("Transform error: %s", error_message)
        # TODO: Show error dialog or status message

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        # TODO: remove unrelevant subscriptions
        # Subscribe to dataset operation events to handle transforms
        self.subscribe_to_event(AppEvents.APP_CLOSING,
                                self.on_app_closing_event)
        self.subscribe_to_event(
            DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_transform_applied_event)

        # Subscribe to UI events for tab changes
        self.subscribe_to_event(UIEvents.TAB_CHANGED,
                                self.on_tab_changed_event)
        # React to theme changes if window-specific adjustments are ever needed
        self.app_context.event_bus.subscribe('theme.changed', lambda _: self.logger.debug(
            "Theme changed event received in main window"))

    def on_transform_applied_event(self, event_data):
        """Handle transform applied events from the event system."""
        # TODO: this shouldn't be in main window
        dataset_id = event_data.get('dataset_id')
        column_name = event_data.get('column_name')
        if dataset_id and column_name:
            self.on_transform_applied(dataset_id, column_name)

    def on_tab_changed_event(self, event_data):
        """Handle tab changed events from the event system."""
        # TODO: this shouldn't be in main window
        # Update transform panel context when tabs change
        if hasattr(self, 'transform_panel'):
            current_widget = self.tab_container.tab_widget.currentWidget()
            if current_widget and type(current_widget).__name__ == 'DatasetTab':
                self.transform_panel.set_active_dataset(current_widget)
            else:
                self.transform_panel.set_active_dataset(None)

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
