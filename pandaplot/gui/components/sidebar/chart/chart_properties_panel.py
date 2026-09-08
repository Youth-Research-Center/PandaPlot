"""Chart properties side panel for configuring chart appearance and data."""
from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.chart import ApplyChartPropertiesCommand
from pandaplot.gui.components.common.dirty_footer import DirtyFooter
from pandaplot.gui.components.sidebar.chart.tabs.axes_tab import AxesTab
from pandaplot.gui.components.sidebar.chart.tabs.chart_tab import ChartTab
from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.gui.components.sidebar.chart.tabs.legend_tab import LegendTab
from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import ChartEvents, ProjectEvents, UIEvents
from pandaplot.models.project.items.chart import restore_chart_state, snapshot_chart_state
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartPropertiesPanel(SidebarPanel):
    """Side panel for configuring chart properties."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.command_executor = app_context.command_executor
        self.current_project = None
        self.current_chart = None  # Current Chart object being edited
        # Internal flags/state for safe UI updates
        self._updating_controls: bool = False  # Guard to prevent feedback loops
        self._has_unsaved_changes: bool = False
        # Baseline for Cancel and for Apply's undo: the chart state as of the
        # last load into this panel or the last Apply.
        self._loaded_snapshot: Optional[dict] = None

        self._initialize()

    @override
    def _init_ui(self):
        """Set up the user interface."""
        self._init_panel_layout()

        # Header
        self._set_title("📈 Chart Properties")

        # Tab widget for organizing chart properties. When the tab bar
        # doesn't fit the panel's width, `resizeEvent` swaps it for
        # `tab_selector_combo` (a dropdown driving the same pages) instead of
        # letting Qt shrink/elide/scroll the tab labels.
        self._tab_titles = ["Chart", "Data", "Style", "Axes", "Legend"]
        self.tab_selector_combo = QComboBox(self)
        self.tab_selector_combo.addItems(self._tab_titles)
        self.tab_selector_combo.setVisible(False)
        self.tab_selector_combo.currentIndexChanged.connect(self._on_tab_selector_combo_changed)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.currentChanged.connect(self._on_tab_widget_current_changed)

        # Style tab is constructed before the Chart tab (though added to the
        # tab widget after Data, below) because ChartTab.chartTypeChanged
        # needs to connect directly to self.style_tab.set_chart_type here.
        self.style_tab = StyleTab(self.app_context, self)
        self.style_tab.configChanged.connect(self._on_any_tab_config_changed)

        # Chart tab: chart identity (title, chart type, histogram bins)
        self.chart_tab = ChartTab(self)
        self.chart_tab.configChanged.connect(self._on_any_tab_config_changed)
        self.chart_tab.chartTypeChanged.connect(self.style_tab.set_chart_type)
        self.chart_tab.chartTypeChanged.connect(lambda _value: self.data_tab.refresh_vector_fields())
        self.tab_widget.addTab(self._wrap_in_scroll_area(self.chart_tab), "Chart")

        # Axes tab: constructed before the Data tab (though added to the tab
        # widget after Style, below) because building the Data tab's series
        # cards calls `_rebuild_series_cards`, which calls
        # `self.axes_tab.refresh_axis_chips` to sync the Y2/Color chips.
        self.axes_tab = AxesTab(self.app_context, self)
        self.axes_tab.configChanged.connect(self._on_any_tab_config_changed)
        # A chart-type change can add or remove the Z axis chip (3-D types
        # only) and the 3-D camera card, so the Axes tab has to re-sync on
        # it -- the same reason StyleTab/DataTab listen above. Connected
        # here rather than beside those two because `self.axes_tab` doesn't
        # exist yet at that point.
        self.chart_tab.chartTypeChanged.connect(
            lambda _value: self.axes_tab.refresh_axis_chips(self.current_chart))

        # Data tab: series list + per-series dataset/X/Y/label configuration
        self.data_tab = DataTab(self.app_context, self)
        self.data_tab.configChanged.connect(self._on_any_tab_config_changed)
        self.data_tab.dirtyOnly.connect(self._on_dirty_only)
        self.data_tab.seriesSelected.connect(lambda kind, obj: self.style_tab.set_selected(kind, obj))
        self.data_tab.seriesListChanged.connect(
            lambda ds, fd: self.style_tab.set_series_list(ds, fd, self.data_tab.selected_index)
        )
        self.data_tab.axesRefreshRequested.connect(self._on_axes_refresh_requested)
        self.style_tab.seriesChipSelected.connect(self.data_tab._expand_series)
        self.tab_widget.addTab(self._wrap_in_scroll_area(self.data_tab), "Data")

        # Style tab (line/marker style)
        self.tab_widget.addTab(self._wrap_in_scroll_area(self.style_tab), "Style")

        self.tab_widget.addTab(self._wrap_in_scroll_area(self.axes_tab), "Axes")

        # Legend tab
        self.legend_tab = LegendTab(self)
        self.legend_tab.configChanged.connect(self._on_any_tab_config_changed)
        self.tab_widget.addTab(self._wrap_in_scroll_area(self.legend_tab), "Legend")

        # Footer: dirty-state indicator + Revert/Apply
        self.footer = DirtyFooter(self)
        self.footer.applyClicked.connect(self._on_apply)
        self.footer.revertClicked.connect(self._on_reset)

        body_widget = QWidget(self)
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.tab_selector_combo)
        body_layout.addWidget(self.tab_widget, stretch=1)
        body_layout.addWidget(self.footer)

        self._set_content(body_widget, scrollable=False)

    def _wrap_in_scroll_area(self, widget: QWidget) -> QScrollArea:
        """Wrap a tab's content in a vertically-scrolling QScrollArea.

        Without this, a tab whose content grows taller than the available
        space (e.g. Style's Chart/Line/Marker/Error Bars cards, or Axes'
        per-axis Range/Ticks cards) has nowhere to go: Qt propagates that
        minimum height all the way up to the main window, which can then
        fail to fit the screen (a `QWindowsWindow::setGeometry` warning,
        clamped to whatever height *does* fit, cutting off part of the
        window instead of just scrolling this one tab).
        """
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def _on_tab_selector_combo_changed(self, index):
        if index >= 0:
            self.tab_widget.setCurrentIndex(index)

    def _on_tab_widget_current_changed(self, index):
        if self.tab_selector_combo.currentIndex() != index:
            self.tab_selector_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.tab_selector_combo.setCurrentIndex(index)
            self.tab_selector_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _update_tab_bar_responsive_mode(self):
        """Switch between the native tab bar and `tab_selector_combo` based on
        available width, so tab labels never get elided/scrolled -- this only
        affects this panel's own tabs, not tab widgets elsewhere in the app."""
        tab_bar = self.tab_widget.tabBar()
        available_width = self.tab_widget.width()
        fits = tab_bar.sizeHint().width() <= available_width if available_width > 0 else True
        tab_bar.setVisible(fits)
        self.tab_selector_combo.setVisible(not fits)

    @override
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_tab_bar_responsive_mode()

    @override
    def _apply_theme(self):
        """Apply theme styling to all components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme colors with fallbacks
        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        card_hover = palette.get("card_hover", "#e5f3ff")
        
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
        self._apply_title_theme(base_fg, card_border)
        
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
        
        # Footer (DirtyFooter) theme token propagation
        tokens = theme_manager.get_design_tokens()
        self.footer.set_tokens(tokens)
        self.chart_tab.apply_theme(tokens)

        # Style tab: shared widgets
        self.style_tab.apply_theme(tokens)

        # Data tab: series management buttons/cards/SegmentedControl.
        self.data_tab.apply_theme(tokens)

        # Axes tab: chip row plus each axis form's Card/SegmentedControl/
        # ToggleSwitch/SectionHeader widgets.
        self.axes_tab.apply_theme(tokens)

        # Legend tab: shared widgets
        self.legend_tab.apply_theme(tokens)


    def setup_event_subscriptions(self):
        """Set up event subscriptions for tab changes."""
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        self.subscribe_to_event(ChartEvents.SERIES_SELECTED, self._on_series_selected_event)
        # Ensure datasets populate after a project is loaded from file. AppState emits
        # 'project_loaded' (underscore) and 'first_project_loaded'. Also subscribe to the
        # canonical constant for forward compatibility.
        self.subscribe_to_event(ProjectEvents.PROJECT_LOADED, self._on_project_loaded)  # may not fire yet
        self.subscribe_to_event("project_loaded", self._on_project_loaded)
        self.subscribe_to_event("first_project_loaded", self._on_project_loaded)
        # A renamed dataset's display name in the Data tab's dataset combo
        # otherwise stays stale until the next tab switch re-triggers
        # set_project(); refresh it live instead.
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self._on_project_item_renamed)

    def _on_project_item_renamed(self, event_data):
        """Refresh dataset-name displays in the Data tab after a dataset rename.

        The rename payload doesn't carry an item type, so look the renamed
        item up to filter out chart/note/folder/etc. renames -- rebuilding
        is otherwise wasted work on every unrelated rename.
        """
        if not self.current_project:
            return
        item = self.current_project.find_item(event_data.get("item_id"))
        if isinstance(item, Dataset):
            self.data_tab.set_project(self.current_project)
            # The combo rebuild above doesn't touch the expanded-but-not-
            # selected series/fit detail rows, which render the dataset's
            # display name as static QLabel text via _dataset_display_name()
            # at card-build time -- rebuild those too so they don't go stale.
            if self.current_chart:
                self.data_tab._rebuild_series_cards()

    def _ensure_datasets_loaded(self):
        """Populate datasets if empty (idempotent)."""
        if not self.data_tab.datasets and self.app_context.app_state.current_project:
            self.set_project(self.app_context.app_state.current_project)

    def _on_project_loaded(self, event_data):
        """Handle project loaded to refresh dataset list and any active chart context."""
        project = event_data.get("project") or self.app_context.app_state.current_project
        if project:
            self.set_project(project)
            # If a chart tab already active, re-load to bind series list correctly
            if self.current_chart:
                self.load_chart_object(self.current_chart)
    
    def _on_tab_changed(self, event_data):
        """Handle tab change events to update context."""
        current_tab_type = event_data.get("tab_type")
        chart_id = event_data.get("tab_id")
        
        # Check if current tab is a chart tab
        if current_tab_type == "chart" and chart_id:
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
    
    def _on_series_selected_event(self, event_data):
        """Handle series selection event triggered by clicking on a chart or legend."""
        chart_id = event_data.get("chart_id")
        series_index = event_data.get("series_index")
        if not self.current_chart or chart_id != self.current_chart.id or series_index is None:
            return

        total_items = len(self.current_chart.data_series) + len(self.current_chart.fit_data)
        if 0 <= series_index < total_items:
            self.data_tab._expand_series(series_index)

    def _on_chart_updated(self, event_data):
        """Handle chart updated events to refresh the panel."""
        chart_id = event_data.get("chart_id")
        if not self.current_chart or chart_id != self.current_chart.id:
            return

        if "chart" in event_data:
            # Command-originated update (Apply execute/undo/redo, add/remove
            # series, fit added): the model changed outside this panel's live
            # edits, so re-sync all controls and re-capture the Cancel/Apply
            # baseline to match the new command boundary.
            # This branch always fires first (add/remove series and
            # fit-added events include both "chart" and "update_type"), making
            # the update_type branch below unreachable for those. That's fine
            # now that DataTab.load preserves the selected row for a reload of
            # the same chart object (only add/remove -- which can invalidate
            # the previous index -- clamp it; a genuinely different chart
            # still resets to 0).
            self.load_chart_object(self.current_chart)
            self.logger.debug("Chart properties panel reloaded for command-originated update")
            return

        update_type = event_data.get("update_type", "")
        if update_type in ["fit_added", "series_added", "series_removed"]:
            self.data_tab._rebuild_series_cards()
            self.logger.debug("Chart properties panel refreshed for update: %s", update_type)

    def _on_axes_refresh_requested(self):
        """Sync both the Axes tab's chip row (Y2/Color chips) and the Style
        tab's axis-style selector with whether any series currently uses
        the secondary Y axis or needs a Z column (see AxesTab.
        refresh_axis_chips / StyleTab.refresh_axis_style_selector)."""
        self.axes_tab.refresh_axis_chips(self.current_chart)
        self.style_tab.refresh_axis_style_selector(self.current_chart)

    def _on_any_tab_config_changed(self):
        if not self.current_chart:
            return
        self._has_unsaved_changes = True
        self._update_status_indicator()
        self.publish_event(ChartEvents.CHART_UPDATED, {
            "chart_id": self.current_chart.id,
            "update_type": "config_updated",
        })

    def _on_dirty_only(self):
        """Mark dirty and refresh the footer without publishing
        CHART_UPDATED -- used for edits that pre-refactor never published
        for (see `DataTab.dirtyOnly`)."""
        if not self.current_chart:
            return
        self._has_unsaved_changes = True
        self._update_status_indicator()

    def _update_status_indicator(self):
        """Update the footer to reflect unsaved changes."""
        self.footer.setModified(
            is_modified=self._has_unsaved_changes,
            change_count=1 if self._has_unsaved_changes else 0,
        )

    def _clear_controls(self):
        """Reset panel controls to neutral defaults without touching any chart."""
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.style_tab.clear_chart_style()
            self.chart_tab.clear()
            self.axes_tab.clear()
            self.legend_tab.clear()
            self.data_tab.clear()
        finally:
            self._updating_controls = previous_guard

    def set_project(self, project):
        """Set the current project."""
        self.current_project = project
        self.data_tab.set_project(project)

    def _on_apply(self):
        """Handle apply button click."""
        if not self.current_chart:
            return
        command = ApplyChartPropertiesCommand(
            self.app_context,
            chart_id=self.current_chart.id,
            apply_fn=self.apply_to_chart,
            old_snapshot=self._loaded_snapshot,
        )
        self.command_executor.execute_command(command)

        # The applied state is the new baseline for Cancel / the next Apply.
        self._loaded_snapshot = snapshot_chart_state(self.current_chart)
        self._has_unsaved_changes = False
        self._update_status_indicator()
    
    def _on_reset(self):
        """Revert live edits back to the last loaded/applied state."""
        if not self.current_chart or self._loaded_snapshot is None:
            return
        restore_chart_state(self.current_chart, self._loaded_snapshot)
        self.load_chart_object(self.current_chart)
        self.publish_event(ChartEvents.CHART_UPDATED, {
            "chart_id": self.current_chart.id,
            "update_type": "config_updated",
        })
    
    def load_chart_object(self, chart):
        """Load a Chart object into the panel for editing.

        Args:
            chart: Chart object to load, or None to clear
        """
        self.current_chart = chart
        self._loaded_snapshot = snapshot_chart_state(chart) if chart else None
        self._has_unsaved_changes = False
        self._update_status_indicator()

        if chart:
            # Ensure datasets are available (important after opening a project file)
            self._ensure_datasets_loaded()
            # Populate controls without letting their change signals write
            # half-loaded values back into chart.config (that feedback loop
            # corrupted chart settings on every tab switch).
            previous_guard = self._updating_controls
            self._updating_controls = True
            try:
                self.style_tab.load_chart_style(chart)

                # Expand the first series/fit entry and rebuild the card list
                # (this also (re)loads it into the config form controls, and
                # loads series/fit 0's style into the Style tab via the
                # seriesSelected signal chain).
                self.data_tab.load(chart)

                # Load configuration
                self.chart_tab.load(chart)
                # ChartTab.load sets the chart-type combo via setCurrentValue,
                # which blocks signals during a load (by design, so a load
                # never triggers live-write handlers). That means
                # chartTypeChanged never fires here, so StyleTab's cached
                # `_chart_type` (used to hide the Line card for Scatter
                # charts) must be synced explicitly, or it would keep
                # whatever chart type was cached from before this load (or
                # None, before the user ever touches the combo by hand).
                self.style_tab.set_chart_type(self.chart_tab.chart_type_control.currentValue())
                self.axes_tab.load(chart)
                self.legend_tab.load(chart)
            finally:
                self._updating_controls = previous_guard

        else:
            # Clear/default values
            self._clear_controls()

    def apply_to_chart(self, chart):
        """Apply current panel settings to a Chart object.

        Args:
            chart: Chart object to update
        """
        if not chart:
            return

        # Update basic chart properties
        self.style_tab.apply_chart_style_to(chart)
        self.chart_tab.apply_to(chart)
        self.axes_tab.apply_to(chart)
        self.legend_tab.apply_to(chart)

        # Apply style updates to the currently selected series or fit data.
        # Runs *before* DataTab may bootstrap a default series below, so this
        # only ever touches a series/fit that already existed prior to this
        # apply -- a freshly-bootstrapped series is never touched by
        # `apply_series_style_to` here.
        current_row = self.data_tab.selected_index
        if current_row >= 0:
            total_series = len(chart.data_series)

            if current_row < total_series:
                # Update data series
                series = chart.data_series[current_row]
                self.style_tab.apply_series_style_to(series)

                self.logger.debug(
                    "Applied style to data series %d: %s (color=%s, marker_color=%s)",
                    current_row, series.label,
                    getattr(series.style, "color", None),
                    getattr(getattr(series.style, "marker", None), "marker_color", None),
                )
            else:
                # Update fit data
                fit_index = current_row - total_series
                if 0 <= fit_index < len(chart.fit_data):
                    fit = chart.fit_data[fit_index]
                    self.style_tab.apply_fit_style_to(fit)

                    self.logger.debug(
                        "Applied style to fit data %d: %s (color=%s)",
                        fit_index, fit.label, fit.style.color
                    )

        # Data-tab-owned fields: re-asserts the selected series' y_axis, and
        # creates a default series (dataset/x/y/label/y_axis) if none exist
        # yet.
        had_series_before_apply = bool(chart.data_series)
        self.data_tab.apply_to(chart)

        if not had_series_before_apply and chart.data_series:
            # DataTab just bootstrapped a default series from zero. Seed
            # only color/line_width/marker_size directly from the Style
            # tab's currently-shown values at creation time -- *not* the
            # full `apply_series_style_to` above (which already ran, before
            # this series existed, so never touched it), so line_style/
            # alpha/marker_style/marker_color/marker_edge_color stay at the
            # DataSeries dataclass defaults rather than being overwritten
            # from whatever the Style tab happens to be showing.
            new_series = chart.data_series[-1]
            if hasattr(new_series.style, "color"):
                new_series.style.color = self.style_tab.line_color_row.currentColor()
            if hasattr(new_series.style, "line_width"):
                new_series.style.line_width = self.style_tab.line_width_slider.value()
            if hasattr(new_series.style, "marker"):
                new_series.style.marker.marker_size = self.style_tab.marker_size_slider.value()

        chart.update_modified_time()
    
