from typing import override

import pandas as pd
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ChartEvents
from pandaplot.models.events.event_types import ConfigEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext


class ChartEditorWidget(PWidget):
    """
    A chart editor widget with configuration options and live preview.
    """

    def __init__(self, app_context: AppContext, chart: Chart, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.chart = chart
        self.is_modified = False
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.setSingleShot(True)

        # Sample data for preview
        # TODO: do we need this?
        self.sample_data = self.generate_sample_data()

        self._init_ui()
        self.load_chart_config()
        self.update_chart()
        self.setup_event_subscriptions()
        self._apply_theme()

        # Apply theme after UI is fully constructed
        QTimer.singleShot(100, self._apply_theme)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to all components."""
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        card_bg = palette.get('card_bg', '#f8f9fa')
        card_border = palette.get('card_border', '#dee2e6')
        base_fg = palette.get('base_fg', '#000000')
        secondary_fg = palette.get('secondary_fg', '#555555')
        
        # Apply styling to preview frame
        if hasattr(self, 'preview_frame'):
            self.preview_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                }}
            """)
        
        # Apply styling to status frame
        if hasattr(self, 'status_frame'):
            self.status_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                    padding: 1px;
                }}
            """)
        
        # Apply styling to dataset label
        if hasattr(self, 'dataset_label'):
            self.dataset_label.setStyleSheet(f"color: {secondary_fg}; font-size: 12px;")
        
        # Apply styling to status label (preserve color logic based on current text)
        if hasattr(self, 'status_label'):
            self._update_status_label_style()
        
        # Apply theme to toolbar if it exists
        if hasattr(self, 'preview_toolbar'):
            self._apply_toolbar_theme()
        
        # Apply theme to spinboxes
        if hasattr(self, 'width_spin'):
            self._apply_spinbox_style(self.width_spin)
        if hasattr(self, 'height_spin'):
            self._apply_spinbox_style(self.height_spin)
        
        # Apply theme to size label
        if hasattr(self, 'size_label'):
            self._apply_label_style(self.size_label)
        if hasattr(self, 'multiply_label'):
            self._apply_label_style(self.multiply_label)
        
        # Apply theme to chart canvas navigation if it exists
        if hasattr(self, 'chart_canvas'):
            self.chart_canvas.apply_navigation_theme(base_fg, card_bg, card_border)

    def _apply_spinbox_style(self, spinbox):
        """Apply theme-aware styling to a QSpinBox"""
        try:
            theme_manager = self.app_context.get_theme_manager()
            palette = theme_manager.get_surface_palette()
            
            base_fg = palette.get('base_fg', '#000000')
            card_border = palette.get('card_border', '#dee2e6')
            card_bg = palette.get('card_bg', '#f8f9fa')

            spinbox.setStyleSheet(f"""
                QSpinBox {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 3px;
                    padding: 2px 5px;
                    color: {base_fg};
                    font-size: 12px;
                }}
                QSpinBox:focus {{
                    border-color: #007bff;
                    background-color: {card_bg};
                }}
            """)
        except Exception as e:
            self.logger.debug(f"Could not apply spinbox style: {e}")

    def _apply_label_style(self, label):
        """Apply theme-aware styling to a QLabel"""
        try:
            theme_manager = self.app_context.get_theme_manager()
            palette = theme_manager.get_surface_palette()
            base_fg = palette.get('base_fg', '#000000')

            label.setStyleSheet(f"""
                QLabel {{
                    color: {base_fg};
                    font-weight: 500;
                    margin: 0 5px;
                }}
            """)
        except Exception as e:
            self.logger.debug(f"Could not apply label style: {e}")

    def _apply_toolbar_theme(self):
        """Apply theme-aware styling to the preview toolbar."""
        if not hasattr(self, 'preview_toolbar'):
            return
            
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        base_fg = palette.get('base_fg', '#000000')
        card_bg = palette.get('card_bg', '#f8f9fa')
        card_border = palette.get('card_border', '#dee2e6')
        
        self.preview_toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {card_bg};
                border-bottom: 1px solid {card_border};
                padding: 4px;
                color: {base_fg};
            }}
            QToolBar QToolButton {{
                color: {base_fg};
                background-color: transparent;
                border: none;
                padding: 6px 10px;
                margin: 1px;
                border-radius: 3px;
                font-weight: 500;
            }}
            QToolBar QToolButton:hover {{
                background-color: {card_border};
                color: {base_fg};
            }}
            QToolBar QToolButton:pressed {{
                background-color: {card_border};
                color: {base_fg};
            }}
        """)

    def _update_status_label_style(self):
        """Update status label styling based on current status and theme."""
        if not hasattr(self, 'status_label'):
            return
            
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        secondary_fg = palette.get('secondary_fg', '#555555')
        
        status_text = self.status_label.text()
        
        # Determine color based on status
        if "Modified" in status_text:
            color = "#ffc107"  # Warning yellow
        elif "Saved" in status_text or "Exported" in status_text:
            color = "#28a745"  # Success green
        elif "Error" in status_text:
            color = "#dc3545"  # Error red
        else:
            color = secondary_fg  # Default theme color
            
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def refresh_theme_styling(self):
        """Refresh all theme-dependent styling. Call this when theme changes."""
        self._apply_theme()

    @override
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Main content area with splitter
        self.create_content_section(layout)

        # Status bar
        self.create_status_section(layout)

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the chart editor."""
        # Subscribe to config updates to adjust display settings like DPI
        super().setup_event_subscriptions()
        try:
            self.subscribe_to_event(ConfigEvents.CONFIG_UPDATED, self._on_config_updated)
        except Exception:
            self.logger.debug(
                "Could not subscribe to config.updated for DPI handling")

    def _on_config_updated(self, data):
        """Handle config.updated events to apply display changes (e.g., DPI)."""
        try:
            cfg = data.get('config') if isinstance(data, dict) else None
            if not cfg:
                return
            dpi = getattr(getattr(cfg, 'chart_display', None), 'dpi', None)
            if dpi and self.chart_canvas and self.chart_canvas.fig.dpi != dpi:
                self.chart_canvas.fig.set_dpi(dpi)
                # Matplotlib may need a tight_layout or redraw
                try:
                    self.chart_canvas.fig.tight_layout()
                except Exception:
                    pass
                self.chart_canvas.draw()
        except Exception:
            self.logger.exception("Failed applying updated DPI setting")

    def create_content_section(self, layout):
        """Create the main content section with chart preview only."""
        # Chart preview section (full width, no configuration panel)
        self.create_chart_preview_section(layout)

    def create_chart_preview_section(self, layout):
        """Create the chart preview section."""
        self.preview_frame = QFrame()
        # Remove hardcoded styling - will be applied in _apply_theme
        # Set size policy to expand and take all available space
        self.preview_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        # Preview toolbar with chart actions and size controls
        self.preview_toolbar = QToolBar()
        # Remove hardcoded styling - will be applied in _apply_theme

        # Add chart actions
        self.create_chart_toolbar_actions(self.preview_toolbar)

        # Add separator
        self.preview_toolbar.addSeparator()

        # Add size controls
        self.size_label = QLabel("Size:")
        # Remove hardcoded styling - will be applied in _apply_theme
        self.preview_toolbar.addWidget(self.size_label)

        # Width control
        self.width_spin = QSpinBox()
        self.width_spin.setRange(4, 20)
        self.width_spin.setValue(8)
        self.width_spin.setSuffix(" in")
        self.width_spin.setToolTip("Chart width in inches")
        # Theme-aware styling will be applied in _apply_theme
        self.width_spin.valueChanged.connect(self._on_size_changed)
        self.preview_toolbar.addWidget(self.width_spin)

        self.multiply_label = QLabel("×")
        # Theme-aware styling will be applied in _apply_theme
        self.preview_toolbar.addWidget(self.multiply_label)

        # Height control
        self.height_spin = QSpinBox()
        self.height_spin.setRange(3, 15)
        self.height_spin.setValue(6)
        self.height_spin.setSuffix(" in")
        self.height_spin.setToolTip("Chart height in inches")
        # Theme-aware styling will be applied in _apply_theme
        self.height_spin.valueChanged.connect(self._on_size_changed)
        self.preview_toolbar.addWidget(self.height_spin)

        # Reset zoom button
        reset_zoom_action = QAction("🔍 Reset Zoom", self)
        reset_zoom_action.setToolTip("Reset chart zoom to fit all data")
        reset_zoom_action.triggered.connect(self._on_reset_zoom)
        self.preview_toolbar.addAction(reset_zoom_action)

        preview_layout.addWidget(self.preview_toolbar)

        # Chart canvas
        # Fetch preferred DPI from config manager
        dpi = 100
        try:
            cfg_manager = self.app_context.get_config_manager()
            cfg = getattr(cfg_manager, 'config', None)
            if cfg and getattr(cfg, 'chart_display', None):
                dpi = getattr(cfg.chart_display, 'dpi', dpi) or dpi
        except Exception:
            pass
        self.chart_canvas = ChartCanvas(width=8, height=6, dpi=dpi)
        self.chart_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add navigation toolbar for zoom/pan
        if hasattr(self.chart_canvas, 'navigation_toolbar'):
            nav_toolbar = self.chart_canvas.navigation_toolbar
            # Theme-aware styling will be applied in apply_theme_aware_colors()
            preview_layout.addWidget(nav_toolbar)

        preview_layout.addWidget(self.chart_canvas)

        layout.addWidget(self.preview_frame)

    def create_status_section(self, layout):
        """Create the status section."""
        self.status_frame = QFrame()
        # Remove hardcoded styling - will be applied in _apply_theme
        # Set fixed height to prevent expansion
        self.status_frame.setFixedHeight(30)
        self.status_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(8, 1, 8, 1)
        status_layout.setSpacing(4)

        datasets = self.chart.get_all_datasets()
        dataset_text = f"Datasets: {', '.join(datasets)}" if datasets else "Sample Data"
        self.dataset_label = QLabel(dataset_text)
        # Remove hardcoded styling - will be applied in _apply_theme
        status_layout.addWidget(self.dataset_label)

        status_layout.addStretch()

        self.status_label = QLabel("Ready")
        # Initial styling will be applied in _apply_theme
        status_layout.addWidget(self.status_label)

        layout.addWidget(self.status_frame)

    def create_chart_toolbar_actions(self, toolbar):
        """Create toolbar actions for chart operations."""
        # Save chart action
        save_action = QAction("💾 Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_chart)
        toolbar.addAction(save_action)

        # Export action
        export_action = QAction("📤 Export", self)
        export_action.triggered.connect(self.export_chart)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Reset action
        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self.reset_chart)
        toolbar.addAction(reset_action)

    def generate_sample_data(self):
        """Generate sample data for chart preview."""
        # TODO: remove
        return pd.DataFrame()

    def load_chart_config(self):
        """Load chart configuration into UI controls."""
        # No configuration UI to load since it's now in the side panel
        pass

    def update_chart(self):
        """Update the chart preview."""
        try:
            # Clear the current plot
            self.chart_canvas.axes.clear()

            # If no data series, show sample data
            if not self.chart.data_series:
                # TODO: remove this, we want to know there is no data as it can showcase whether we have an error
                # instead of showing some data, rather write no data loaded
                self.dataset_label.setText("No Data Loaded")
            else:
                # Plot actual data series from real datasets
                for i, series in enumerate(self.chart.data_series):
                    # Get the actual dataset from the project
                    project = self.app_context.get_app_state().current_project
                    if project:
                        dataset_item = project.find_item(series.dataset_id)
                        from pandaplot.models.project.items.dataset import Dataset

                        if isinstance(dataset_item, Dataset) and dataset_item.data is not None:
                            # Use real data from the dataset
                            df = dataset_item.data

                            # Check if the required columns exist
                            if series.x_column in df.columns and series.y_column in df.columns:
                                x_data = df[series.x_column]
                                y_data = df[series.y_column]

                                # Plot based on chart type for regular data series
                                if self.chart.chart_type == 'line':
                                    self.chart_canvas.axes.plot(x_data, y_data,
                                                                color=series.color,
                                                                linewidth=series.line_width,
                                                                marker='o' if series.marker_style == 'circle' else 's',
                                                                markersize=series.marker_size,
                                                                label=series.label,
                                                                alpha=1.0 if series.visible else 0.3)
                                elif self.chart.chart_type == 'scatter':
                                    self.chart_canvas.axes.scatter(x_data, y_data,
                                                                   c=series.color,
                                                                   s=series.marker_size*10,
                                                                   label=series.label,
                                                                   alpha=1.0 if series.visible else 0.3)
                                elif self.chart.chart_type == 'bar':
                                    self.chart_canvas.axes.bar(x_data, y_data,
                                                               color=series.color,
                                                               label=series.label,
                                                               alpha=1.0 if series.visible else 0.3)
                                elif self.chart.chart_type == 'hist':
                                    self.chart_canvas.axes.hist(y_data, bins=20,
                                                                color=series.color,
                                                                label=series.label,
                                                                alpha=0.7 if series.visible else 0.3)
                            else:
                                # Column not found - use sample data as fallback
                                x_data = self.sample_data['x']
                                y_col = 'y1' if i == 0 else 'y2'
                                y_data = self.sample_data[y_col] if y_col in self.sample_data.columns else self.sample_data['y1']

                                if self.chart.chart_type == 'line':
                                    self.chart_canvas.axes.plot(x_data, y_data,
                                                                color=series.color,
                                                                linewidth=series.line_width,
                                                                marker='o' if series.marker_style == 'circle' else 's',
                                                                markersize=series.marker_size,
                                                                label=f"{series.label} (Column not found)",
                                                                alpha=0.5, linestyle='--')
                        else:
                            # Dataset not found - use sample data as fallback
                            x_data = self.sample_data['x']
                            y_col = 'y1' if i == 0 else 'y2'
                            y_data = self.sample_data[y_col] if y_col in self.sample_data.columns else self.sample_data['y1']

                            if self.chart.chart_type == 'line':
                                self.chart_canvas.axes.plot(x_data, y_data,
                                                            color=series.color,
                                                            linewidth=series.line_width,
                                                            marker='o' if series.marker_style == 'circle' else 's',
                                                            markersize=series.marker_size,
                                                            label=f"{series.label} (Dataset not found)",
                                                            alpha=0.5, linestyle=':')

                # Plot fit data from chart.fit_data
                for i, fit in enumerate(self.chart.fit_data):
                    if fit.visible:
                        # Plot the fit line
                        line_style = '--' if fit.line_style == 'dashed' else '-'
                        self.chart_canvas.axes.plot(fit.x_data, fit.y_data,
                                                    color=fit.color,
                                                    linewidth=fit.line_width,
                                                    linestyle=line_style,
                                                    label=fit.label,
                                                    alpha=1.0)

            # Apply chart configuration
            config = self.chart.config
            self.chart_canvas.axes.set_title(config.get(
                'title', self.chart.name), fontsize=14, fontweight='bold')
            self.chart_canvas.axes.set_xlabel(config.get('x_label', ''))
            self.chart_canvas.axes.set_ylabel(config.get('y_label', ''))

            if config.get('show_grid', True):
                self.chart_canvas.axes.grid(
                    True, alpha=config.get('grid_alpha', 0.3))

            if config.get('show_legend', True) and (self.chart.data_series or self.chart.fit_data):
                self.chart_canvas.axes.legend(
                    loc=config.get('legend_position', 'upper right'))

            # Store original limits for zoom reset functionality
            self.chart_canvas.store_original_limits()

            # Refresh canvas
            self.chart_canvas.draw()

        except Exception as e:
            self.logger.exception("Error updating chart")
            self.update_status(f"Chart error: {str(e)}")

    def save_chart(self):
        """Save the chart configuration."""
        try:
            # Update modification time
            self.chart.update_modified_time()

            # Update UI
            self.is_modified = False
            self.update_status("Saved ✓")

            # Publish chart updated event
            self.publish_event(ChartEvents.CHART_UPDATED, {
                'chart_id': self.chart.id,
                'chart_name': self.chart.name
            })

            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))

        except Exception as e:
            self.update_status(f"Error: {str(e)}")

    def auto_save(self):
        """Auto-save the chart configuration."""
        if self.is_modified:
            self.save_chart()

    def export_chart(self):
        """Export the chart to file."""
        try:
            # Save the current figure
            filename = f"{self.chart.name}.png"
            self.chart_canvas.fig.savefig(
                filename, dpi=300, bbox_inches='tight')
            self.update_status(f"Exported to {filename} ✓")

            # Reset status after 3 seconds
            QTimer.singleShot(3000, lambda: self.update_status("Ready"))

        except Exception as e:
            self.update_status(f"Export error: {str(e)}")

    def reset_chart(self):
        """Reset chart to default configuration."""
        self.chart._init_default_config()
        self.update_chart()
        self.update_status("Reset to defaults ✓")

        # Reset status after 2 seconds
        QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def update_status(self, status: str):
        """Update the status label."""
        self.status_label.setText(status)
        self._update_status_label_style()

    def _on_size_changed(self):
        """Handle chart size changes."""
        if hasattr(self, 'chart_canvas'):
            width = self.width_spin.value()
            height = self.height_spin.value()
            self.chart_canvas.set_size(width, height)
            self.update_status("Chart size updated")

            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def _on_reset_zoom(self):
        """Handle reset zoom action."""
        if hasattr(self, 'chart_canvas'):
            self.chart_canvas.reset_zoom()
            self.update_status("Zoom reset")

            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def get_chart(self) -> Chart:
        """Get the current chart object."""
        return self.chart

    def refresh_chart(self):
        """Refresh the chart preview when configuration changes from external sources."""
        self.update_chart()

        # Update dataset label in status
        datasets = self.chart.get_all_datasets()
        dataset_text = f"Datasets: {', '.join(datasets)}" if datasets else "Sample Data"
        self.dataset_label.setText(dataset_text)
