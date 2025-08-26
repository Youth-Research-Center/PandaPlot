import logging

from PySide6.QtWidgets import QVBoxLayout, QWidget

from pandaplot.commands.project.chart import CreateChartCommand
from pandaplot.commands.project.project import (LoadProjectCommand, NewProjectCommand, OpenProjectCommand)
from pandaplot.gui.components.tabs import DatasetTab, NoteTab, ChartTab
from pandaplot.gui.components.tabs.tab import CustomTabWidget
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.models.events import (
    EventBusComponentMixin,
    AnalysisEvents,
    ChartEvents,
    DatasetEvents,
    ProjectEvents,
    UIEvents,
)
from pandaplot.models.project.items import Chart, Dataset, Note
from pandaplot.models.state.app_context import AppContext


class TabContainer(EventBusComponentMixin, QWidget):
    """
    A container widget that manages tabbed content for the main application workspace.
    This component provides a centralized way to manage different tabs like Plot, Data, Transform, and Analysis.
    Supports drag-and-drop reordering and tab closing.
    """

    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self.logger = logging.getLogger(__name__)

        self.app_context = app_context
        # TODO: we shouldn't know about these tab types here
        self.tabs = {}

        self.setup_ui()
        self.create_default_tabs()
        self.setup_event_subscriptions()

    def subscribe_to_multiple_events(self, event_subscriptions: list):
        """Subscribe to multiple events."""
        for event_type, handler in event_subscriptions:
            self.subscribe_to_event(event_type, handler)

    def setup_ui(self):
        """Initialize the UI layout and components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        # Create custom tab widget
        self.tab_widget = CustomTabWidget()

        # Connect close signal and tab change signal
        self.tab_widget.tab_close_requested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        layout.addWidget(self.tab_widget)

    def create_default_tabs(self):
        """Create the default tabs for the application."""
        # Only show Welcome tab if no project is loaded
        if self.app_context and not self.app_context.get_app_state().has_project:
            self.create_welcome_tab()

    def close_tab(self, index):
        """
        Handle tab close request.

        Args:
            index (int): The index of the tab to close
        """
        if index >= 0 and index < self.tab_widget.count():
            # Get tab title before removing
            tab_title = self.tab_widget.tabText(index)

            # Get the widget before removing the tab
            widget = self.tab_widget.widget(index)

            item_id_to_remove = None
            for curr_item_id, curr_tab in self.tabs.items():
                if curr_tab is widget:
                    item_id_to_remove = curr_item_id
                    break
            if item_id_to_remove:
                del self.tabs[item_id_to_remove]

            # Remove the tab
            self.tab_widget.removeTab(index)

            # Clean up the widget
            if widget:
                widget.deleteLater()

            # Check if we need to add a welcome tab (only if no project is loaded and no tabs remain)
            if self.tab_widget.count() == 0 and self.app_context and not self.app_context.get_app_state().has_project:
                self.create_welcome_tab()

            # Publish tab closed event
            self.publish_event(UIEvents.TAB_CLOSED, {
                'tab_index': index,
                'tab_title': tab_title,
                'tab_id': id(widget) if widget else None
            })

    def open_tab(self, item_id):
        if not self.app_context:
            self.logger.warning("Cannot open tab: No app context provided")
            return
        
         # Check if note tab is already open
        if item_id in self.tabs:
            # Switch to existing tab
            existing_tab = self.tabs[item_id]
            try:
                tab_index = self.tab_widget.indexOf(existing_tab)
                if tab_index >= 0:
                    self.tab_widget.setCurrentIndex(tab_index)
                    return
                else:
                    # Tab no longer exists, remove from tracking
                    del self.tabs[item_id]
            except RuntimeError:
                # Qt object has been deleted, remove from tracking
                del self.tabs[item_id]

        # Get note data from project
        if not self.app_context.get_app_state().has_project:
            self.logger.warning("Cannot open note: No project loaded")
            return

        project = self.app_context.get_app_state().current_project
        if not project:
            self.logger.warning("Cannot open item: No project loaded")
            return

        # Find the note item in the project hierarchy
        item = project.find_item(item_id)
        if item is None:
            self.logger.warning("Cannot open item: Item %s not found", item_id)
            return


        try:
            new_tab = self._create_tab(item)

            # Add tab
            tab_index = self.tab_widget.addTab(new_tab, new_tab.get_tab_title())
    
            # Track the tab
            self.tabs[item_id] = new_tab

            # Switch to the new tab
            self.tab_widget.setCurrentIndex(tab_index)
        except Exception as e:
            self.logger.error("Failed to open tab for item %s: %s", item_id, str(e))

    def _create_tab(self, item):
        #TODO: move to a separate factory class
        if item is None:
            raise ValueError("Item cannot be None")
        
        if isinstance(item, Note):
            return NoteTab(self.app_context, item)
        elif isinstance(item, Chart):
            return ChartTab(self.app_context, item)
        elif isinstance(item, Dataset):
            return DatasetTab(self.app_context, item)
        else:
            raise ValueError(f"Unsupported item type, item class {item.__class__.__name__}")

    def update_tab_title(self, tab_widget, new_title: str):
        """Update the title of a specific tab."""
        tab_index = self.tab_widget.indexOf(tab_widget)
        if tab_index >= 0:
            self.tab_widget.setTabText(tab_index, new_title)

    def handle_new_project(self):
        """Handle new project request from welcome tab."""
        if self.app_context:
            command = NewProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def handle_open_project(self):
        """Handle open project request from welcome tab."""
        if self.app_context:
            command = OpenProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def handle_recent_project(self, project_path: str):
        """Handle recent project selection from welcome tab."""
        if self.app_context:
            command = LoadProjectCommand(self.app_context, project_path)
            self.app_context.get_command_executor().execute_command(command)

    def handle_import_data(self):
        """Handle import data request from welcome tab."""
        if self.app_context:
            # Import data requires a project to be loaded first
            if not self.app_context.get_app_state().has_project:
                # Create a new project first
                self.handle_new_project()

            # Show file dialog for CSV import
            from pandaplot.commands.project.dataset.import_csv_command import (
                ImportCsvCommand,
            )
            command = ImportCsvCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def create_welcome_tab(self):
        """Create and add a welcome tab."""
        welcome_tab = WelcomeTab(self.app_context)

        # Connect welcome tab signals
        welcome_tab.new_project_requested.connect(self.handle_new_project)
        welcome_tab.open_project_requested.connect(self.handle_open_project)
        welcome_tab.recent_project_selected.connect(self.handle_recent_project)
        welcome_tab.import_data_requested.connect(self.handle_import_data)

        self.tab_widget.addTab(welcome_tab, welcome_tab.get_tab_title())
        return welcome_tab

    def create_chart_from_dataset(self, dataset_id: str, chart_name: str):
        """Create a new chart from a dataset and open it in a tab."""
        # TODO: remove, needs update on dataset tab
        if not self.app_context:
            self.logger.warning("Cannot create chart: No app context provided")
            return

        app_state = self.app_context.get_app_state()
        if app_state.has_project and app_state.current_project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return

        project = app_state.current_project

        # Verify dataset exists
        if project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return
        dataset_item = project.find_item(dataset_id)
        if not dataset_item:
            self.logger.warning("Cannot create chart: Dataset %s not found", dataset_id)
            return

        command = CreateChartCommand(self.app_context, dataset_id, chart_name, dataset_item.parent_id)
        self.app_context.get_command_executor().execute_command(command)

        chart_id = command.created_chart_id

        if chart_id:
            # TODO: this should be handled on tab container level by listening on new item creation
            return self.open_tab(chart_id)

    def on_project_closed(self):
        """Called when a project is closed - clean up tracking dictionaries and show welcome tab if no tabs are open."""
        # Clear tracking dictionaries since project is closed
        self.tabs.clear()

        if self.tab_widget.count() == 0:
            self.create_welcome_tab()

    def setup_event_subscriptions(self):
        """Setup event subscriptions for this component."""
        self.subscribe_to_multiple_events([
            # Keep existing project events
            (ProjectEvents.PROJECT_CLOSED, lambda _: self.on_project_closed()),

            # Subscribe to dataset events
            (DatasetEvents.DATASET_DATA_CHANGED, self.on_dataset_updated),
            (AnalysisEvents.ANALYSIS_COMPLETED, self.on_analysis_completed),
            (ChartEvents.CHART_CREATED, lambda event_data: self.open_tab(event_data.get('chart_id'))),
            ('ui.chart.open_requested', lambda event_data: self.open_tab(event_data.get('chart_id'))),
            ('ui.note.open_requested', lambda event_data: self.open_tab(
                event_data.get('note_id'))),
            ('ui.dataset.open_requested', lambda event_data: self.open_tab(
                event_data.get('dataset_id')))
        ])

    def on_tab_changed(self, index: int):
        """Handle tab changes and publish event."""
        if index >= 0:
            current_widget = self.tab_widget.widget(index)
            tab_data = self.get_tab_data(current_widget) 

            self.publish_event(UIEvents.TAB_CHANGED, {
                'tab_index': index,
                'tab_type': tab_data['type'],
                'tab_id': tab_data['id'],
                'tab_title': self.tab_widget.tabText(index),
                'dataset_id': tab_data.get('dataset_id'),
                'chart_id': tab_data.get('chart_id'),
                'note_id': tab_data.get('note_id')
            })

    def get_tab_data(self, widget):
        """Get tab data for a widget."""
        if hasattr(widget, 'dataset') and widget.dataset:
            return {
                'type': 'dataset',
                'id': widget.dataset.id,
                'dataset_id': widget.dataset.id
            }
        elif hasattr(widget, 'chart') and widget.chart:
            return {
                'type': 'chart',
                'id': widget.chart.id,
                'chart_id': widget.chart.id
            }
        elif hasattr(widget, 'note') and widget.note:
            return {
                'type': 'note',
                'id': widget.note.id,
                'note_id': widget.note.id
            }
        else:
            return {
                'type': 'other',
                'id': id(widget)
            }

    def on_dataset_updated(self, event_data):
        """Handle dataset update events."""
        dataset_id = event_data.get('dataset_id')
        # Find and refresh the relevant dataset tab
        for tab_id, tab_widget in self.tabs.items():
            if hasattr(tab_widget, 'dataset') and tab_widget.dataset.id == dataset_id:
                if hasattr(tab_widget, 'load_dataset_data'):
                    tab_widget.load_dataset_data()  # Refresh without signal coupling

    def on_analysis_completed(self, event_data):
        """Handle analysis completion events."""
        dataset_id = event_data.get('dataset_id')
        # Find and refresh the relevant dataset tab
        for tab_id, tab_widget in self.tabs.items():
            if hasattr(tab_widget, 'dataset') and tab_widget.dataset.id == dataset_id:
                if hasattr(tab_widget, 'load_dataset_data'):
                    tab_widget.load_dataset_data()  # Refresh to show new analysis column


# TODO: ensure tab name is updated on item name change