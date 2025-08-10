from PySide6.QtWidgets import QWidget, QVBoxLayout

from pandaplot.gui.components.tabs.tab import CustomTabWidget
from pandaplot.gui.components.tabs.note_tab import NoteTab
from pandaplot.gui.components.tabs.chart_tab import ChartTab
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.note import Note
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.events.event_types import UIEvents, ProjectEvents, DatasetEvents, AnalysisEvents
from pandaplot.models.state.app_context import AppContext



class TabContainer(EventBusComponentMixin, QWidget):
    """
    A container widget that manages tabbed content for the main application workspace.
    This component provides a centralized way to manage different tabs like Plot, Data, Transform, and Analysis.
    Supports drag-and-drop reordering and tab closing.
    """
    
    def __init__(self, app_context:AppContext, parent=None):
        super().__init__(event_bus=app_context.event_bus, parent=parent)

        self.app_context = app_context
        # TODO: we shouldn't know about these tab types here
        self.note_tabs = {}  # Track note tabs by note_id
        self.chart_tabs = {}  # Track chart tabs by chart_id
        self.dataset_tabs = {}  # Track dataset tabs by dataset_id
        
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
            # Check if tab can be closed
            if not self.can_close_tab(index):
                return
            
            # Get tab title before removing
            tab_title = self.tab_widget.tabText(index)
            
            # Get the widget before removing the tab
            widget = self.tab_widget.widget(index)
            
            # If it's a note tab, clean up the note_tabs dictionary
            if isinstance(widget, NoteTab):
                note_id_to_remove = None
                for note_id, note_tab in self.note_tabs.items():
                    if note_tab is widget:
                        note_id_to_remove = note_id
                        break
                if note_id_to_remove:
                    del self.note_tabs[note_id_to_remove]
            
            # If it's a chart tab, clean up the chart_tabs dictionary
            elif isinstance(widget, ChartTab):
                chart_id_to_remove = None
                for chart_id, chart_tab in self.chart_tabs.items():
                    if chart_tab is widget:
                        chart_id_to_remove = chart_id
                        break
                if chart_id_to_remove:
                    del self.chart_tabs[chart_id_to_remove]
            
            # Clean up dataset_tabs (for QWidget-based dataset tabs)
            dataset_id_to_remove = None
            for dataset_id, dataset_tab in self.dataset_tabs.items():
                if dataset_tab is widget:
                    dataset_id_to_remove = dataset_id
                    break
            if dataset_id_to_remove:
                del self.dataset_tabs[dataset_id_to_remove]
            
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
    
    def add_tab(self, widget, title):
        """
        Add a new tab to the tab widget.
        
        Args:
            widget (QWidget): The widget to add as tab content
            title (str): The title for the tab
            
        Returns:
            int: The index of the added tab
        """
        return self.tab_widget.addTab(widget, title)
    
    def add_closable_tab(self, widget, title):
        """
        Add a new closable tab to the tab widget.
        
        Args:
            widget (QWidget): The widget to add as tab content
            title (str): The title for the tab
            
        Returns:
            int: The index of the added tab
        """
        index = self.tab_widget.addTab(widget, title)
        # The close button is enabled by default when tabsClosable is True
        return index
    
    def remove_tab(self, index):
        """
        Remove a tab at the specified index.
        
        Args:
            index (int): The index of the tab to remove
        """
        self.close_tab(index)
    
    def can_close_tab(self, index):
        """
        Check if a tab can be closed. Now allows closing all tabs.
        
        Args:
            index (int): The index of the tab
            
        Returns:
            bool: True if the tab can be closed, False otherwise
        """
        # Allow closing all tabs - when no tabs remain, we can add new ones later
        return True
    
    def get_current_tab_index(self):
        """
        Get the index of the currently selected tab.
        
        Returns:
            int: The index of the current tab
        """
        return self.tab_widget.currentIndex()
    
    def set_current_tab(self, index):
        """
        Set the current tab by index.
        
        Args:
            index (int): The index of the tab to select
        """
        self.tab_widget.setCurrentIndex(index)
    
    def get_tab_widget(self, index):
        """
        Get the widget at the specified tab index.
        
        Args:
            index (int): The index of the tab
            
        Returns:
            QWidget: The widget at the specified tab
        """
        return self.tab_widget.widget(index)
    
    def get_tab_count(self):
        """
        Get the total number of tabs.
        
        Returns:
            int: The number of tabs
        """
        return self.tab_widget.count()
    
    def set_tab_enabled(self, index, enabled):
        """
        Enable or disable a tab.
        
        Args:
            index (int): The index of the tab
            enabled (bool): Whether the tab should be enabled
        """
        self.tab_widget.setTabEnabled(index, enabled)
    
    def set_tab_visible(self, index, visible):
        """
        Show or hide a tab.
        
        Args:
            index (int): The index of the tab
            visible (bool): Whether the tab should be visible
        """
        self.tab_widget.setTabVisible(index, visible)
    
    def open_note_tab(self, note_id: str, note_name: str):
        """
        Open a note in a new tab or switch to existing tab.
        
        Args:
            note_id (str): The ID of the note to open
            note_name (str): The name of the note
        """
        if not self.app_context:
            print("Cannot open note tab: No app context provided")
            return
        
        # Check if note tab is already open
        if note_id in self.note_tabs:
            # Switch to existing tab
            existing_tab = self.note_tabs[note_id]
            try:
                tab_index = self.tab_widget.indexOf(existing_tab)
                if tab_index >= 0:
                    self.tab_widget.setCurrentIndex(tab_index)
                    return
                else:
                    # Tab no longer exists, remove from tracking
                    del self.note_tabs[note_id]
            except RuntimeError:
                # Qt object has been deleted, remove from tracking
                del self.note_tabs[note_id]
        
        # Get note data from project
        if not self.app_context.get_app_state().has_project:
            print("Cannot open note: No project loaded")
            return
            
        project = self.app_context.get_app_state().current_project
        if not project:
            print("Cannot open note: No project loaded")
            return
            
        # Find the note item in the project hierarchy
        note_item = project.find_item(note_id)
        if not note_item:
            print(f"Cannot open note: Note {note_id} not found")
            return
        
        # Verify it's actually a Note object
        if not isinstance(note_item, Note):
            print(f"Cannot open note: Item {note_id} is not a note")
            return
        
        # Create note tab
        note_tab = NoteTab(self.app_context, note_item)
        note_tab.title_changed.connect(lambda new_title: self.update_tab_title(note_tab, new_title))
        
        # Add tab
        tab_index = self.add_closable_tab(note_tab, note_tab.get_tab_title())
        
        # Track the tab
        self.note_tabs[note_id] = note_tab
        
        # Switch to the new tab
        self.tab_widget.setCurrentIndex(tab_index)
    
    def update_tab_title(self, tab_widget, new_title: str):
        """Update the title of a specific tab."""
        tab_index = self.tab_widget.indexOf(tab_widget)
        if tab_index >= 0:
            self.tab_widget.setTabText(tab_index, new_title)
    
    def close_note_tab(self, note_id: str):
        """Close a specific note tab."""
        if note_id in self.note_tabs:
            note_tab = self.note_tabs[note_id]
            tab_index = self.tab_widget.indexOf(note_tab)
            if tab_index >= 0:
                self.close_tab(tab_index)
            del self.note_tabs[note_id]
    
    def handle_new_project(self):
        """Handle new project request from welcome tab."""
        if self.app_context:
            from pandaplot.commands.project.project.new_project_command import NewProjectCommand
            command = NewProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)
    
    def handle_open_project(self):
        """Handle open project request from welcome tab."""
        if self.app_context:
            from pandaplot.commands.project.project.open_project_command import OpenProjectCommand
            command = OpenProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)
    
    def handle_recent_project(self, project_path: str):
        """Handle recent project selection from welcome tab."""
        if self.app_context:
            from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
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
            from pandaplot.commands.project.dataset.import_csv_command import ImportCsvCommand
            command = ImportCsvCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)
    
    def ensure_welcome_tab_if_empty(self):
        """Ensure there's a welcome tab if no tabs are open."""
        if self.tab_widget.count() == 0:
            self.create_welcome_tab()
    
    def create_welcome_tab(self):
        """Create and add a welcome tab."""
        welcome_tab = WelcomeTab(self.app_context)
        
        # Connect welcome tab signals
        welcome_tab.new_project_requested.connect(self.handle_new_project)
        welcome_tab.open_project_requested.connect(self.handle_open_project)
        welcome_tab.recent_project_selected.connect(self.handle_recent_project)
        welcome_tab.import_data_requested.connect(self.handle_import_data)
        
        self.add_tab(welcome_tab, welcome_tab.get_tab_title())
        return welcome_tab
    
    def create_plot_tab(self):
        """Create and add a plot tab."""
        from PySide6.QtWidgets import QLabel
        
        plot_tab = QWidget()
        plot_layout = QVBoxLayout(plot_tab)
        plot_layout.addWidget(QLabel("Plot Tab - Interactive plotting interface\n\n"
                                   "Features:\n"
                                   "• Column selection for X and Y axes\n"
                                   "• Plot type selection (Line, Scatter, Bar)\n"
                                   "• Chart properties dialog\n"
                                   "• Live plot updates"))
        
        index = self.add_closable_tab(plot_tab, "📊 Plot")
        self.set_current_tab(index)
        return plot_tab
    
    def open_dataset_tab(self, dataset_id: str, dataset_name: str):
        """Open a dataset in a new tab or switch to existing tab."""
        # Check if dataset tab is already open
        if dataset_id in self.dataset_tabs:
            # Switch to existing tab
            existing_tab = self.dataset_tabs[dataset_id]
            try:
                tab_index = self.tab_widget.indexOf(existing_tab)
                if tab_index >= 0:
                    self.tab_widget.setCurrentIndex(tab_index)
                    return existing_tab
                else:
                    # Tab no longer exists, remove from tracking
                    del self.dataset_tabs[dataset_id]
            except RuntimeError:
                # Qt object has been deleted, remove from tracking
                del self.dataset_tabs[dataset_id]

        # Get dataset from project
        if not self.app_context or not self.app_context.get_app_state().has_project:
            print("Cannot open dataset: No project loaded")
            return

        project = self.app_context.get_app_state().current_project
        if not project:
            print("Cannot open dataset: No project loaded")
            return

        # Find the dataset item in the project hierarchy
        dataset_item = project.find_item(dataset_id)
        if not dataset_item:
            print(f"Cannot open dataset: Dataset {dataset_id} not found")
            return

        # Verify it's actually a Dataset object
        from pandaplot.models.project.items.dataset import Dataset
        if not isinstance(dataset_item, Dataset):
            print(f"Cannot open dataset: Item {dataset_id} is not a dataset")
            return

        # Create dataset tab using our new DatasetTab
        from pandaplot.gui.components.tabs.dataset_tab import DatasetTab
        dataset_tab = DatasetTab(self.app_context, dataset_item)
        
        # Track the dataset tab
        self.dataset_tabs[dataset_id] = dataset_tab
        
        # Add tab
        index = self.add_closable_tab(dataset_tab, f"📊 {dataset_item.name}")
        self.set_current_tab(index)
        return dataset_tab
    
    def open_chart_tab(self, chart_id: str, chart_name: str):
        """Open a chart in a new tab or switch to existing tab."""
        if not self.app_context:
            print("Cannot open chart tab: No app context provided")
            return

        # Check if chart tab is already open
        if chart_id in self.chart_tabs:
            # Switch to existing tab
            existing_tab = self.chart_tabs[chart_id]
            try:
                tab_index = self.tab_widget.indexOf(existing_tab)
                if tab_index >= 0:
                    self.tab_widget.setCurrentIndex(tab_index)
                    return existing_tab
                else:
                    # Tab no longer exists, remove from tracking
                    del self.chart_tabs[chart_id]
            except RuntimeError:
                # Qt object has been deleted, remove from tracking
                del self.chart_tabs[chart_id]

        # Get chart data from project
        if not self.app_context.get_app_state().has_project:
            print("Cannot open chart: No project loaded")
            return
            
        project = self.app_context.get_app_state().current_project
        if not project:
            print("Cannot open chart: No project found")
            return
            
        chart_item = project.find_item(chart_id)
        if not chart_item or not isinstance(chart_item, Chart):
            print(f"Cannot open chart: Chart {chart_id} not found")
            return

        # Create chart tab
        chart_tab = ChartTab(self.app_context, chart_item)

        # Track the chart tab
        self.chart_tabs[chart_id] = chart_tab

        # Add tab
        tab_index = self.add_closable_tab(chart_tab, chart_tab.get_tab_title())

        # Switch to the new tab
        self.set_current_tab(tab_index)
        return chart_tab

    def create_chart_from_dataset(self, dataset_id: str, chart_name: str):
        """Create a new chart from a dataset and open it in a tab."""
        if not self.app_context:
            print("Cannot create chart: No app context provided")
            return

        app_state = self.app_context.get_app_state()
        if app_state.has_project and app_state.current_project is None:
            print("Cannot create chart: No project loaded")
            return

        project = app_state.current_project

        # Verify dataset exists
        if project is None:
            print("Cannot create chart: No project loaded")
            return
        dataset_item = project.find_item(dataset_id)
        if not dataset_item:
            print(f"Cannot create chart: Dataset {dataset_id} not found")
            return

        # Use CreateChartCommand to properly add chart to project hierarchy
        from pandaplot.commands.project.chart.create_chart_command import CreateChartCommand
        command = CreateChartCommand(self.app_context, dataset_id, chart_name, dataset_item.parent_id)
        self.app_context.get_command_executor().execute_command(command)

        chart_id = command.created_chart_id

        if chart_id:
            # TODO: this should be handled on tab container level by listening on new item creation
            return self.open_chart_tab(chart_id, chart_name)
    
    def on_project_loaded(self):
        """Called when a project is loaded - welcome tab stays open."""
        # Welcome tab now stays open until manually closed
        # No automatic closing when project is loaded
        pass
    
    def on_project_closed(self):
        """Called when a project is closed - clean up tracking dictionaries and show welcome tab if no tabs are open."""
        # Clear tracking dictionaries since project is closed
        self.note_tabs.clear()
        self.chart_tabs.clear()
        
        if self.tab_widget.count() == 0:
            self.create_welcome_tab()
    
    def on_project_loaded_event(self, event_data):
        """Event handler for when a project is loaded."""
        self.on_project_loaded()
    
    def on_project_closed_event(self, event_data):
        """Event handler for when a project is closed."""
        self.on_project_closed()
    
    def setup_event_subscriptions(self):
        """Setup event subscriptions for this component."""
        self.subscribe_to_multiple_events([
            # Keep existing project events
            (ProjectEvents.PROJECT_LOADED, self.on_project_loaded_event),
            (ProjectEvents.PROJECT_CLOSED, self.on_project_closed_event),
            
            # Subscribe to dataset events 
            (DatasetEvents.DATASET_DATA_CHANGED, self.on_dataset_updated),
            (AnalysisEvents.ANALYSIS_COMPLETED, self.on_analysis_completed),
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
        for tab_id, tab_widget in self.dataset_tabs.items():
            if hasattr(tab_widget, 'dataset') and tab_widget.dataset.id == dataset_id:
                if hasattr(tab_widget, 'load_dataset_data'):
                    tab_widget.load_dataset_data()  # Refresh without signal coupling
    
    def on_analysis_completed(self, event_data):
        """Handle analysis completion events."""
        dataset_id = event_data.get('dataset_id')
        # Find and refresh the relevant dataset tab
        for tab_id, tab_widget in self.dataset_tabs.items():
            if hasattr(tab_widget, 'dataset') and tab_widget.dataset.id == dataset_id:
                if hasattr(tab_widget, 'load_dataset_data'):
                    tab_widget.load_dataset_data()  # Refresh to show new analysis column
