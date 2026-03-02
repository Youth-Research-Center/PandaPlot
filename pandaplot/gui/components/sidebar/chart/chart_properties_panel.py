"""Chart properties side panel for configuring chart appearance and data."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QPushButton, QLineEdit,
    QGroupBox, QScrollArea,
    QTabWidget, QListWidget
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, List, override

from pandaplot.commands.project.chart import (
    AddSeriesCommand, ApplyChartPropertiesCommand, RemoveSeriesCommand,
)
from pandaplot.gui.components.sidebar.chart.axes_tab import AxesTab
from pandaplot.gui.components.sidebar.chart.legend_tab import LegendTab
from pandaplot.gui.components.sidebar.chart.style_tab import StyleTab
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.chart.chart_configuration import (
    ChartConfiguration, ChartType,
)
from pandaplot.models.chart.chart_style_manager import ChartStyleManager
from pandaplot.models.events import UIEvents, ChartEvents, ProjectEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.project.items import Dataset
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartPropertiesPanel(PWidget):
    """Side panel for configuring chart properties."""

    chart_created = Signal(str)  # chart_id
    chart_updated = Signal(str)  # chart_id

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.command_executor = app_context.command_executor
        self.style_manager = ChartStyleManager()
        self.current_project = None
        self.current_chart_id: Optional[str] = None
        self.current_chart = None  # Current Chart object being edited
        self.datasets: List = []
        # Internal flags/state for safe UI updates
        self._updating_controls: bool = False  # Guard to prevent feedback loops
        self._pending_label: str = ""        # Buffer while user types label
        self._has_unsaved_changes: bool = False

        self._initialize()
        self._connect_signals()

    @override
    def _init_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        self.title_label = QLabel("📊 Chart Properties")
        layout.addWidget(self.title_label)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # Chart info section (basic chart settings)
        self._create_chart_info_section(content_layout)

        # Data Series Management section (moved above tabs)
        self._create_series_management_section(content_layout)

        # Tab widget for organizing other properties
        self.tab_widget = QTabWidget()

        # Style tab
        self.style_tab = StyleTab(self.app_context)
        self.tab_widget.addTab(self.style_tab, "Style")

        # Axes tab
        self.axes_tab = AxesTab()
        self.tab_widget.addTab(self.axes_tab, "Axes")

        # Legend tab
        self.legend_tab = LegendTab(self.app_context)
        self.tab_widget.addTab(self.legend_tab, "Legend")

        content_layout.addWidget(self.tab_widget)
        # Add stretch so tab area uses available space and buttons (outside scroll) stay fixed
        content_layout.addStretch(1)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # Buttons (outside scroll so they're always visible)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 6, 0, 0)
        button_layout.setSpacing(8)

        self.status_label = QLabel("")
        self.status_label.setMinimumHeight(30)
        self.apply_button = QPushButton("Apply")
        self.reset_button = QPushButton("Cancel")

        self.apply_button.setObjectName("chartApplyButton")
        self.reset_button.setObjectName("chartCancelButton")

        for btn in (self.apply_button, self.reset_button):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)

        button_layout.addWidget(self.status_label)
        button_layout.addStretch(1)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        layout.addLayout(button_layout)

    @override
    def _apply_theme(self):
        """Apply theme styling to all components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        # Get theme colors with fallbacks
        card_bg = palette.get('card_bg', '#ffffff')
        card_border = palette.get('card_border', '#dee2e6')
        base_fg = palette.get('base_fg', '#333333')
        card_hover = palette.get('card_hover', '#e5f3ff')

        # Apply theme to main widget
        self.setStyleSheet(f"""
            ChartPropertiesPanel {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 9pt;
                color: {base_fg};
                margin-top: 5px;
                padding-top: 10px;
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: {card_bg};
            }}
        """)

        # Title label with improved styling
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {base_fg};
                padding: 5px;
                background-color: {card_border};
                border-radius: 3px;
            }}
        """)

        # Tab widget with theme-aware colors
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {card_border};
                top: 1px;
                background: {card_bg};
            }}
            QTabBar::tab {{
                background: {card_hover};
                border: 1px solid {card_border};
                border-bottom: none;
                padding: 4px 8px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: {base_fg};
            }}
            QTabBar::tab:selected {{
                background: {card_bg};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                background: {card_hover};
            }}
        """)

        # Main action buttons
        self._apply_button_styling()

        # Series management buttons
        self._apply_series_button_styling()

        # Update all color buttons
        self._update_color_buttons()

    def _update_color_buttons(self):
        """Update all ColorButton instances with current theme."""
        self.style_tab.update_color_buttons()
        self.legend_tab.update_color_buttons()

    def _apply_button_styling(self):
        """Apply theme styling to main action buttons."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        # Get colors with fallbacks
        accent = palette.get('accent', '#4CAF50')
        secondary_fg = palette.get('secondary_fg', '#666666')
        card_hover = palette.get('card_hover', '#e5f3ff')
        base_fg = palette.get('base_fg', '#333333')
        card_border = palette.get('card_border', '#dee2e6')
        card_bg = palette.get('card_bg', '#ffffff')

        # Primary button (Apply)
        primary_style = f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                padding: 6px 14px;
                border: none;
                border-radius: 4px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {card_hover};
                color: {base_fg};
            }}
            QPushButton:pressed {{
                background-color: {card_border};
            }}
            QPushButton:disabled {{
                background-color: {secondary_fg};
                color: #999999;
            }}
        """
        self.apply_button.setStyleSheet(primary_style)

        # Secondary button (Cancel)
        secondary_style = f"""
            QPushButton {{
                background-color: {card_hover};
                color: {base_fg};
                padding: 6px 14px;
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {card_bg};
            }}
            QPushButton:pressed {{
                background-color: {card_border};
            }}
            QPushButton:disabled {{
                background-color: {card_hover};
                color: {secondary_fg};
            }}
        """
        self.reset_button.setStyleSheet(secondary_style)

    def _apply_series_button_styling(self):
        """Apply theme styling to series management buttons."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        # Get colors with fallbacks
        accent = palette.get('accent', '#4CAF50')
        secondary_fg = palette.get('secondary_fg', '#666666')
        card_hover = palette.get('card_hover', '#e5f3ff')
        base_fg = palette.get('base_fg', '#333333')
        card_border = palette.get('card_border', '#dee2e6')
        card_bg = palette.get('card_bg', '#ffffff')

        # Add series button (primary style)
        add_style = f"""
            QPushButton {{
                background: {accent};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {card_hover};
                color: {base_fg};
            }}
            QPushButton:disabled {{
                background: {secondary_fg};
            }}
        """
        self.add_series_button.setStyleSheet(add_style)

        # Remove series button (secondary style)
        remove_style = f"""
            QPushButton {{
                background: {card_hover};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {card_bg};
            }}
            QPushButton:disabled {{
                background: {card_hover};
                color: {secondary_fg};
            }}
        """
        self.remove_series_button.setStyleSheet(remove_style)

    def _create_chart_info_section(self, layout):
        """Create the basic chart information section."""
        # Chart info group
        info_group = QGroupBox("Chart Information")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("Title:"), 0, 0)
        self.title_edit = QLineEdit()
        info_layout.addWidget(self.title_edit, 0, 1)

        info_layout.addWidget(QLabel("Chart Type:"), 1, 0)
        self.chart_type_combo = QComboBox()
        for chart_type in ChartType:
            self.chart_type_combo.addItem(chart_type.value.title(), chart_type)
        info_layout.addWidget(self.chart_type_combo, 1, 1)

        layout.addWidget(info_group)

    def _create_series_management_section(self, layout):
        """Create the data series management section."""
        # Data Series group
        series_group = QGroupBox("Data Series")
        series_layout = QVBoxLayout(series_group)

        # Series list and buttons row
        list_row = QHBoxLayout()
        self.series_list = QListWidget()
        self.series_list.setMaximumHeight(140)
        self.series_list.currentRowChanged.connect(self._on_series_selection_changed)
        list_row.addWidget(self.series_list, 1)

        buttons_col = QVBoxLayout()
        self.add_series_button = QPushButton("Add Series")
        self.add_series_button.setMinimumHeight(28)
        self.add_series_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_series_button.clicked.connect(self._add_series)
        buttons_col.addWidget(self.add_series_button)

        self.remove_series_button = QPushButton("Remove")
        self.remove_series_button.setMinimumHeight(28)
        self.remove_series_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_series_button.clicked.connect(self._remove_series)
        self.remove_series_button.setEnabled(False)
        buttons_col.addWidget(self.remove_series_button)
        buttons_col.addStretch(1)
        list_row.addLayout(buttons_col)
        series_layout.addLayout(list_row)

        # Series configuration group
        series_config_group = QGroupBox("Series Configuration")
        series_config_layout = QGridLayout(series_config_group)

        series_config_layout.addWidget(QLabel("Dataset:"), 0, 0)
        self.dataset_combo = QComboBox()
        series_config_layout.addWidget(self.dataset_combo, 0, 1)

        series_config_layout.addWidget(QLabel("X Column:"), 1, 0)
        self.x_column_combo = QComboBox()
        series_config_layout.addWidget(self.x_column_combo, 1, 1)

        series_config_layout.addWidget(QLabel("Y Column:"), 2, 0)
        self.y_column_combo = QComboBox()
        series_config_layout.addWidget(self.y_column_combo, 2, 1)

        series_config_layout.addWidget(QLabel("Label:"), 3, 0)
        self.series_label_edit = QLineEdit()
        series_config_layout.addWidget(self.series_label_edit, 3, 1)

        # Disable series configuration initially
        series_config_group.setEnabled(False)
        self.series_config_group = series_config_group
        series_layout.addWidget(series_config_group)
        layout.addWidget(series_group)

    def _connect_signals(self):
        """Connect widget signals."""
        self.dataset_combo.currentTextChanged.connect(self._on_dataset_changed)
        self.apply_button.clicked.connect(self._on_apply)
        self.reset_button.clicked.connect(self._on_reset)

        # Connect chart-level configuration changes
        self.chart_type_combo.currentIndexChanged.connect(self._on_chart_config_changed)
        self.title_edit.textChanged.connect(self._on_chart_config_changed)
        self.axes_tab.axes_changed.connect(self._on_chart_config_changed)
        self.legend_tab.legend_changed.connect(self._on_chart_config_changed)

        # Connect series configuration change signals
        self.x_column_combo.currentTextChanged.connect(self._on_series_config_changed)
        self.y_column_combo.currentTextChanged.connect(self._on_series_config_changed)
        # Defer label persistence to editingFinished to avoid disruptive refresh while typing
        self.series_label_edit.textChanged.connect(self._on_label_typing)
        self.series_label_edit.editingFinished.connect(self._on_label_committed)

        # Connect style change signal (aggregated from StyleTab)
        self.style_tab.style_changed.connect(self._on_style_changed)

    def setup_event_subscriptions(self):
        """Set up event subscriptions for tab changes."""
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        # Ensure datasets populate after a project is loaded from file. AppState emits
        # 'project_loaded' (underscore) and 'first_project_loaded'. Also subscribe to the
        # canonical constant for forward compatibility.
        self.subscribe_to_event(ProjectEvents.PROJECT_LOADED, self._on_project_loaded)  # may not fire yet
        self.subscribe_to_event('project_loaded', self._on_project_loaded)
        self.subscribe_to_event('first_project_loaded', self._on_project_loaded)

    def _ensure_datasets_loaded(self):
        """Populate datasets if empty (idempotent)."""
        if not self.datasets and self.app_context.app_state.current_project:
            self.set_project(self.app_context.app_state.current_project)

    def _on_project_loaded(self, event_data):
        """Handle project loaded to refresh dataset list and any active chart context."""
        project = event_data.get('project') or self.app_context.app_state.current_project
        if project:
            self.set_project(project)
            # If a chart tab already active, re-load to bind series list correctly
            if self.current_chart:
                self.load_chart_object(self.current_chart)

    def _on_tab_changed(self, event_data):
        """Handle tab change events to update context."""
        current_tab_type = event_data.get('tab_type')
        chart_id = event_data.get('chart_id')

        # Check if current tab is a chart tab
        if current_tab_type == 'chart' and chart_id:
            # Get the chart from the project using chart_id
            project = self.app_context.app_state.current_project
            self.set_project(project)
            if project is not None:
                chart = project.find_item(chart_id)
                if chart:
                    # Load the chart into the properties panel
                    self.load_chart_object(chart)
                    self.logger.info("Chart properties panel context set to chart %s", chart.name)
                else:
                    self.logger.warning("Chart properties panel: chart id %s not found in project", chart_id)
            else:
                self.logger.warning("Chart properties panel: no current project available while switching tab")
        else:
            # Clear chart properties panel context when no relevant tab is active
            self.load_chart_object(None)
            self.logger.debug("Chart properties panel context cleared")

    def _on_chart_updated(self, event_data):
        """Handle chart updated events to refresh the panel."""
        chart_id = event_data.get('chart_id')
        update_type = event_data.get('update_type', '')

        # If this is our current chart, refresh the display
        if self.current_chart and chart_id == self.current_chart.id:
            # Refresh the series list to show new series (like fit lines)
            if update_type in ['fit_added', 'series_added', 'series_removed']:
                self._update_series_list()
                self.logger.debug("Chart properties panel refreshed for update: %s", update_type)

    def _add_series(self):
        """Add a new data series."""
        if not self.current_chart:
            return

        # Create a new series with default values
        dataset_id = self.dataset_combo.currentData() if self.dataset_combo.count() > 0 else ""
        dataset_name = self.dataset_combo.currentText() if self.dataset_combo.count() > 0 else ""
        x_column = self.x_column_combo.currentText() if self.x_column_combo.count() > 0 else ""
        y_column = self.y_column_combo.currentText() if self.y_column_combo.count() > 0 else ""

        if dataset_id and x_column and y_column:
            command = AddSeriesCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                dataset_id=dataset_id,
                x_column=x_column,
                y_column=y_column,
                label=f"{dataset_name}:{y_column}",
                color=self._get_next_series_color(),
            )
            self.command_executor.execute_command(command)

            # Update the series list
            self._update_series_list()

            # Select the new series
            self.series_list.setCurrentRow(len(self.current_chart.data_series) - 1)

    def _remove_series(self):
        """Remove the selected data series."""
        if not self.current_chart or not self.current_chart.data_series:
            return

        current_row = self.series_list.currentRow()
        if current_row >= 0 and current_row < len(self.current_chart.data_series):
            command = RemoveSeriesCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                series_index=current_row,
            )
            self.command_executor.execute_command(command)

            # Update the series list
            self._update_series_list()

            # Select previous series or disable if no series left
            if self.current_chart.data_series:
                new_row = min(current_row, len(self.current_chart.data_series) - 1)
                self.series_list.setCurrentRow(new_row)
            else:
                self.series_config_group.setEnabled(False)

    def _on_series_selection_changed(self, current_row: int):
        """Handle series selection change."""
        if not self.current_chart or current_row < 0:
            self.series_config_group.setEnabled(False)
            return

        total_series = len(self.current_chart.data_series)
        total_items = total_series + len(self.current_chart.fit_data)

        if current_row >= total_items:
            self.series_config_group.setEnabled(False)
            return

        # Enable configuration
        self.series_config_group.setEnabled(True)

        if current_row < total_series:
            # This is a data series
            series = self.current_chart.data_series[current_row]
            self._load_series_into_controls(series)
        else:
            # This is fit data
            fit_index = current_row - total_series
            fit = self.current_chart.fit_data[fit_index]
            self._load_fit_into_controls(fit)

        # Enable/disable remove button
        self.remove_series_button.setEnabled(total_items > 0)

    def _on_series_config_changed(self):
        """Handle dataset / column configuration changes for the selected series.

        Label changes are intentionally deferred to editingFinished handled by
        _on_label_committed to avoid disruptive list refresh while typing.
        """
        if self._updating_controls or not self.current_chart:
            return

        current_row = self.series_list.currentRow()
        if current_row < 0:
            return

        total_series = len(self.current_chart.data_series)
        if current_row < total_series:
            # Update data series (guard for safety)
            if current_row >= len(self.current_chart.data_series):
                return
            series = self.current_chart.data_series[current_row]
            if self.dataset_combo.currentData():
                series.dataset_id = self.dataset_combo.currentData()
            series.x_column = self.x_column_combo.currentText()
            series.y_column = self.y_column_combo.currentText()
        else:
            # Fit data: columns/dataset not editable, ignore
            return

        self._has_unsaved_changes = True
        self._update_status_indicator()

    def _on_style_changed(self):
        """Handle style changes."""
        if self._updating_controls or not self.current_chart:
            return

        current_row = self.series_list.currentRow()
        if current_row < 0:
            return

        total_series = len(self.current_chart.data_series)

        if current_row < total_series:
            # Updating a data series
            if current_row >= len(self.current_chart.data_series):
                return
            series = self.current_chart.data_series[current_row]
            self.style_tab.apply_style_to_series(series)
        else:
            # Updating fit data
            fit_index = current_row - total_series
            if fit_index >= len(self.current_chart.fit_data):
                return
            fit = self.current_chart.fit_data[fit_index]
            self.style_tab.apply_style_to_fit(fit)

        # Emit update event so any open chart tab refreshes immediately
        if self.current_chart:
            self._has_unsaved_changes = True
            self._update_status_indicator()
            self.publish_event(ChartEvents.CHART_UPDATED, {
                'chart_id': self.current_chart.id,
                'update_type': 'series_updated'
            })

    def _on_chart_config_changed(self):
        """Handle chart-level configuration changes."""
        if not self.current_chart or self._updating_controls:
            return

        # Update chart configuration from UI controls
        self.current_chart.name = self.title_edit.text()

        config = self.current_chart.config
        self.axes_tab.apply_to_chart_config(config)
        self.legend_tab.apply_to_chart_config(config)

        if self.chart_type_combo.currentData():
            chart_type_map = {
                ChartType.LINE: 'line',
                ChartType.SCATTER: 'scatter',
                ChartType.BAR: 'bar',
                ChartType.HISTOGRAM: 'hist',
                ChartType.BOX: 'box',
                ChartType.VIOLIN: 'violin'
            }
            chart_type = self.chart_type_combo.currentData()
            if chart_type in chart_type_map:
                self.current_chart.chart_type = chart_type_map[chart_type]

        # Emit update event so any open chart tab refreshes immediately
        if self.current_chart:
            self._has_unsaved_changes = True
            self._update_status_indicator()
            self.publish_event(ChartEvents.CHART_UPDATED, {
                'chart_id': self.current_chart.id,
                'update_type': 'config_updated'
            })

    def _update_status_indicator(self):
        """Update the status label to reflect unsaved changes."""
        if self._has_unsaved_changes:
            self.status_label.setText("Modified *")
            self.status_label.setStyleSheet("color: #ffc107; font-size: 9pt; font-weight: bold;")
        else:
            self.status_label.setText("")

    def _update_series_list(self):
        """Update the series list widget."""
        previous_row = self.series_list.currentRow()
        self.series_list.clear()

        if not self.current_chart:
            return

        # Add data series
        for i, series in enumerate(self.current_chart.data_series):
            label = series.label or f"Series {i+1}"
            self.series_list.addItem(label)

        # Add fit data as separate items
        for i, fit in enumerate(self.current_chart.fit_data):
            label = f"🔧 {fit.label}" # Wrench emoji to distinguish fit data
            self.series_list.addItem(label)

        # Enable/disable controls
        has_items = len(self.current_chart.data_series) > 0 or len(self.current_chart.fit_data) > 0
        self.remove_series_button.setEnabled(has_items)

        # Restore previous selection if still valid
        if previous_row >= 0 and previous_row < self.series_list.count():
            self.series_list.setCurrentRow(previous_row)

    def _load_series_into_controls(self, series):
        """Load a data series into the configuration controls."""
        # Enable all controls for series editing
        self._updating_controls = True
        try:
            self._reset_controls_for_series()

            # Set dataset
            for i in range(self.dataset_combo.count()):
                if self.dataset_combo.itemData(i) == series.dataset_id:
                    self.dataset_combo.setCurrentIndex(i)
                    break

            # Set columns
            x_index = self.x_column_combo.findText(series.x_column)
            if x_index >= 0:
                self.x_column_combo.setCurrentIndex(x_index)

            y_index = self.y_column_combo.findText(series.y_column)
            if y_index >= 0:
                self.y_column_combo.setCurrentIndex(y_index)

            # Set label (block signals while populating)
            self.series_label_edit.blockSignals(True)
            self.series_label_edit.setText(series.label)
            self.series_label_edit.blockSignals(False)
            self._pending_label = series.label

            # Update style controls to reflect this series
            self.style_tab.load_series_style(series)
        finally:
            self._updating_controls = False

    def _load_fit_into_controls(self, fit):
        """Load fit data into the configuration controls."""
        self._updating_controls = True
        try:
            # For fit data, disable dataset/column controls since they're not editable
            self.dataset_combo.setEnabled(False)
            self.x_column_combo.setEnabled(False)
            self.y_column_combo.setEnabled(False)

            # Show fit info in the label (block signals)
            self.series_label_edit.blockSignals(True)
            self.series_label_edit.setText(fit.label)
            self.series_label_edit.blockSignals(False)
            self._pending_label = fit.label

            # Update style controls to reflect this fit
            self.style_tab.load_fit_style(fit)
        finally:
            self._updating_controls = False

    def _on_label_typing(self, text: str):
        """Buffer label text while user is typing without mutating the model."""
        self._pending_label = text

    def _on_label_committed(self):
        """Persist buffered label to model after editing finishes."""
        if self._updating_controls or not self.current_chart:
            return
        current_row = self.series_list.currentRow()
        if current_row < 0:
            return
        total_series = len(self.current_chart.data_series)
        new_label = self._pending_label or self.series_label_edit.text()
        if current_row < total_series:
            if current_row < len(self.current_chart.data_series):
                self.current_chart.data_series[current_row].label = new_label
        else:
            fit_index = current_row - total_series
            if 0 <= fit_index < len(self.current_chart.fit_data):
                self.current_chart.fit_data[fit_index].label = new_label

        # Update just the current QListWidgetItem text to avoid focus loss
        item = self.series_list.item(current_row)
        if item:
            if current_row < total_series:
                item.setText(new_label or f"Series {current_row+1}")
            else:
                item.setText(f"🔧 {new_label}")
        self._pending_label = new_label

    def _reset_controls_for_series(self):
        """Reset controls for editing regular data series."""
        self.dataset_combo.setEnabled(True)
        self.x_column_combo.setEnabled(True)
        self.y_column_combo.setEnabled(True)

    def _get_next_series_color(self) -> str:
        """Get the next color for a new series."""
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                 "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

        if not self.current_chart or not self.current_chart.data_series:
            return colors[0]

        return colors[len(self.current_chart.data_series) % len(colors)]

    def set_project(self, project):
        """Set the current project."""
        self.current_project = project
        self._update_datasets()

    def _update_datasets(self):
        """Update the available datasets."""
        self.dataset_combo.clear()
        self.datasets = []

        if self.current_project:
            # Iterate through all items in the project to find datasets
            for item in self.current_project.get_all_items():
                if isinstance(item, Dataset):
                    self.dataset_combo.addItem(item.name, item.id)
                    self.datasets.append(item)

    def _on_dataset_changed(self):
        """Handle dataset selection change."""
        dataset_id = self.dataset_combo.currentData()
        if dataset_id and self.current_project:
            dataset = self.current_project.find_item(dataset_id)
            if isinstance(dataset, Dataset) and dataset.data is not None:
                columns = list(dataset.data.columns)

                # Update column combos
                self.x_column_combo.clear()
                self.y_column_combo.clear()

                for column in columns:
                    self.x_column_combo.addItem(column)
                    self.y_column_combo.addItem(column)

                # Set defaults if possible
                if len(columns) >= 2:
                    self.x_column_combo.setCurrentIndex(0)
                    self.y_column_combo.setCurrentIndex(1)

    def _get_current_configuration(self) -> ChartConfiguration:
        """Get the current configuration from UI."""
        config = ChartConfiguration()

        # Basic info
        config.title = self.title_edit.text()
        config.chart_type = self.chart_type_combo.currentData() or ChartType.LINE
        config.dataset_id = self.dataset_combo.currentData() or ""
        config.x_column = self.x_column_combo.currentText()
        config.y_column = self.y_column_combo.currentText()

        # Style (delegated to tabs)
        config.line_style = self.style_tab.get_line_style()
        config.marker_style = self.style_tab.get_marker_style()

        # Axes
        config.x_axis = self.axes_tab.get_x_axis()
        config.y_axis = self.axes_tab.get_y_axis()

        # Legend
        config.legend = self.legend_tab.get_legend()

        return config

    def _on_apply(self):
        """Handle apply button click."""
        if self.current_chart:
            command = ApplyChartPropertiesCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                apply_fn=self.apply_to_chart,
            )
            self.command_executor.execute_command(command)

            self._has_unsaved_changes = False
            self._update_status_indicator()

    def _on_reset(self):
        """Handle reset button click."""
        self.load_chart(None)

    def load_chart(self, chart_id: Optional[str]):
        """Load a chart configuration into the panel.

        Args:
            chart_id: The chart ID to load, or None for new chart
        """
        self.current_chart_id = chart_id

        if chart_id and self.current_project:
            # Load existing chart
            if hasattr(self.current_project, 'charts') and chart_id in self.current_project.charts:
                chart_dict = self.current_project.charts[chart_id]
                config = ChartConfiguration.from_dict(chart_dict)
                self._load_configuration(config)
            else:
                self._load_default_configuration()
        else:
            # New chart
            self._load_default_configuration()

    def load_chart_object(self, chart):
        """Load a Chart object into the panel for editing.

        Args:
            chart: Chart object to load, or None to clear
        """
        self.current_chart = chart
        self._has_unsaved_changes = False
        self._update_status_indicator()

        if chart:
            # Ensure datasets are available (important after opening a project file)
            self._ensure_datasets_loaded()
            # Load basic info
            self.title_edit.setText(chart.config.get('title', chart.name))

            # Set chart type
            chart_type_map = {
                'line': ChartType.LINE,
                'scatter': ChartType.SCATTER,
                'bar': ChartType.BAR,
                'hist': ChartType.HISTOGRAM,
                'box': ChartType.BOX,
                'violin': ChartType.VIOLIN
            }
            chart_type = chart_type_map.get(chart.chart_type, ChartType.LINE)
            for i in range(self.chart_type_combo.count()):
                if self.chart_type_combo.itemData(i) == chart_type:
                    self.chart_type_combo.setCurrentIndex(i)
                    break

            # Update series list
            self._update_series_list()

            # If there are data series, select the first one
            if chart.data_series:
                self.series_list.setCurrentRow(0)
                self._load_series_into_controls(chart.data_series[0])
                self.series_config_group.setEnabled(True)

                # Set style from first series for the style tab
                first_series = chart.data_series[0]
                self.style_tab.line_color_button.set_color(first_series.color)
                self.style_tab.line_width_spin.setValue(first_series.line_width)
                self.style_tab.marker_size_spin.setValue(first_series.marker_size)
                self.add_series_button.show()
                self.remove_series_button.show()
            else:
                self.series_config_group.setEnabled(False)
                self.add_series_button.show()
                self.remove_series_button.hide()

            # Load axis and legend configuration
            config = chart.config
            self.axes_tab.load_from_chart_config(config)
            self.legend_tab.load_from_chart_config(config)

        else:
            # Clear/default values
            self._load_default_configuration()
            self.series_list.clear()
            self.series_config_group.setEnabled(False)
            if hasattr(self, 'add_series_button'):
                self.add_series_button.show()
            if hasattr(self, 'remove_series_button'):
                self.remove_series_button.hide()

    def apply_to_chart(self, chart):
        """Apply current panel settings to a Chart object.

        Args:
            chart: Chart object to update
        """
        if not chart:
            return

        # Update basic chart properties
        chart.config['title'] = self.title_edit.text()
        self.axes_tab.apply_to_chart_config(chart.config)
        self.legend_tab.apply_to_chart_config(chart.config)

        # Update chart type
        chart_type_map = {
            ChartType.LINE: 'line',
            ChartType.SCATTER: 'scatter',
            ChartType.BAR: 'bar',
            ChartType.HISTOGRAM: 'hist',
            ChartType.BOX: 'box',
            ChartType.VIOLIN: 'violin'
        }
        chart_type = self.chart_type_combo.currentData()
        if chart_type in chart_type_map:
            chart.chart_type = chart_type_map[chart_type]

        # Apply style updates to the currently selected series or fit data
        current_row = self.series_list.currentRow()
        if current_row >= 0:
            total_series = len(chart.data_series)

            if current_row < total_series:
                # Update data series
                series = chart.data_series[current_row]
                self.style_tab.apply_style_to_series(series)

                self.logger.debug(
                    "Applied style to data series %d: %s (color=%s, marker_color=%s)",
                    current_row, series.label, series.color, series.marker_color
                )
            else:
                # Update fit data
                fit_index = current_row - total_series
                if 0 <= fit_index < len(chart.fit_data):
                    fit = chart.fit_data[fit_index]
                    self.style_tab.apply_style_to_fit(fit)

                    self.logger.debug(
                        "Applied style to fit data %d: %s (color=%s)",
                        fit_index, fit.label, fit.color
                    )

        # If no series exist but we have configuration, create a default series
        if not chart.data_series:
            dataset_id = self.dataset_combo.currentData()
            dataset_name = self.dataset_combo.currentText()
            x_column = self.x_column_combo.currentText()
            y_column = self.y_column_combo.currentText()

            if dataset_id and x_column and y_column:
                chart.add_data_series(
                    dataset_id=dataset_id,
                    x_column=x_column,
                    y_column=y_column,
                    color=self.style_tab.line_color_button.get_color(),
                    line_width=self.style_tab.line_width_spin.value(),
                    marker_size=self.style_tab.marker_size_spin.value(),
                    label=f"{dataset_name}:{y_column}"
                )

        chart.update_modified_time()

    def _load_configuration(self, config: ChartConfiguration):
        """Load a configuration into the UI widgets."""
        # Basic info
        self.title_edit.setText(config.title)

        # Find and set chart type
        for i in range(self.chart_type_combo.count()):
            if self.chart_type_combo.itemData(i) == config.chart_type:
                self.chart_type_combo.setCurrentIndex(i)
                break

        # Find and set dataset
        for i in range(self.dataset_combo.count()):
            if self.dataset_combo.itemData(i) == config.dataset_id:
                self.dataset_combo.setCurrentIndex(i)
                break

        # Set columns
        x_index = self.x_column_combo.findText(config.x_column)
        if x_index >= 0:
            self.x_column_combo.setCurrentIndex(x_index)

        y_index = self.y_column_combo.findText(config.y_column)
        if y_index >= 0:
            self.y_column_combo.setCurrentIndex(y_index)

        # Style (delegated to tabs)
        self.style_tab.set_line_style(config.line_style)
        self.style_tab.set_marker_style(config.marker_style)

        # Axes
        self.axes_tab.set_x_axis(config.x_axis)
        self.axes_tab.set_y_axis(config.y_axis)

        # Legend
        self.legend_tab.set_legend(config.legend)

    def _load_default_configuration(self):
        """Load default configuration."""
        config = self.style_manager.get_default_configuration()
        self._load_configuration(config)
