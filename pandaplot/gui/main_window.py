import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.components.sidebar import CollapsibleSidebar
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.components.sidebar.conditional_panel_manager import ConditionalPanelManager
from pandaplot.gui.components.sidebar.panel_conditions import is_dataset_tab_active, is_dataset_with_analysis_data, should_show_chart_properties, should_show_fit_panel
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.events.event_types import AppEvents, DatasetOperationEvents, UIEvents


class PandaMainWindow(EventBusComponentMixin, QMainWindow):
    def __init__(self, app_context: AppContext):
        super().__init__(event_bus=app_context.event_bus)
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("PandaPlot")
        
        # Initialize MVC components
        self.app_context = app_context

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
        self.app_context.event_bus.subscribe(AppEvents.APP_CLOSING, self.closeEvent)
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
        self.sidebar = CollapsibleSidebar(self.main_splitter, width=250)
        self.main_splitter.addWidget(self.sidebar)

        # Create main content area (right pane) with tab container
        self.tab_container = TabContainer(app_context=self.app_context, parent=self.main_splitter)
        self.tab_container.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        
        self.main_splitter.addWidget(self.tab_container)

        # Set initial splitter sizes: [sidebar_width, remaining_width]
        self.main_splitter.setSizes([250, 1000])
        
        # Create project view panel and connect it to app state
        self.project_view_panel = ProjectViewPanel(self.app_context)
        
        self.sidebar.add_panel("explorer", "📁", self.project_view_panel)
        self.sidebar.show_panel("explorer")
        
        # Connect project view signals to tab container
        # TODO: remove signals
        self.project_view_panel.note_open_requested.connect(self.tab_container.open_note_tab)
        self.project_view_panel.dataset_open_requested.connect(self.tab_container.open_dataset_tab)
        self.project_view_panel.chart_open_requested.connect(self.tab_container.open_chart_tab)
        self.project_view_panel.chart_create_requested.connect(self.tab_container.create_chart_from_dataset)
        self.project_view_panel.plot_tab_requested.connect(self.tab_container.create_plot_tab)
        
        # Initialize conditional panel manager for dynamic sidebar panels
        self.conditional_panel_manager = ConditionalPanelManager(self.sidebar, self.tab_container)
        
        # Connect tab changes to conditional panel manager (centralized)
        self.tab_container.tab_widget.currentChanged.connect(self.conditional_panel_manager.on_tab_changed)
        
        # Create and register transform panel
        self.setup_transform_panel()
        
        # Create and register analysis panel
        self.setup_analysis_panel()
        
        # Create and register chart properties panel
        self.setup_chart_properties_panel()
        
        # Create and register fit panel
        self.setup_fit_panel()
        
        # Connect sidebar settings button to settings dialog
        self.sidebar.icon_bar.settings_requested.connect(self.show_settings_dialog)
    
    def setup_transform_panel(self):
        """Set up the transform panel and register it with conditional panel manager."""
        # TODO: setup should happen somewhere else
        # Create transform panel
        self.transform_panel = TransformPanel(self.app_context)
        
        # Add panel to sidebar (initially hidden)
        self.sidebar.add_panel("transform", "🔧", self.transform_panel)
        
        # Hide the panel button initially until a dataset tab is active
        if "transform" in self.sidebar.icon_bar.panels:
            self.sidebar.icon_bar.panels["transform"].setVisible(False)
        
        # Register with conditional panel manager to show only when dataset tab is active
        self.conditional_panel_manager.register_conditional_panel(
            "transform", 
            is_dataset_tab_active,
            priority=10  # High priority for transform panel
        )
        
        # Force initial evaluation to set correct visibility
        self.conditional_panel_manager.evaluate_panel_visibility()
        
        # Transform panel now uses events instead of signals
    
    def setup_analysis_panel(self):
        """Set up the analysis panel and register it with conditional panel manager."""
        # TODO: setup should happen somewhere else
        # Create analysis panel
        self.analysis_panel = AnalysisPanel(self.app_context)
        
        # Add panel to sidebar (initially hidden)
        self.sidebar.add_panel("analysis", "📊", self.analysis_panel)
        
        # Hide the panel button initially until a dataset tab is active
        if "analysis" in self.sidebar.icon_bar.panels:
            self.sidebar.icon_bar.panels["analysis"].setVisible(False)
        
        # Register with conditional panel manager to show only when dataset tab with analysis data is active
        self.conditional_panel_manager.register_conditional_panel(
            "analysis", 
            is_dataset_with_analysis_data,
            priority=9  # Slightly lower priority than transform panel
        )
        
        # Force initial evaluation to set correct visibility
        self.conditional_panel_manager.evaluate_panel_visibility()
        
        # Analysis panel now uses events instead of signals
    
    def setup_chart_properties_panel(self):
        """Set up the chart properties panel and register it with conditional panel manager."""
        # TODO: setup should happen somewhere else
        # Create chart properties panel
        self.chart_properties_panel = ChartPropertiesPanel(self.app_context)
        
        # Add panel to sidebar (initially hidden)
        self.sidebar.add_panel("chart_properties", "📈", self.chart_properties_panel)
        
        # Hide the panel button initially until appropriate context is active
        if "chart_properties" in self.sidebar.icon_bar.panels:
            self.sidebar.icon_bar.panels["chart_properties"].setVisible(False)
        
        # Register with conditional panel manager to show when appropriate
        self.conditional_panel_manager.register_conditional_panel(
            "chart_properties", 
            should_show_chart_properties,
            priority=8  # Lower priority than analysis panel
        )
        
        # Force initial evaluation to set correct visibility
        self.conditional_panel_manager.evaluate_panel_visibility()
        
        # Note: ChartPropertiesPanel now handles its own events through event bus subscriptions
    
    def setup_fit_panel(self):
        """Set up the fit panel and register it with conditional panel manager."""
        # TODO: setup should happen somewhere else
        # Create fit panel
        self.fit_panel = FitPanel(self.app_context)
        
        # Add panel to sidebar (initially hidden)
        self.sidebar.add_panel("fit", "📐", self.fit_panel)
        
        # Hide the panel button initially until appropriate context is active
        if "fit" in self.sidebar.icon_bar.panels:
            self.sidebar.icon_bar.panels["fit"].setVisible(False)
        
        # Register with conditional panel manager to show when appropriate
        self.conditional_panel_manager.register_conditional_panel(
            "fit", 
            should_show_fit_panel,
            priority=7  # Lower priority than chart properties panel
        )
        
        # Force initial evaluation to set correct visibility
        self.conditional_panel_manager.evaluate_panel_visibility()
        
        # Note: FitPanel now handles its own events through event bus subscriptions
    
    def on_transform_applied(self, dataset_id: str, new_column_name: str):
        """Handle successful transform application."""
        # TODO: transform applied callback should be handled differently
        print(f"Transform applied to dataset {dataset_id}: new column '{new_column_name}'")
        
        # Find and refresh the dataset tab
        current_widget = self.tab_container.tab_widget.currentWidget()
        if current_widget and type(current_widget).__name__ == 'DatasetTab':
            # Use getattr for safe attribute access
            dataset = getattr(current_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'id') and dataset.id == dataset_id:
                # Refresh the current dataset tab
                load_method = getattr(current_widget, 'load_dataset_data', None)
                if callable(load_method):
                    load_method()
                    print(f"Refreshed dataset tab for dataset {dataset_id}")
                    
                    # Also update the transform panel to show new columns
                    if hasattr(self, 'transform_panel'):
                        self.transform_panel.update_column_list()
    
    def on_transform_error(self, error_message: str):
        """Handle transform error."""
        # TODO: transform error callback should be handled differently
        print(f"Transform error: {error_message}")
        # TODO: Show error dialog or status message

    def show_settings_dialog(self):
        """Show the settings dialog."""
        # TODO: move this away from main window
        dialog = SettingsDialog(self.app_context, self)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()
    
    def on_settings_changed(self, settings):
        """Handle settings changes."""
        # TODO: this shouldn't be here, move when refactoring icon bar 
        print(f"Settings changed: {settings}")
        # TODO: Apply settings to the application
    
    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        # TODO: remove unrelevant subscriptions
        # Subscribe to dataset operation events to handle transforms
        self.subscribe_to_event(DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_transform_applied_event)
        
        # Subscribe to UI events for tab changes
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self.on_tab_changed_event)
    
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
        

    def closeEvent(self, event):
        """Handle window close event - clean up matplotlib figures and exit"""
        try:
            # Close all documents and clean up
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            # Force exit even if cleanup fails
            event.accept()
