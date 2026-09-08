"""Curve fitting panel for performing regression analysis on chart data."""
import logging
from typing import Optional, override

import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.apply_fit_command import ApplyFitCommand
from pandaplot.commands.project.fit.perform_fit_command import PerformFitCommand
from pandaplot.gui.components.common.busy_spinner import BusySpinner
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import ChartEvents, UIEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import DataSeries, resolve_series_column
from pandaplot.models.state import AppContext
from pandaplot.services.fit.fit_service import MIN_FIT_POINTS, FitService
from pandaplot.services.theme import ThemeManager
from pandaplot.utils.item_display_options import dataset_display_options

# Sentinel itemData for the series_combo's "Custom..." entry, distinguishing
# it from a real DataSeries (itemData) and from "nothing selected" (None).
CUSTOM_SERIES_SENTINEL = "__custom__"


class FitPanel(SidebarPanel):
    """Side panel for performing curve fitting on chart data."""

    fit_completed = Signal(dict)  # Emitted when fit is completed with results
    fit_applied = Signal(dict)   # Emitted when fit should be applied to chart

    def __init__(self, app_context: AppContext, parent: Optional[QWidget]=None):
        super().__init__(app_context=app_context, parent=parent)
        self.fit_service = FitService()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.app_context = app_context
        self.current_chart = None
        self.fit_results = None
        self.fit_fixed_parameters: Optional[str] = None
        self._pending_fit_command = None
        self.datasets = []
        self._pending_tab_event_data: Optional[dict] = None
        self._needs_chart_refresh: bool = False

        # Check scipy availability lazily (only when FitPanel is instantiated)
        self.scipy_available = self._check_scipy_available()

        self._initialize()
        self._connect_signals()

        if not self.scipy_available:
            self._show_scipy_warning()

    def _check_scipy_available(self) -> bool:
        """Check if scipy is installed without importing it (import is deferred to fit time)."""
        import importlib.util
        return importlib.util.find_spec("scipy") is not None

    @override
    def _init_ui(self):
        """Set up the user interface."""
        self._init_panel_layout()

        # Title
        self._set_title("📐 Curve Fitting")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        # Data source section
        self._create_data_source_section(content_layout)

        # Fit configuration section
        self._create_fit_config_section(content_layout)

        # Results section
        self._create_results_section(content_layout)

        # Action buttons
        self._create_action_buttons(content_layout)

        self._set_content(content_widget, scrollable=True)

    @override
    def _apply_theme(self):
        """Apply theme styling to all components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        # Get theme colors with fallbacks
        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")

        # Apply theme to main widget
        self.setStyleSheet(f"""
            FitPanel {{
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

        # Title label with shared styling
        self._apply_title_theme(base_fg, card_border)

        self.update_data_points_display()

    def _apply_menu_styling(self):
            """Apply theme styling to the function menu"""
            theme_manager = self.app_context.get_manager(ThemeManager)
            palette = theme_manager.get_surface_palette()

            # Get theme colors with fallbacks
            card_bg = palette.get("card_bg", "#ffffff")
            card_border = palette.get("card_border", "#dee2e6")
            base_fg = palette.get("base_fg", "#333333")
            card_hover = palette.get("card_hover", "#e5f3ff")

            # Menu styling
            menu_style = f"""
                QMenu {{
                    background-color: {card_bg};
                    color: {base_fg};
                    border: 1px solid {card_border};
                    border-radius: 4px;
                }}
                QMenu::item {{
                    padding: 5px 20px;
                    background-color: transparent;
                }}
                QMenu::item:selected {{
                    background-color: {card_hover};
                    color: {base_fg};
                }}
                QMenu::item:pressed {{
                    background-color: {card_border};
                    color: {base_fg};
                }}
            """
            self.menu.setStyleSheet(menu_style)

    def _create_data_source_section(self, layout):
        """Create the data source selection section."""
        data_group = QGroupBox("Data Source")
        data_layout = QGridLayout(data_group)

        data_layout.addWidget(QLabel("Chart Series:"), 0, 0)

        self.series_combo = QComboBox()
        data_layout.addWidget(self.series_combo, 0, 1)

        # Dataset/X/Y column pickers for the "Custom..." data source, only
        # shown when that sentinel entry is selected in series_combo (see
        # _on_series_changed). Populated from every dataset in the project,
        # not just ones already on the chart.
        self.custom_source_widget = QWidget()
        custom_source_layout = QGridLayout(self.custom_source_widget)
        custom_source_layout.setContentsMargins(0, 0, 0, 0)

        custom_source_layout.addWidget(QLabel("Dataset:"), 0, 0)
        self.custom_dataset_combo = QComboBox()
        custom_source_layout.addWidget(self.custom_dataset_combo, 0, 1)

        custom_source_layout.addWidget(QLabel("X Column:"), 1, 0)
        self.custom_x_column_combo = QComboBox()
        custom_source_layout.addWidget(self.custom_x_column_combo, 1, 1)

        custom_source_layout.addWidget(QLabel("Y Column:"), 2, 0)
        self.custom_y_column_combo = QComboBox()
        custom_source_layout.addWidget(self.custom_y_column_combo, 2, 1)

        self.custom_source_widget.setVisible(False)
        data_layout.addWidget(self.custom_source_widget, 1, 0, 1, 2)

        data_layout.addWidget(QLabel("Data Points:"), 2, 0)

        points_layout = QHBoxLayout()
        self.data_points_label = QLabel("No data selected")
        points_layout.addWidget(self.data_points_label)

        self.data_points_warning_icon = QLabel("⚠")
        self.data_points_warning_icon.setStyleSheet("color: red;")
        self.data_points_warning_icon.setVisible(False)
        points_layout.addWidget(self.data_points_warning_icon)
        points_layout.addStretch()

        data_layout.addLayout(points_layout, 2, 1)

        layout.addWidget(data_group)

    def _create_fit_config_section(self, layout):
        """Create the fit configuration section."""
        fit_group = QGroupBox("Fit Configuration")
        fit_layout = QVBoxLayout(fit_group)

        # Fit type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Fit Type:"))
        self.fit_type_combo = QComboBox()
        self.fit_type_combo.addItems([
            "Linear (y = ax + b)",
            "Quadratic (y = ax² + bx + c)", 
            "Exponential (y = ae^(bx) + c)",
            "Power (y = ax^b + c)",
            "Logarithmic (y = a*ln(x) + b)",
            "Custom Function"
        ])
        type_layout.addWidget(self.fit_type_combo)
        type_layout.addStretch()
        fit_layout.addLayout(type_layout)

        # Custom function input (initially hidden)
        self.custom_group = QGroupBox("Custom Function")
        custom_layout = QGridLayout(self.custom_group)

        custom_layout.addWidget(QLabel("Function:"), 0, 0)
        self.custom_function_edit = QLineEdit()
        self.custom_function_edit.setPlaceholderText("e.g., a*x**2 + b*x + c")
        custom_layout.addWidget(self.custom_function_edit, 0, 1)
        #show menu
        self.function_button = PButton(
            "Functions", role="secondary",
            on_click=lambda: self.menu.exec_(self.function_button.mapToGlobal(self.function_button.rect().bottomLeft()))
        )
        custom_layout.addWidget(self.function_button, 0, 2)
        self.menu = QMenu()
        self.function_names = ["sin", "cos","tan", "sqrt", "exp", "log", "arcsin", "arccos"]
        self._apply_menu_styling()

        for name in self.function_names:
            action = self.menu.addAction(name)
            action.triggered.connect(lambda checked, f=name: self._insert_function(f + "("))

        custom_layout.addWidget(QLabel("Parameters:"), 1, 0)
        self.custom_params_edit = QLineEdit()
        self.custom_params_edit.setPlaceholderText("e.g., a, b, c")
        custom_layout.addWidget(self.custom_params_edit, 1, 1)

        custom_layout.addWidget(QLabel("Define parameters values:"), 2, 0)
        self.initial_guess_edit = QLineEdit()
        self.initial_guess_edit.setPlaceholderText("e.g. b=2.1, c=1")
        custom_layout.addWidget(self.initial_guess_edit, 2, 1)
        # display that some parameters are free
        
        self.custom_group.setVisible(False)
        fit_layout.addWidget(self.custom_group)
        
        # Fit options
        options_layout = QGridLayout()
        
        # Number of fit points
        options_layout.addWidget(QLabel("Fit Points:"), 0, 0)
        self.fit_points_spin = QSpinBox()
        self.fit_points_spin.setRange(50, 5000)
        self.fit_points_spin.setValue(500)
        options_layout.addWidget(self.fit_points_spin, 0, 1)
        
        # Show confidence bands
        self.confidence_check = QCheckBox("Show Confidence Bands")
        self.confidence_check.setChecked(False)
        options_layout.addWidget(self.confidence_check, 1, 0, 1, 2)
        
        # R-squared calculation
        self.r_squared_check = QCheckBox("Calculate R²")
        self.r_squared_check.setChecked(True)
        options_layout.addWidget(self.r_squared_check, 2, 0, 1, 2)
        
        fit_layout.addLayout(options_layout)

        # Fit range (plot the fitted curve outside the source data's own range)
        range_layout = QGridLayout()
        self.range_auto_check = QCheckBox("Auto")
        self.range_auto_check.setChecked(True)
        range_layout.addWidget(QLabel("Fit Range:"), 0, 0)
        range_layout.addWidget(self.range_auto_check, 0, 1)

        # In Auto mode the actual min/max are shown as read-only labels (kept
        # live via update_data_points_display()) rather than disabled
        # spinboxes, so switching series/tabs or applying a fit never leaves
        # a stale manually-typed number on screen.
        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(-1e9, 1e9)
        self.range_min_spin.setDecimals(6)
        self.range_min_spin.setVisible(False)
        self.range_min_value_label = QLabel("—")
        range_layout.addWidget(QLabel("Min:"), 1, 0)
        range_layout.addWidget(self.range_min_spin, 1, 1)
        range_layout.addWidget(self.range_min_value_label, 1, 1)

        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(-1e9, 1e9)
        self.range_max_spin.setDecimals(6)
        self.range_max_spin.setValue(1.0)
        self.range_max_spin.setVisible(False)
        self.range_max_value_label = QLabel("—")
        range_layout.addWidget(QLabel("Max:"), 2, 0)
        range_layout.addWidget(self.range_max_spin, 2, 1)
        range_layout.addWidget(self.range_max_value_label, 2, 1)

        self.range_warning_label = QLabel("Max must be greater than Min.")
        self.range_warning_label.setStyleSheet("color: red;")
        self.range_warning_label.setVisible(False)
        range_layout.addWidget(self.range_warning_label, 3, 0, 1, 2)

        fit_layout.addLayout(range_layout)
        layout.addWidget(fit_group)

    def _create_results_section(self, layout):
        """Create the results display section."""
        results_group = QGroupBox("Fit Results")
        results_layout = QVBoxLayout(results_group)

        # Results text area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Fit results will appear here...")
        results_layout.addWidget(self.results_text, stretch=1)

        # Equation display
        equation_layout = QHBoxLayout()
        equation_layout.addWidget(QLabel("Equation:"))
        self.equation_label = QLabel("No fit performed")
        self.equation_label.setMaximumHeight(60)
        self.equation_label.setStyleSheet("font-family: monospace; background-color: #f5f5f5; color: #333333; padding: 5px; border: 1px solid #ddd;")
        equation_layout.addWidget(self.equation_label)
        results_layout.addLayout(equation_layout)

        layout.addWidget(results_group)

    def _create_action_buttons(self, layout):
        """Create action buttons."""
        button_layout = QHBoxLayout()

        self.fit_button = PButton(
            "Perform Fit", role="primary", on_click=self._perform_fit, enabled=self.scipy_available
        )
        button_layout.addWidget(self.fit_button)

        self.apply_button = PButton("Apply", role="secondary", on_click=self._apply_fit, enabled=False)
        button_layout.addWidget(self.apply_button)

        self.clear_button = PButton("Clear Results", role="secondary", on_click=self._clear_results)
        button_layout.addWidget(self.clear_button)

        self.busy_spinner = BusySpinner()
        button_layout.addWidget(self.busy_spinner)

        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect widget signals."""
        self.fit_type_combo.currentTextChanged.connect(self._on_fit_type_changed)
        self.series_combo.currentIndexChanged.connect(self._on_series_changed)
        self.custom_dataset_combo.currentIndexChanged.connect(self._on_custom_dataset_changed)
        self.custom_x_column_combo.currentIndexChanged.connect(self._on_custom_column_changed)
        self.custom_y_column_combo.currentIndexChanged.connect(self._on_custom_column_changed)
        self.range_auto_check.toggled.connect(self._on_range_auto_toggled)
        self.range_min_spin.valueChanged.connect(self.update_data_points_display)
        self.range_max_spin.valueChanged.connect(self.update_data_points_display)

    def setup_event_subscriptions(self):
        """Set up event subscriptions for tab changes."""
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        self.subscribe_to_event(ChartEvents.SERIES_SELECTED, self._on_series_selected_event)

    def _on_series_selected_event(self, event_data):
        """Clicking a data series on the chart canvas or its legend also
        selects it here as the source to fit -- a fitted-curve click is
        ignored, since a fit isn't itself a valid source for a new fit.
        """
        if not self.isVisible() or self.current_chart is None:
            return
        chart_id = event_data.get("chart_id")
        if chart_id != self.current_chart.id or event_data.get("kind") != "series":
            return
        index = event_data.get("index")
        # series_combo mirrors chart.data_series 1:1, in order, followed by
        # a trailing "Custom..." entry -- so the series' own index in the
        # chart is also its row here.
        if index is None or not (0 <= index < len(self.current_chart.data_series)):
            return
        self.series_combo.setCurrentIndex(index)

    def _show_scipy_warning(self):
        """Show warning if scipy is not available."""
        warning_text = (
            "SciPy is not available. Curve fitting functionality is disabled.\n"
            "Please install SciPy to enable curve fitting: pip install scipy"
        )
        self.results_text.setPlainText(warning_text)
        self.results_text.setStyleSheet("color: red;")
    
    @property
    def current_project(self):
        """The active project, read live from app state.

        Not cached: every real call site was re-deriving this same value
        from app_state moments later anyway (via load_chart_object), so a
        separate manually-synced field only risked going stale (see #246
        follow-up).
        """
        app_state = getattr(self.app_context, "app_state", None)
        if app_state is None:
            return None
        return app_state.current_project

    def _resolve_selected_series(self) -> Optional[DataSeries]:
        """Resolve series_combo's current selection to a DataSeries.

        A real chart series is returned unchanged. The "Custom..." sentinel
        instead builds a transient DataSeries from the dataset/X/Y column
        combos below it -- never added to the chart, it only exists to
        satisfy the `series.dataset_id`/`x_column_id`/`y_column_id` reads
        that PerformFitCommand/ApplyFitCommand and get_current_data() rely
        on. Returns None if dataset/X/Y aren't all chosen yet, matching the
        "no selection" gating already in place for a real series.
        """
        selected = self.series_combo.currentData()

        if isinstance(selected, DataSeries):
            return selected

        if selected != CUSTOM_SERIES_SENTINEL:
            return None

        dataset_id = self.custom_dataset_combo.currentData()
        x_column_id = self.custom_x_column_combo.currentData()
        y_column_id = self.custom_y_column_combo.currentData()

        if not dataset_id or not x_column_id or not y_column_id:
            return None

        return DataSeries(
            dataset_id=dataset_id,
            x_column_id=x_column_id,
            y_column_id=y_column_id,
        )

    def get_current_data(self):
        """Get data from selected chart series."""
        if not self.current_project:
            self.logger.warning("No current project in FitPanel")
            return None

        series = self._resolve_selected_series()

        self.logger.info("get_current_data: current_project=%r, series=%r, combo_count=%d",
            self.current_project, series, self.series_combo.count())

        if series is None:
            self.logger.warning("No series selected in series_combo")
            return None

        self.logger.info("Selected series: dataset_id=%r, x=%r, y=%r",
            series.dataset_id, series.x_column, series.y_column)

        dataset = self.current_project.find_item(series.dataset_id)

        if not isinstance(dataset, Dataset):
            self.logger.warning("Dataset not found: id=%r, result=%r",
                series.dataset_id, dataset)
            return None

        df = dataset.data

        if df is None:
            self.logger.warning("Dataset contains no data: id=%r", series.dataset_id)
            return None

        self.logger.info("Dataset found: %r, dataframe shape=%s, columns=%s",
            dataset, df.shape, list(df.columns))

        x_column = resolve_series_column(dataset, series.x_column_id, series.x_column)
        y_column = resolve_series_column(dataset, series.y_column_id, series.y_column)

        if not x_column or not y_column or x_column not in df.columns or y_column not in df.columns:
            self.logger.warning(
                "Columns not found: x=%r y=%r columns=%s",
                x_column,
                y_column,
                list(df.columns),
            )
            return None

        mask = ~(pd.isna(df[x_column]) | pd.isna(df[y_column]))
        x_data = df[x_column][mask].values
        y_data = df[y_column][mask].values

        self.logger.info("Extracted %d data points", len(x_data))

        return df, mask, x_data, y_data, series

    def _on_tab_changed(self, event_data):
        """Handle tab change events to update context.

        The Fit panel does real work here (loading chart/dataset context,
        which triggers get_current_data()), so skip it entirely while the
        panel isn't the visible sidebar panel. Only an event that was
        actually skipped is remembered, and it's replayed from showEvent()
        once the panel becomes visible again -- otherwise re-showing the
        panel (e.g. after switching to another sidebar panel and back)
        would needlessly reload the chart and wipe any completed fit
        results, even though nothing changed while it was hidden.
        """
        if not self.isVisible():
            self._pending_tab_event_data = event_data
            return
        self._pending_tab_event_data = None
        self._apply_tab_change(event_data)

    def _apply_tab_change(self, event_data):
        current_tab_type = event_data.get("tab_type")
        tab_id = event_data.get("tab_id")
        chart_id = tab_id if current_tab_type == "chart" else None
        dataset_id = tab_id if current_tab_type == "dataset" else None

        # Check if current tab is a chart tab
        if current_tab_type == "chart" and chart_id:
            # Get the chart from the project using chart_id
            project = self.app_context.app_state.current_project
            if project is not None:
                chart = project.find_item(chart_id)
                if chart:
                    # Load the chart into the fit panel for data analysis
                    self.load_chart_object(chart)
                    self.logger.info("Fit panel context set to chart %s", chart.name)
                else:
                    self.logger.warning("Fit panel: chart id %s not found in project", chart_id)
            else:
                self.logger.warning("No current project available while switching tab")

        elif current_tab_type == "dataset" and dataset_id:
            # For dataset tabs, provide context for data fitting
            project = self.app_context.app_state.current_project
            if project is not None:
                dataset = project.find_item(dataset_id)
                if dataset:
                    # Set project context for dataset access
                    self.load_chart_object(None)  # Clear chart context
                    self.logger.debug("Fit panel dataset context set for dataset %s", dataset.name)
        else:
            # Clear fit panel context when no relevant tab is active
            self.load_chart_object(None)
            self.logger.debug("Fit panel context cleared")

    def update_data_points_display(self):
        """Update the data points display and enable/disable the Fit button accordingly."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#555555")

        range_valid = self._is_range_valid()
        self.range_warning_label.setVisible(not range_valid)
        if not range_valid:
            self.range_warning_label.setText(self._range_invalid_reason())

        current_data = self.get_current_data()
        if current_data is not None:
            df, mask, x_data, y_data, series = current_data
            if len(x_data) > 0:
                self.range_min_value_label.setText(f"{x_data.min():.6g}")
                self.range_max_value_label.setText(f"{x_data.max():.6g}")
            else:
                self.range_min_value_label.setText("—")
                self.range_max_value_label.setText("—")
            self.data_points_label.setText(f"{len(x_data)} points")

            if len(x_data) < MIN_FIT_POINTS:
                tooltip = f"At least {MIN_FIT_POINTS} valid (x, y) data points are required to perform a fit."
                self.data_points_label.setStyleSheet("color: red;")
                self.data_points_label.setToolTip(tooltip)
                self.data_points_warning_icon.setToolTip(tooltip)
                self.data_points_warning_icon.setVisible(True)
                self.fit_button.setEnabled(False)
                self.fit_button.setToolTip(tooltip)
            elif not range_valid:
                self.data_points_label.setStyleSheet(f"color: {base_fg};")
                self.data_points_label.setToolTip("")
                self.data_points_warning_icon.setVisible(False)
                self.fit_button.setEnabled(False)
                self.fit_button.setToolTip(self._range_invalid_reason())
            else:
                self.data_points_label.setStyleSheet(f"color: {base_fg};")
                self.data_points_label.setToolTip("")
                self.data_points_warning_icon.setVisible(False)
                # Don't re-enable while a fit is already in flight -- this
                # runs from unrelated range/series-change signals that know
                # nothing about that state.
                self.fit_button.setEnabled(self.scipy_available and self._pending_fit_command is None)
                self.fit_button.setToolTip("")
        else:
            tooltip = "Select a chart series with valid data to perform a fit."
            self.range_min_value_label.setText("—")
            self.range_max_value_label.setText("—")
            self.data_points_label.setText("No data selected")
            self.data_points_label.setStyleSheet(f"color: {secondary_fg}; font-style: italic;")
            self.data_points_label.setToolTip(tooltip)
            self.data_points_warning_icon.setToolTip(tooltip)
            self.data_points_warning_icon.setVisible(True)
            self.fit_button.setEnabled(False)
            self.fit_button.setToolTip(tooltip)

    def _on_fit_type_changed(self):
        """Handle fit type selection change."""
        fit_type = self.fit_type_combo.currentText()
        self.custom_group.setVisible("Custom" in fit_type)
        self.update_data_points_display()

    def display_results(self):
        """Display the fitting results."""
        if self.fit_results is None:
            return

        results = self.fit_results
        fit_type = results.fit_type
        perr = results.errors
        param_names = results.param_names
        r_squared = results.r_squared
        params = results.params

        self.equation_label.setText(
            results.equation or "No equation"
        )

        results_text = f"Fit Type: {fit_type}\n\n"
        results_text += "Parameters:\n"
        results_text += self.fit_service.format_parameters(
            param_names,
            params,
            perr,
            fixed_parameters=self.fit_fixed_parameters,
        )

        if r_squared is not None:
            results_text += f"\nR² = {r_squared:.6f}\n"

        results_text += f"\nData points: {len(results.x_data)}\n"
        results_text += f"Fit points: {len(results.x_fit)}"

        self.results_text.setStyleSheet("")
        self.results_text.setPlainText(results_text)

    def _apply_fit(self):
        """Apply the current fit result to the current chart."""
        if self.fit_results is None:
            self.logger.warning("No fit results available to apply")
            return

        series = self._resolve_selected_series()

        if series is None:
            self.logger.warning("No selected series for applying fit")
            return

        if self.current_chart is None:
            self.logger.warning("No current chart available")
            return

        dataset = self.current_project.find_item(series.dataset_id)

        if not isinstance(dataset, Dataset):
            self.logger.warning("Dataset not found: %s", series.dataset_id)
            return

        command = ApplyFitCommand(
            app_context=self.app_context,
            chart_id=self.current_chart.id,
            fit_results=self.fit_results,
            source_dataset_id=series.dataset_id,
            source_x_column_id=series.x_column_id,
            source_y_column_id=series.y_column_id,
            source_x_column=resolve_series_column(
                dataset,
                series.x_column_id,
                series.x_column) or "",
            source_y_column=resolve_series_column(
                dataset,
                series.y_column_id,
                series.y_column) or "",
            fixed_parameters=self.fit_fixed_parameters,
        )

        executor = self.app_context.get_command_executor()

        if not executor.execute_command(command):
            self.logger.error("ApplyFitCommand failed")
            return

        self.logger.info("Fit applied to chart %s", self.current_chart.id)

    def _clear_results(self):
        """Clear the fit results."""
        self.fit_results = None
        self.fit_fixed_parameters = None
        self.results_text.clear()
        self.results_text.setStyleSheet("")
        self.equation_label.setText("No fit performed")
        self.apply_button.setEnabled(False)
        if hasattr(self, "busy_spinner"):
            self.busy_spinner.stop()

    def load_chart_object(self, chart):
        """Load a Chart object for fitting analysis."""
        self._clear_results()
        self.current_chart = chart

        # Clearing/populating a combo box fires currentIndexChanged as items
        # come and go, which would call _on_series_changed() (and thus
        # get_current_data()) repeatedly mid-update. Block it and trigger
        # the update once, explicitly, once the combo reflects the new chart.
        self.series_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        self.series_combo.clear()

        if chart is None:
            self.series_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self.custom_source_widget.setVisible(False)
            self.update_data_points_display()
            return

        for series in chart.data_series:
            if series.label:
                label = series.label
            else:
                dataset = (
                    self.current_project.find_item(series.dataset_id)
                    if self.current_project else None
                )
                x_name = resolve_series_column(dataset, series.x_column_id, series.x_column) or "?"
                y_name = resolve_series_column(dataset, series.y_column_id, series.y_column) or "?"
                label = f"{y_name} vs {x_name}"
            self.series_combo.addItem(label, series)

        self.series_combo.addItem("Custom...", CUSTOM_SERIES_SENTINEL)

        if self.series_combo.count() > 0:
            self.series_combo.setCurrentIndex(0)
        self.series_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

        self._on_series_changed()

    def _on_series_changed(self):
        self._clear_results()
        self.range_auto_check.setChecked(True)
        is_custom = self.series_combo.currentData() == CUSTOM_SERIES_SENTINEL
        self.custom_source_widget.setVisible(is_custom)
        if is_custom:
            self._populate_custom_dataset_combo()
        self.update_data_points_display()

    def _populate_custom_dataset_combo(self):
        """Fill custom_dataset_combo with every dataset in the project,
        mirroring data_tab.py's own dataset combo population pattern."""
        previously_selected_id = (
            self.custom_dataset_combo.currentData() if self.custom_dataset_combo.count() > 0 else None
        )
        self.custom_dataset_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            self.custom_dataset_combo.clear()
            if self.current_project:
                display_names = dict(dataset_display_options(self.current_project))
                for item in self.current_project.get_all_items():
                    if isinstance(item, Dataset):
                        self.custom_dataset_combo.addItem(display_names[item.id], item.id)

            if previously_selected_id is not None:
                restored_index = self.custom_dataset_combo.findData(previously_selected_id)
                if restored_index >= 0:
                    self.custom_dataset_combo.setCurrentIndex(restored_index)
        finally:
            self.custom_dataset_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

        self._populate_custom_column_combos(self.custom_dataset_combo.currentData())

    def _populate_custom_column_combos(self, dataset_id):
        """Fill custom_x_column_combo/custom_y_column_combo with the columns
        of `dataset_id`, mirroring data_tab.py's _populate_column_combos."""
        self.custom_x_column_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        self.custom_y_column_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            self.custom_x_column_combo.clear()
            self.custom_y_column_combo.clear()

            dataset = self.current_project.find_item(dataset_id) if dataset_id and self.current_project else None
            if isinstance(dataset, Dataset) and dataset.data is not None:
                for column in dataset.data.columns:
                    column_id = dataset.column_id(column) or ""
                    self.custom_x_column_combo.addItem(column, column_id)
                    self.custom_y_column_combo.addItem(column, column_id)
                if self.custom_y_column_combo.count() >= 2:
                    self.custom_y_column_combo.setCurrentIndex(1)
        finally:
            self.custom_x_column_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self.custom_y_column_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _on_custom_dataset_changed(self):
        self._populate_custom_column_combos(self.custom_dataset_combo.currentData())
        self._clear_results()
        self.range_auto_check.setChecked(True)
        self.update_data_points_display()

    def _on_custom_column_changed(self):
        self._clear_results()
        self.range_auto_check.setChecked(True)
        self.update_data_points_display()

    def _on_range_auto_toggled(self, checked: bool):  # noqa: FBT001 - Qt `toggled` callback, invoked positionally
        """Show the live data-range labels in Auto mode, or manual range
        entry (seeded from the current series' actual data range as a
        starting point) once Auto is unchecked."""
        self.range_min_spin.setVisible(not checked)
        self.range_max_spin.setVisible(not checked)
        self.range_min_value_label.setVisible(checked)
        self.range_max_value_label.setVisible(checked)

        if not checked:
            current_data = self.get_current_data()
            if current_data is not None:
                _, _, x_data, _, _ = current_data
                if len(x_data) > 0:
                    self.range_min_spin.setValue(float(x_data.min()))
                    self.range_max_spin.setValue(float(x_data.max()))

        self.update_data_points_display()

    def _is_range_valid(self) -> bool:
        if self.range_auto_check.isChecked():
            return True
        if self.range_max_spin.value() <= self.range_min_spin.value():
            return False
        fit_name = self.fit_type_combo.currentText().split(" (")[0]
        if fit_name in ("Logarithmic", "Power") and self.range_min_spin.value() <= 0:
            return False
        return True

    def _range_invalid_reason(self) -> str:
        if self.range_max_spin.value() <= self.range_min_spin.value():
            return "Max must be greater than Min."
        return "Min must be greater than 0 for this fit type."

    def _on_chart_updated(self, event_data):
        chart = event_data.get("chart")

        if not chart:
            return

        if self.current_chart and chart.id != self.current_chart.id:
            return

        # Skip doing the reload now while the panel isn't visible, but
        # remember that a refresh is owed: showEvent reloads the current
        # chart fresh from the project on reactivation (unless a pending
        # tab change already takes care of it), so this update is picked
        # up either way. The relevance check above must run first -- an
        # update for some other chart shouldn't mark this one as needing
        # a refresh.
        if not self.isVisible():
            self._needs_chart_refresh = True
            return

        self.load_chart_object(chart)

    @override
    def showEvent(self, event):
        """Apply context that was skipped while the panel was hidden: replay
        a pending tab-change event, or -- if only a chart update was
        skipped -- reload the current chart fresh from the project."""
        super().showEvent(event)

        pending_tab_event = self._pending_tab_event_data
        self._pending_tab_event_data = None
        needs_chart_refresh = self._needs_chart_refresh
        self._needs_chart_refresh = False

        if pending_tab_event is not None:
            self._apply_tab_change(pending_tab_event)
        elif needs_chart_refresh and self.current_chart is not None:
            project = self.app_context.app_state.current_project
            chart = project.find_item(self.current_chart.id) if project else None
            self.load_chart_object(chart)

    def _insert_function(self, function_str):
        cursor_pos = self.custom_function_edit.cursorPosition()
        current_text = self.custom_function_edit.text()

        new_text = (
                current_text[:cursor_pos]
                + function_str
                + current_text[cursor_pos:]
        )

        self.custom_function_edit.setText(new_text)
        self.custom_function_edit.setCursorPosition(cursor_pos + len(function_str))

    def _perform_fit(self):
        """Create and execute a curve fitting command."""
        # update_data_points_display() (fired by unrelated range/series
        # changes while a fit is in flight) re-enables fit_button based only
        # on data validity, not on whether a fit is already running -- so a
        # click can still reach here mid-flight. Guard on the pending
        # command itself rather than trusting the button's enabled state.
        if self._pending_fit_command is not None:
            return

        current_data = self.get_current_data()

        if current_data is None:
            self.logger.warning("No data available for fitting")
            return

        df, mask, x_data, y_data, series = current_data

        fit_type = self.fit_type_combo.currentText()
        is_custom = fit_type.split(" (")[0] == "Custom Function"

        # Chart/series navigation stays enabled while a fit computes in the
        # background, so capture what the fit was actually requested for and
        # compare against the panel's context once the result is back --
        # applying a stale fit to whatever chart/series happens to be
        # selected when the background thread finishes would silently
        # attach the wrong data. Content-based (not object identity): a
        # "Custom..." selection builds a fresh transient DataSeries on every
        # _resolve_selected_series() call, so identity would always differ.
        dispatch_context = (
            self.current_chart.id if self.current_chart else None,
            series.dataset_id, series.x_column_id, series.y_column_id,
        )

        def _on_complete(result):
            self.busy_spinner.stop()
            self.fit_button.setEnabled(self.scipy_available)
            self._pending_fit_command = None

            current_series = self._resolve_selected_series()
            current_context = (
                self.current_chart.id if self.current_chart else None,
                current_series.dataset_id if current_series else None,
                current_series.x_column_id if current_series else None,
                current_series.y_column_id if current_series else None,
            )
            if current_context != dispatch_context:
                self.logger.info(
                    "Discarding stale fit result: chart/series changed while fitting."
                )
                return

            if result is not CommandResult.SUCCESS:
                self.logger.error("PerformFitCommand failed: %s", command.error_message)
                self._clear_results()
                self.results_text.setPlainText(command.error_message or "Fit failed.")
                self.results_text.setStyleSheet("color: red;")
                return

            self.fit_results = command.result
            self.fit_fixed_parameters = command.fixed_parameters
            self.display_results()
            self.apply_button.setEnabled(self.fit_results is not None)

        command = PerformFitCommand(
            fit_service=self.fit_service,
            fit_type=fit_type,
            x_data=x_data,
            y_data=y_data,
            fit_points=self.fit_points_spin.value(),
            calculate_r_squared=self.r_squared_check.isChecked(),
            confidence_bands=self.confidence_check.isChecked(),
            sigma_y=self.fit_service._extract_sigma_y(
                df,
                mask,
                series,
                dataset=self.current_project.find_item(series.dataset_id),
            ),
            custom_function=self.custom_function_edit.text() if is_custom else None,
            custom_parameters=self.custom_params_edit.text() if is_custom else None,
            fixed_parameters=self.initial_guess_edit.text() if is_custom else None,
            x_min=None if self.range_auto_check.isChecked() else self.range_min_spin.value(),
            x_max=None if self.range_auto_check.isChecked() else self.range_max_spin.value(),
            task_scheduler=self.app_context.get_task_scheduler(),
            on_complete=_on_complete,
        )
        self._pending_fit_command = command  # keep alive until on_complete fires

        # Disable Apply too: it's bound to the *previous* self.fit_results,
        # which must not be committable while a new fit is still computing.
        apply_was_enabled = self.apply_button.isEnabled()
        self.fit_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.busy_spinner.start()

        executor = self.app_context.get_command_executor()
        if not executor.execute_command(command):
            # Synchronous dispatch failure (e.g. a fit already in progress) --
            # on_complete never fires, so the previous result is still valid
            # and Apply's enabled state must be restored, not left disabled.
            self.busy_spinner.stop()
            self.fit_button.setEnabled(self.scipy_available)
            self.apply_button.setEnabled(apply_was_enabled)
            self._pending_fit_command = None

