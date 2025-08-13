"""
Conditional Panel Manager for managing sidebar panel visibility based on active tab state.
Provides a generic framework for panels that should appear/disappear based on context.
"""

from typing import Dict, Callable, Optional, Any
import logging
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.sidebar.sidebar import CollapsibleSidebar
from pandaplot.gui.components.tabs.tab_container import TabContainer


class ConditionalPanelManager(QObject):
    """
    Manages conditional visibility of sidebar panels based on active tab state.
    Provides a generic framework for panels that should appear/disappear based on context.
    """
    
    # Signals
    panel_visibility_changed = Signal(str, bool)  # panel_name, is_visible
    
    def __init__(self, sidebar: CollapsibleSidebar, tab_container: TabContainer):
        """
        Initialize with sidebar and tab container references.
        
        Args:
            sidebar: The collapsible sidebar widget
            tab_container: The tab container widget
        """
        super().__init__()
        self.sidebar = sidebar
        self.tab_container = tab_container
        self.registered_panels: Dict[str, Dict[str, Any]] = {}
        self.current_tab_widget: Optional[QWidget] = None
        self._logger = logging.getLogger(__name__)

        # Connect to tab change events
        self._connect_tab_events()
    
    def _connect_tab_events(self):
        """Connect to tab container events."""
        if hasattr(self.tab_container, 'tab_widget'):
            self.tab_container.tab_widget.currentChanged.connect(self._on_tab_index_changed)
    
    def register_conditional_panel(self, panel_name: str, condition_func: Callable[[QWidget], bool], priority: int = 0):
        """
        Register a panel with its visibility condition and priority.
        
        Args:
            panel_name: Name of the panel (must match sidebar panel name)
            condition_func: Function that takes current tab widget and returns bool
            priority: Priority for evaluation order (higher priority evaluated first)
        """
        self.registered_panels[panel_name] = {
            'condition_func': condition_func,
            'priority': priority,
            'is_visible': False
        }
        
        # Sort by priority (descending)
        self.registered_panels = dict(
            sorted(self.registered_panels.items(), 
                  key=lambda x: x[1]['priority'], 
                  reverse=True)
        )
        
        self._logger.debug("Registered panel '%s' priority=%s", panel_name, priority)
    
    def unregister_conditional_panel(self, panel_name: str):
        """
        Unregister a conditional panel.
        
        Args:
            panel_name: Name of the panel to unregister
        """
        if panel_name in self.registered_panels:
            del self.registered_panels[panel_name]
            self._logger.debug("Unregistered panel '%s'", panel_name)
    
    def _on_tab_index_changed(self, index: int):
        """
        Handle tab index change event.
        
        Args:
            index: The new tab index
        """
        if index >= 0:
            current_widget = self.tab_container.tab_widget.widget(index)
            self.on_tab_changed(current_widget)
        else:
            # No tab selected
            self.on_tab_changed(None)
    
    def on_tab_changed(self, current_tab_widget):
        """
        Called when active tab changes - evaluate all panel conditions.
        
        Args:
            current_tab_widget: The currently active tab widget (or None or int for tab index)
        """
        # Handle case where int (tab index) is passed instead of widget
        if isinstance(current_tab_widget, int):
            self._logger.debug("Received tab index %s -> converting to widget", current_tab_widget)
            if current_tab_widget >= 0:
                current_tab_widget = self.tab_container.tab_widget.widget(current_tab_widget)
            else:
                current_tab_widget = None
        
        self.current_tab_widget = current_tab_widget
        tab_class_name = type(current_tab_widget).__name__ if current_tab_widget else 'None'
        self._logger.debug("Tab changed to %s", tab_class_name)
        
        # Debug: Check if it's a dataset tab
        if current_tab_widget:
            is_dataset = tab_class_name == 'DatasetTab'
            self._logger.debug("Is dataset tab? %s", is_dataset)
        
        # Evaluate all panel conditions
        self.evaluate_panel_visibility()
    
    def evaluate_panel_visibility(self):
        """Check all registered panels and show/hide accordingly."""
        if not self.registered_panels:
            return
        
        for panel_name, panel_config in self.registered_panels.items():
            condition_func = panel_config['condition_func']
            previous_visibility = panel_config['is_visible']
            
            try:
                # Evaluate condition
                should_be_visible = condition_func(self.current_tab_widget)
                
                # Update visibility if changed
                if should_be_visible != previous_visibility:
                    panel_config['is_visible'] = should_be_visible
                    self._update_panel_visibility(panel_name, should_be_visible)
                    
                    # Emit signal
                    self.panel_visibility_changed.emit(panel_name, should_be_visible)
                    
                    self._logger.debug("Panel '%s' visibility changed -> %s", panel_name, should_be_visible)
                    
            except Exception:
                self._logger.error("Error evaluating condition for panel '%s'", panel_name, exc_info=True)
    
    def _update_panel_visibility(self, panel_name: str, should_be_visible: bool):
        """
        Update the actual panel visibility in the sidebar.
        
        Args:
            panel_name: Name of the panel
            should_be_visible: Whether the panel should be visible
        """
        # Update icon bar button visibility
        if panel_name in self.sidebar.icon_bar.panels:
            button = self.sidebar.icon_bar.panels[panel_name]
            button.setVisible(should_be_visible)
        
        if should_be_visible:
            # Show the panel if it exists and no panel is currently active
            if panel_name in self.sidebar.panel_area.panels:
                if not self.sidebar.active_panel:
                    self.sidebar.show_panel(panel_name)
        else:
            # Hide the panel if it's currently active
            if self.sidebar.active_panel == panel_name:
                # Find an alternative panel to show, or collapse sidebar
                alternative_panel = self._find_alternative_visible_panel()
                if alternative_panel:
                    self.sidebar.show_panel(alternative_panel)
                else:
                    # No visible panels, collapse sidebar
                    if not self.sidebar.is_collapsed:
                        self.sidebar.toggle()
    
    def _find_alternative_visible_panel(self) -> Optional[str]:
        """
        Find an alternative panel that should be visible.
        
        Returns:
            Name of an alternative visible panel, or None
        """
        for panel_name, panel_config in self.registered_panels.items():
            if panel_config['is_visible'] and panel_name in self.sidebar.panel_area.panels:
                return panel_name
        
        # Check for non-conditional panels (always visible)
        for panel_name in self.sidebar.panel_area.panels:
            if panel_name not in self.registered_panels:
                return panel_name
        
        return None
    
    def get_current_tab_context(self) -> dict:
        """
        Get current tab context information for condition evaluation.
        
        Returns:
            Dictionary with tab context information
        """
        context = {
            'current_tab_widget': self.current_tab_widget,
            'tab_type': type(self.current_tab_widget).__name__ if self.current_tab_widget else None,
            'has_tab': self.current_tab_widget is not None,
            'tab_count': self.tab_container.tab_widget.count() if hasattr(self.tab_container, 'tab_widget') else 0
        }
        
        # Add dataset-specific context if applicable
        if hasattr(self.current_tab_widget, 'dataset') and self.current_tab_widget is not None:
            dataset = getattr(self.current_tab_widget, 'dataset', None)
            if dataset:
                context.update({
                    'has_dataset': True,
                    'dataset_id': getattr(dataset, 'id', None),
                    'dataset_name': getattr(dataset, 'name', None),
                    'dataset_shape': getattr(dataset.data, 'shape', None) if hasattr(dataset, 'data') and dataset.data is not None else None
                })
            else:
                context['has_dataset'] = False
        else:
            context['has_dataset'] = False
        
        # Add chart-specific context if applicable
        if hasattr(self.current_tab_widget, 'chart') and self.current_tab_widget is not None:
            chart = getattr(self.current_tab_widget, 'chart', None)
            if chart:
                context.update({
                    'has_chart': True,
                    'chart_id': getattr(chart, 'id', None),
                    'chart_name': getattr(chart, 'name', None)
                })
            else:
                context['has_chart'] = False
        else:
            context['has_chart'] = False
        
        return context
    
    def get_panel_visibility_status(self) -> Dict[str, bool]:
        """
        Get current visibility status of all registered panels.
        
        Returns:
            Dictionary mapping panel names to their visibility status
        """
        return {panel_name: config['is_visible'] 
                for panel_name, config in self.registered_panels.items()}
    
    def force_evaluate_all_panels(self):
        """Force re-evaluation of all panel conditions."""
        self._logger.debug("Force evaluating all panel conditions")
        
        # Reset all visibility states
        for panel_config in self.registered_panels.values():
            panel_config['is_visible'] = False
        
        # Re-evaluate
        self.evaluate_panel_visibility()
    
    def is_panel_should_be_visible(self, panel_name: str) -> bool:
        """
        Check if a specific panel should be visible based on current context.
        
        Args:
            panel_name: Name of the panel to check
            
        Returns:
            True if panel should be visible, False otherwise
        """
        if panel_name not in self.registered_panels:
            return False
        
        condition_func = self.registered_panels[panel_name]['condition_func']
        
        try:
            return condition_func(self.current_tab_widget)
        except Exception:
            self._logger.error("Error checking visibility for panel '%s'", panel_name, exc_info=True)
            return False
