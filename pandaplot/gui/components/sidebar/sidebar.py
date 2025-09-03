from typing import Optional, override

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pandaplot.gui.components.sidebar.icon_bar import IconBar
from pandaplot.gui.components.sidebar.panels.panel_area import PanelArea
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.state.app_context import AppContext
from pandaplot.gui.core.widget_extension import PWidget


class CollapsibleSidebar(PWidget):
    """A collapsible sidebar that contains an icon bar and panel area."""

    def __init__(self, app_context: AppContext, parent: QWidget, width: int = 400, collapsed_width: int = 40):
        super().__init__(app_context=app_context, parent=parent)
        self.default_width = width
        self.collapsed_width = collapsed_width
        self.is_collapsed: bool = False
        self.active_panel: Optional[str] = None
        self.last_width: int = width
        self.auto_collapse_threshold: int = 100
        self.auto_expand_threshold: int = 60

        # Set initial size but allow resizing
        self.setMinimumWidth(self.collapsed_width)
        self.resize(self.default_width, self.height())

        # Timer to debounce resize events
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.check_auto_collapse)

        self._init_ui()
        self._apply_theme()
        self.setup_event_subscriptions()

    @override
    def _init_ui(self):
        """Initialize the UI components."""
        # Main horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create icon bar
        self.icon_bar = IconBar(app_context=self.app_context, parent=self, width=self.collapsed_width)
        self.icon_bar.panel_requested.connect(self.show_panel)
        self.icon_bar.settings_requested.connect(
            self.show_settings_dialog)
        main_layout.addWidget(self.icon_bar, 0)

        # Create panel area
        self.panel_area = PanelArea(parent=self)
        main_layout.addWidget(self.panel_area, 1)

    def add_panel(self, name: str, icon, content_widget):
        """
        Add a new panel to the sidebar.

        Args:
            name (str): Unique identifier for the panel
            icon (str): Icon character or text for the button
            content_widget (QWidget): Widget to display in the panel
        """
        # Add button to icon bar
        self.icon_bar.add_panel_button(name, icon)

        # Add panel to panel area
        self.panel_area.add_panel(name, content_widget)

    def remove_panel(self, name):
        """Remove a panel from the sidebar."""
        self.icon_bar.remove_panel_button(name)
        self.panel_area.remove_panel(name)

        # Update active panel if it was removed
        if self.active_panel == name:
            self.active_panel = None

    def show_settings_dialog(self):
        """Show the settings dialog."""
        # TODO: not sure if we should handle this with a command
        dialog = SettingsDialog(self.app_context, self)
        dialog.exec()

    def show_panel(self, name):
        """Show a specific panel."""
        # If clicking the same panel that's already active, toggle collapse/expand
        if self.active_panel == name:
            self.toggle()
        else:
            # Switch to a different panel
            if self.panel_area.show_panel(name):
                self.active_panel = name
                self.icon_bar.set_active_button(name)

                # If sidebar is collapsed, expand it to show the new panel
                if self.is_collapsed:
                    if self.width() <= self.auto_expand_threshold:
                        # Reset width constraints and resize to show content
                        self.setMinimumWidth(self.collapsed_width)
                        self.setMaximumWidth(16777215)
                        self.resize(max(self.last_width, 200), self.height())
                    self.is_collapsed = False
                    self.panel_area.show()

    def toggle(self):
        """Toggle the sidebar between collapsed and expanded states."""
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            # Store current width before collapsing
            self.last_width = self.width()
            self.panel_area.hide()
            self.setFixedWidth(self.collapsed_width)
        else:
            self.panel_area.show()
            # Restore to previous width and allow resizing again
            self.setMinimumWidth(self.collapsed_width)
            self.setMaximumWidth(16777215)
            self.resize(self.last_width, self.height())

    def resizeEvent(self, event):
        """Handle resize events to auto-collapse when needed."""
        super().resizeEvent(event)
        # Start/restart the timer to debounce resize events
        self.resize_timer.start(100)

    def check_auto_collapse(self):
        """Check if sidebar should auto-collapse based on width."""
        current_width = self.width()

        # Auto-collapse if width is below collapse threshold and not already collapsed
        if current_width <= self.auto_collapse_threshold and not self.is_collapsed:
            self.last_width = current_width
            self.is_collapsed = True
            self.panel_area.hide()
            self.resize(self.collapsed_width, self.height())

        # Auto-expand if width is above expand threshold and currently collapsed
        elif current_width > self.auto_expand_threshold and self.is_collapsed:
            self.is_collapsed = False
            self.panel_area.show()

    def get_active_panel(self):
        """Get the name of the currently active panel."""
        return self.active_panel

    def is_panel_visible(self, name):
        """Check if a specific panel is currently visible."""
        return self.active_panel == name and not self.is_collapsed

    def _on_theme_changed(self, _data: dict):
        """Handle theme changes by reapplying sidebar styling."""
        try:
            self._apply_theme()
        except Exception as e:
            self.logger.warning("Failed applying theme change to sidebar: %s", e)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to the sidebar based on current theme."""
        theme_manager = self.app_context.get_theme_manager()
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        panel_bg = palette.get('card_bg', '#ffffff')
        
        # Apply theme to sidebar background
        self.setStyleSheet(f"QWidget {{ background-color: {panel_bg}; }}")
        
            