from typing import override

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.gui.components.tabs.dataset.dataset_table_view import DatasetTableView
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


class DatasetTab(PWidget):
    """
    Tab widget for displaying dataset contents in an editable table format.
    """

    def __init__(self, app_context: AppContext, dataset: Dataset, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.dataset = dataset
        
        # Initialize the pandas table model and view
        self.table_model = PandasTableModel(app_context, dataset, self)
        self.table_view = DatasetTableView(app_context, self.table_model, self)
        
        self.logger.debug("Initializing DatasetTab for dataset: %s (ID: %s)",
                          dataset.name, dataset.id)

        self._initialize()
        self.load_dataset_data()

    def setup_event_subscriptions(self):
        """Set up event subscriptions for dataset updates."""
        # Subscribe to dataset operation events
        self.subscribe_to_event(
            DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_dataset_column_added)
        self.subscribe_to_event(
            DatasetOperationEvents.DATASET_ROW_ADDED, self.on_dataset_row_added)
        self.subscribe_to_event(
            DatasetOperationEvents.DATASET_BULK_UPDATE, self.on_dataset_bulk_update)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to all components."""
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        card_bg = palette.get('card_bg', '#f8f9fa')
        card_hover = palette.get('card_hover', '#e9ecef')
        card_border = palette.get('card_border', '#dee2e6')
        base_fg = palette.get('base_fg', '#000000')
        secondary_fg = palette.get('secondary_fg', '#555555')
        accent = palette.get('accent', '#4A90E2')
        
        # Derive accent color variants for interaction states
        from PySide6.QtGui import QColor
        accent_color = QColor(accent)
        if accent_color.isValid():
            accent_hover = accent_color.darker(110).name()
            accent_pressed = accent_color.darker(125).name()
        else:
            accent_hover = accent
            accent_pressed = accent
        
        # Apply styling to action buttons
        for btn in [self.create_chart_btn, self.export_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {accent};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {accent_hover};
                }}
                QPushButton:pressed {{
                    background-color: {accent_pressed};
                }}
                QPushButton:disabled {{
                    background-color: {secondary_fg};
                }}
            """)
        
        # Apply styling to table view
        self.table_view.setStyleSheet(f"""
            QTableView {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                selection-background-color: {card_hover};
                gridline-color: {card_border};
                color: {base_fg};
            }}
            QTableView::item {{
                padding: 5px;
                border-bottom: 1px solid {card_border};
            }}
            QTableView::item:selected {{
                background-color: {card_hover};
                color: {accent};
            }}
            QTableView::item:focus {{
                border: 2px solid {accent};
                background-color: {card_hover};
            }}
            QHeaderView::section {{
                background-color: {card_hover};
                padding: 8px;
                border: 1px solid {card_border};
                font-weight: bold;
                color: {base_fg};
            }}
        """)
        
        # Apply styling to action buttons
        self.create_chart_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {accent_pressed};
            }}
        """)
        
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e7e34;
            }
            QPushButton:pressed {
                background-color: #155724;
            }
        """)

    def on_dataset_column_added(self, event_data):
        """Handle when a column is added to any dataset."""
        self.logger.debug(
            "DatasetTab received DATASET_COLUMN_ADDED event: %s", event_data)
        dataset_id = event_data.get('dataset_id')
        self.logger.debug("Event dataset_id: %s, current dataset_id: %s",
                          dataset_id, self.dataset.id if self.dataset else 'None')
        if dataset_id == self.dataset.id:
            self.logger.info(
                "Column added event received for dataset %s", dataset_id)
            self.load_dataset_data()  # Refresh the table to show new column
        else:
            self.logger.debug(
                "Dataset IDs don't match, ignoring DATASET_COLUMN_ADDED event for dataset %s", dataset_id)

    def on_dataset_row_added(self, event_data):
        """Handle when a row is added to any dataset."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.dataset.id:
            self.logger.info(
                "Row added event received for dataset %s", dataset_id)
            self.load_dataset_data()  # Refresh the table to show new row

    def on_dataset_bulk_update(self, event_data):
        """Handle bulk updates to any dataset."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.dataset.id:
            self.logger.info(
                "Bulk update event received for dataset %s", dataset_id)
            self.load_dataset_data()  # Refresh the table

    @override
    def _init_ui(self):
        """Initialize the UI layout and components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Add the table view directly - no edit mode toggle needed
        main_layout.addWidget(self.table_view)

        # Actions section
        self.create_actions_section(main_layout)

    def create_actions_section(self, layout):
        """Create action buttons section."""
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 5, 0, 0)

        # Create chart button
        self.create_chart_btn = QPushButton("📈 Create Chart from Data")
        self.create_chart_btn.clicked.connect(self.create_chart_from_data)
        actions_layout.addWidget(self.create_chart_btn)

        # Export data button
        self.export_btn = QPushButton("💾 Export Data")
        self.export_btn.clicked.connect(self.export_data)
        actions_layout.addWidget(self.export_btn)

        # Add stretch to push buttons to the left
        actions_layout.addStretch()

        layout.addWidget(actions_frame)

    def _on_editing_started(self, index: "QModelIndex"):
        """Handle when cell editing starts."""
        self.logger.debug("Editing started at row %d, col %d", index.row(), index.column())

    def _on_editing_finished(self, index: "QModelIndex"):
        """Handle when cell editing finishes."""
        self.logger.debug("Editing finished at row %d, col %d", index.row(), index.column())



    def load_dataset_data(self):
        """Load and display the dataset data in the table view."""
        self.logger.debug("Loading dataset data for: %s",
                          self.dataset.name if self.dataset else 'None')
        
        # The PandasTableModel automatically handles data loading when dataset is set
        # Log the data shape for debugging
        df = self.dataset.data
        if df is not None:
            rows, cols = df.shape
            self.logger.info("Successfully loaded dataset '%s' with %d rows and %d columns",
                             self.dataset.name, rows, cols)
            
            # Auto-resize columns to fit content optimally
            self._auto_resize_columns()
        else:
            self.logger.info("Dataset '%s' has no data to display", self.dataset.name)

    def _auto_resize_columns(self):
        """Auto-resize columns to optimal width based on content and headers."""
        if not self.table_view or not self.dataset or self.dataset.data is None:
            return
            
        # Use ResizeToContents for optimal sizing that considers both headers and content
        self.table_view.resizeColumnsToContents()
        
        # Set reasonable minimum and maximum column widths
        header = self.table_view.horizontalHeader()
        for column in range(self.table_view.model().columnCount()):
            current_width = header.sectionSize(column)
            
            # Set minimum width to ensure header text is visible (especially with two-line headers)
            min_width = 100  # Minimum width to show header content
            
            # Set maximum width to prevent extremely wide columns
            max_width = 300  # Maximum width for readability
            
            # Apply constraints
            optimal_width = max(min_width, min(current_width, max_width))
            header.resizeSection(column, optimal_width)
        
        self.logger.debug("Auto-resized columns for dataset '%s'", self.dataset.name)

    def get_tab_title(self) -> str:
        """Get the title for this tab."""
        title = f"📊 {self.dataset.name}"
        return title

    def create_chart_from_data(self):
        """Create a chart from this dataset."""
        if not self.app_context:
            return

        # Request chart creation through the main window's signal system
        # We can emit a signal that will be handled by the tab container
        chart_name = f"Chart from {self.dataset.name}"
        self.logger.info(
            "Requesting chart creation from dataset %s", self.dataset.id)

        # Get the tab container from parent hierarchy
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'create_chart_from_dataset'):
            parent_widget = parent_widget.parent()

        if parent_widget and hasattr(parent_widget, 'create_chart_from_dataset'):
            try:
                create_method = getattr(
                    parent_widget, 'create_chart_from_dataset', None)
                if callable(create_method):
                    create_method(self.dataset.id, chart_name)
                else:
                    self.logger.warning(
                        "create_chart_from_dataset not callable on parent for dataset %s", self.dataset.id)
            except Exception as e:
                self.logger.error(
                    "Error creating chart from dataset %s: %s", self.dataset.id, e, exc_info=True)
        else:
            self.logger.warning(
                "Could not find tab container to create chart for dataset %s", self.dataset.id)

    def export_data(self):
        """Export the dataset to a file."""
        # TODO: Implement data export functionality
        self.logger.info(
            "Export data requested for dataset %s (TODO not implemented)",
            self.dataset.id,
        )
