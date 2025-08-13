import logging
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.dataset.add_column_command import AddColumnCommand
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.events.mixins import EventBusComponentMixin
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


class DatasetTab(EventBusComponentMixin, QWidget):
    """
    Tab widget for displaying dataset contents in an editable table format.
    """
    
    def __init__(self, app_context: AppContext, dataset: Dataset, parent=None):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.dataset = dataset
        self.original_data = None  # Store original data for comparison
        self.is_editing_enabled = False  # Track editing state
        self.has_unsaved_changes = False  # Track if data has been modified
        
        self.logger.debug("Initializing DatasetTab for dataset: %s (ID: %s)", 
                         dataset.name, dataset.id)
        
        self.setup_ui()
        self.load_dataset_data()
        self.setup_event_subscriptions()
    
    def subscribe_to_event(self, event_type: str, handler):
        """Subscribe to an event - delegate to the event bus component."""
        # Use the inherited method from EventBusComponentMixin
        super().subscribe_to_event(event_type, handler)
    
    def setup_event_subscriptions(self):
        """Set up event subscriptions for dataset updates."""
        # Subscribe to dataset operation events
        self.subscribe_to_event(DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_dataset_column_added)
        self.subscribe_to_event(DatasetOperationEvents.DATASET_ROW_ADDED, self.on_dataset_row_added)
        self.subscribe_to_event(DatasetOperationEvents.DATASET_BULK_UPDATE, self.on_dataset_bulk_update)
        self.subscribe_to_event(DatasetEvents.DATASET_DATA_CHANGED, self.on_dataset_data_changed)
    
    def on_dataset_column_added(self, event_data):
        """Handle when a column is added to any dataset."""
        print(f"DEBUG: DatasetTab received DATASET_COLUMN_ADDED event: {event_data}")
        dataset_id = event_data.get('dataset_id')
        print(f"DEBUG: Event dataset_id: {dataset_id}, Current dataset_id: {self.dataset.id if self.dataset else 'None'}")
        if dataset_id == self.dataset.id:
            print(f"DatasetTab: Column added event received for dataset {dataset_id}")
            self.load_dataset_data()  # Refresh the table to show new column
        else:
            print("DEBUG: Dataset IDs don't match, ignoring event")
    
    def on_dataset_row_added(self, event_data):
        """Handle when a row is added to any dataset."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.dataset.id:
            print(f"DatasetTab: Row added event received for dataset {dataset_id}")
            self.load_dataset_data()  # Refresh the table to show new row
    
    def on_dataset_bulk_update(self, event_data):
        """Handle bulk updates to any dataset."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.dataset.id:
            print(f"DatasetTab: Bulk update event received for dataset {dataset_id}")
            self.load_dataset_data()  # Refresh the table
    
    def on_dataset_data_changed(self, event_data):
        """Handle when dataset data changes."""
        dataset_id = event_data.get('dataset_id')
        if dataset_id == self.dataset.id:
            print(f"DatasetTab: Dataset data changed event received for dataset {dataset_id}")
            self.load_dataset_data()  # Refresh the table
    
    def setup_ui(self):
        """Initialize the UI layout and components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header section
        self.create_header_section(main_layout)
        
        # Data table section
        self.create_data_table_section(main_layout)
        
        # Actions section
        self.create_actions_section(main_layout)
    
    def create_header_section(self, layout):
        """Create the header section with dataset info."""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        header_layout.setSpacing(5)
        
        # Dataset name
        name_label = QLabel(f"📊 {self.dataset.name}")
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #333333;")
        header_layout.addWidget(name_label)
        
        # Dataset info
        self.info_label = QLabel("Loading dataset information...")
        self.info_label.setStyleSheet("color: #666666;")
        header_layout.addWidget(self.info_label)
        
        # Source file if available
        if hasattr(self.dataset, 'source_file') and self.dataset.source_file:
            source_label = QLabel(f"Source: {self.dataset.source_file}")
            source_label.setStyleSheet("color: #888888; font-size: 9pt;")
            header_layout.addWidget(source_label)
        
        layout.addWidget(header_frame)
    
    def create_data_table_section(self, layout):
        """Create the data table section with editing controls."""
        # Control bar for table options
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 5)
        
        # Edit mode toggle
        self.edit_mode_checkbox = QCheckBox("Enable Editing")
        self.edit_mode_checkbox.stateChanged.connect(self.toggle_edit_mode)
        control_layout.addWidget(self.edit_mode_checkbox)
        
        # Status label
        self.edit_status_label = QLabel("Read-only mode")
        self.edit_status_label.setStyleSheet("color: #666666; font-style: italic;")
        control_layout.addWidget(self.edit_status_label)
        
        # Spacer
        control_layout.addStretch()
        
        # Save changes button (initially hidden)
        self.save_changes_btn = QPushButton("💾 Save Changes")
        self.save_changes_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.save_changes_btn.clicked.connect(self.save_changes)
        self.save_changes_btn.setVisible(False)
        control_layout.addWidget(self.save_changes_btn)
        
        # Discard changes button (initially hidden)
        self.discard_changes_btn = QPushButton("↶ Discard Changes")
        self.discard_changes_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        self.discard_changes_btn.clicked.connect(self.discard_changes)
        self.discard_changes_btn.setVisible(False)
        control_layout.addWidget(self.discard_changes_btn)
        
        layout.addWidget(control_frame)
        
        # Table widget
        self.table_widget = QTableWidget()
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                selection-background-color: #e3f2fd;
                gridline-color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QTableWidget::item:focus {
                border: 2px solid #007bff;
                background-color: #fff3cd;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                color: #333333;
            }
        """)
        
        # Configure table properties
        self.table_widget.setSortingEnabled(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table_widget.itemChanged.connect(self.on_item_changed)
        
        # Configure headers to resize
        horizontal_header = self.table_widget.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal_header.setStretchLastSection(True)
        
        vertical_header = self.table_widget.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table_widget)
    
    def create_actions_section(self, layout):
        """Create action buttons section."""
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 5, 0, 0)
        
        # Create chart button
        create_chart_btn = QPushButton("📈 Create Chart from Data")
        create_chart_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        create_chart_btn.clicked.connect(self.create_chart_from_data)
        actions_layout.addWidget(create_chart_btn)
        
        # Export data button
        export_btn = QPushButton("💾 Export Data")
        export_btn.setStyleSheet("""
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
        export_btn.clicked.connect(self.export_data)
        actions_layout.addWidget(export_btn)
        
        # Add column button
        add_column_btn = QPushButton("➕ Add Column")
        add_column_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
        """)
        add_column_btn.clicked.connect(self.add_column_to_dataset)
        actions_layout.addWidget(add_column_btn)
        
        # Add row button
        add_row_btn = QPushButton("➕ Add Row")
        add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        add_row_btn.clicked.connect(self.add_row_to_dataset)
        actions_layout.addWidget(add_row_btn)
        
        # Add stretch to push buttons to the left
        actions_layout.addStretch()
        
        layout.addWidget(actions_frame)
    
    def load_dataset_data(self):
        """Load and display the dataset data."""
        self.logger.debug("Loading dataset data for: %s", self.dataset.name if self.dataset else 'None')
        try:
            # Get the pandas DataFrame from the dataset
            df = self.dataset.data
            self.logger.debug("Dataset data shape: %s", df.shape if df is not None else 'None')
            
            if df is None or df.empty:
                self.info_label.setText("No data available")
                self.logger.info("Dataset '%s' has no data to display", self.dataset.name)
                return
            
            # Store original data for comparison and reset functionality
            self.original_data = df.copy()
            
            # Update info label
            rows, cols = df.shape
            self.info_label.setText(f"Shape: {rows:,} rows × {cols} columns")
            self.logger.debug("Updated info label for dataset '%s': %d rows × %d columns", 
                            self.dataset.name, rows, cols)
            
            # Configure table dimensions
            max_rows = min(rows, 1000)  # Limit to first 1000 rows for performance
            self.table_widget.setRowCount(max_rows)
            self.table_widget.setColumnCount(cols)
            
            # Set column headers
            column_names = list(df.columns)
            self.logger.debug("Setting column headers for dataset '%s': %s", 
                            self.dataset.name, column_names)
            self.table_widget.setHorizontalHeaderLabels(column_names)
            
            # Temporarily disconnect itemChanged signal to avoid triggering during loading
            self.table_widget.itemChanged.disconnect()
            
            # Populate table data
            data_errors = 0
            for row in range(max_rows):
                for col in range(cols):
                    try:
                        value = df.iloc[row, col]
                        # Handle different data types
                        if pd.isna(value):
                            display_value = ""
                        elif isinstance(value, (int, float)):
                            display_value = str(value)
                        else:
                            display_value = str(value)
                        
                        item = QTableWidgetItem(display_value)
                        # Set editable based on current edit mode
                        if self.is_editing_enabled:
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        
                        # Store original value as user data for change detection
                        item.setData(Qt.ItemDataRole.UserRole, display_value)
                        
                        self.table_widget.setItem(row, col, item)
                    except Exception as e:
                        # Handle any data conversion issues
                        data_errors += 1
                        self.logger.warning("Data conversion error at row %d, col %d in dataset '%s': %s", 
                                          row, col, self.dataset.name, str(e))
                        item = QTableWidgetItem(f"Error: {str(e)}")
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        self.table_widget.setItem(row, col, item)
            
            if data_errors > 0:
                self.logger.warning("Dataset '%s' had %d data conversion errors during loading", 
                                  self.dataset.name, data_errors)
            
            # Reconnect itemChanged signal
            self.table_widget.itemChanged.connect(self.on_item_changed)
            
            # Update info if we're showing limited rows
            if rows > 1000:
                self.info_label.setText(f"Shape: {rows:,} rows × {cols} columns (showing first 1,000 rows)")
                self.logger.info("Dataset '%s': Displaying first 1,000 of %d rows for performance", 
                               self.dataset.name, rows)
            
            self.logger.info("Successfully loaded dataset '%s' with %d rows and %d columns", 
                           self.dataset.name, rows, cols)
            
        except Exception as e:
            error_msg = f"Failed to load dataset data: {str(e)}"
            self.logger.error("Error loading dataset '%s': %s", 
                            self.dataset.name if self.dataset else 'Unknown', error_msg, exc_info=True)
            self.info_label.setText(error_msg)
            # Show error to user
            QMessageBox.critical(self, "Dataset Load Error", error_msg)
            
            # Resize columns to content
            self.table_widget.resizeColumnsToContents()
            
        except Exception as e:
            self.info_label.setText(f"Error loading data: {str(e)}")
            print(f"DatasetTab: Error loading dataset data: {e}")
    
    def toggle_edit_mode(self, state):
        """Toggle between read-only and editable modes."""
        self.is_editing_enabled = state == Qt.CheckState.Checked.value
        
        # Update all table items
        for row in range(self.table_widget.rowCount()):
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                if item:
                    if self.is_editing_enabled:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        item.setBackground(Qt.GlobalColor.white)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setBackground(Qt.GlobalColor.transparent)
        
        # Update status label
        if self.is_editing_enabled:
            self.edit_status_label.setText("Edit mode - Click any cell to modify")
            self.edit_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        else:
            self.edit_status_label.setText("Read-only mode")
            self.edit_status_label.setStyleSheet("color: #666666; font-style: italic;")
            
        # Hide save/discard buttons if switching to read-only and no changes
        if not self.is_editing_enabled and not self.has_unsaved_changes:
            self.save_changes_btn.setVisible(False)
            self.discard_changes_btn.setVisible(False)
    
    def on_item_changed(self, item):
        """Handle when a table item is changed."""
        if not self.is_editing_enabled:
            return
            
        # Get original value
        original_value = item.data(Qt.ItemDataRole.UserRole)
        current_value = item.text()
        
        # Check if the value actually changed
        if current_value != original_value:
            self.has_unsaved_changes = True
            self.save_changes_btn.setVisible(True)
            self.discard_changes_btn.setVisible(True)
            self.edit_status_label.setText("⚠️ Unsaved changes")
            self.edit_status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            
            # Mark changed item with different background
            item.setBackground(Qt.GlobalColor.yellow)
            
            # Publish data changed event
            self.publish_event(DatasetOperationEvents.DATASET_ROW_UPDATED, {
                'dataset_id': self.dataset.id,
                'dataset_name': self.dataset.name,
                'row_index': item.row(),
                'column_index': item.column(),
                'old_value': original_value,
                'new_value': current_value
            })
    
    def save_changes(self):
        """Save the current table data back to the dataset."""
        try:
            # Get current data from table
            rows = self.table_widget.rowCount()
            cols = self.table_widget.columnCount()
            
            # Get column names
            column_names = []
            for col in range(cols):
                header_item = self.table_widget.horizontalHeaderItem(col)
                column_names.append(header_item.text() if header_item else f"Column_{col}")
            
            # Create new DataFrame with modified data
            data_dict = {}
            for col in range(cols):
                column_data = []
                column_name = column_names[col]
                
                # Determine original column dtype
                if self.original_data is not None and column_name in self.original_data.columns:
                    original_dtype = self.original_data[column_name].dtype
                else:
                    original_dtype = 'object'  # Default to object type
                
                for row in range(rows):
                    item = self.table_widget.item(row, col)
                    if item:
                        cell_value = item.text()
                        
                        # Handle empty cells
                        if cell_value == "":
                            if pd.api.types.is_numeric_dtype(original_dtype):
                                column_data.append(np.nan)
                            else:
                                column_data.append("")
                        else:
                            # Try to convert to original dtype
                            try:
                                if pd.api.types.is_integer_dtype(original_dtype):
                                    column_data.append(int(float(cell_value)))
                                elif pd.api.types.is_float_dtype(original_dtype):
                                    column_data.append(float(cell_value))
                                elif pd.api.types.is_bool_dtype(original_dtype):
                                    column_data.append(cell_value.lower() in ['true', '1', 'yes'])
                                else:
                                    column_data.append(str(cell_value))
                            except (ValueError, TypeError):
                                # If conversion fails, store as string
                                column_data.append(str(cell_value))
                    else:
                        column_data.append(np.nan if pd.api.types.is_numeric_dtype(original_dtype) else "")
                
                data_dict[column_name] = column_data
            
            # Create new DataFrame
            modified_df = pd.DataFrame(data_dict)
            
            # If we had more rows in original data (due to 1000 row limit), preserve them
            if self.original_data is not None and len(self.original_data) > 1000:
                # Keep the unchanged rows beyond 1000
                unchanged_rows = self.original_data.iloc[1000:].copy()
                modified_df = pd.concat([modified_df, unchanged_rows], ignore_index=True)
            
            # Update dataset
            self.dataset.set_data(modified_df)
            
            # Update original data reference
            self.original_data = modified_df.copy()
            
            # Reset change tracking
            self.has_unsaved_changes = False
            self.save_changes_btn.setVisible(False)
            self.discard_changes_btn.setVisible(False)
            self.edit_status_label.setText("✅ Changes saved")
            self.edit_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            
            # Reset item backgrounds and update user data
            for row in range(rows):
                for col in range(cols):
                    item = self.table_widget.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.white if self.is_editing_enabled else Qt.GlobalColor.transparent)
                        item.setData(Qt.ItemDataRole.UserRole, item.text())
            
            # Publish bulk update event
            self.publish_event(DatasetOperationEvents.DATASET_BULK_UPDATE, {
                'dataset_id': self.dataset.id,
                'dataset_name': self.dataset.name,
                'updated_rows': rows,
                'updated_columns': cols,
                'operation': 'save_changes'
            })
            
            # Show success message
            QMessageBox.information(self, "Changes Saved", 
                                  f"Successfully saved changes to '{self.dataset.name}'")
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", 
                               f"Failed to save changes:\n{str(e)}")
            print(f"DatasetTab: Error saving changes: {e}")
    
    def discard_changes(self):
        """Discard all unsaved changes and reload original data."""
        try:
            # Ask for confirmation
            reply = QMessageBox.question(self, "Discard Changes",
                                       "Are you sure you want to discard all unsaved changes?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Reload original data
                self.load_dataset_data()
                
                # Reset change tracking
                self.has_unsaved_changes = False
                self.save_changes_btn.setVisible(False)
                self.discard_changes_btn.setVisible(False)
                self.edit_status_label.setText("Changes discarded" if self.is_editing_enabled else "Read-only mode")
                self.edit_status_label.setStyleSheet("color: #28a745; font-weight: bold;" if self.is_editing_enabled else "color: #666666; font-style: italic;")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to discard changes:\n{str(e)}")
            print(f"DatasetTab: Error discarding changes: {e}")
    
    def get_tab_title(self) -> str:
        """Get the title for this tab."""
        title = f"📊 {self.dataset.name}"
        if self.has_unsaved_changes:
            title += " *"  # Add asterisk to indicate unsaved changes
        return title
    
    def create_chart_from_data(self):
        """Create a chart from this dataset."""
        if not self.app_context:
            return
        
        # Request chart creation through the main window's signal system
        # We can emit a signal that will be handled by the tab container
        chart_name = f"Chart from {self.dataset.name}"
        print(f"DatasetTab: Requesting chart creation from dataset {self.dataset.id}")
        
        # Get the tab container from parent hierarchy
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, 'create_chart_from_dataset'):
            parent_widget = parent_widget.parent()
        
        if parent_widget and hasattr(parent_widget, 'create_chart_from_dataset'):
            # Found the tab container, call its method directly
            parent_widget.create_chart_from_dataset(self.dataset.id, chart_name)
        else:
            print("DatasetTab: Could not find tab container to create chart")
    
    def export_data(self):
        """Export the dataset to a file."""
        # TODO: Implement data export functionality
        print("DatasetTab: Export data functionality - TODO")
    
    def add_column_to_dataset(self):
        """Add a new column to the dataset."""
        if not self.app_context:
            return
        
        
        command = AddColumnCommand(self.app_context, self.dataset.id)
        success = self.app_context.get_command_executor().execute_command(command)
        
        if success:
            # Reload the dataset data to show the new column
            self.load_dataset_data()
            print(f"DatasetTab: Added column to dataset {self.dataset.id}")
        else:
            print(f"DatasetTab: Failed to add column to dataset {self.dataset.id}")
    
    def add_row_to_dataset(self):
        """Add a new row to the dataset."""
        if not self.app_context:
            return
        
        from pandaplot.commands.project.dataset.add_row_command import AddRowCommand
        
        command = AddRowCommand(self.app_context, self.dataset.id)
        success = self.app_context.get_command_executor().execute_command(command)
        
        if success:
            # Reload the dataset data to show the new row
            self.load_dataset_data()
            print(f"DatasetTab: Added row to dataset {self.dataset.id}")
        else:
            print(f"DatasetTab: Failed to add row to dataset {self.dataset.id}")
    
    def get_dataset_id(self) -> str:
        """Get the dataset ID."""
        return self.dataset.id
