
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class ChartCanvas(FigureCanvas):
    """Custom matplotlib canvas for displaying charts."""

    def __init__(self, width=10, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="white")
        super().__init__(self.fig)
        self.axes = self.fig.add_subplot(111)
        self.setParent(None)

        # Enable zoom and pan functionality
        self.setup_navigation()

        # Store original limits for reset functionality
        self.original_xlim = None
        self.original_ylim = None

    def setup_navigation(self):
        """Set up zoom and pan functionality."""
        # Enable matplotlib's built-in navigation toolbar functionality
        # This provides zoom, pan, and reset functionality
        from matplotlib.backends.backend_qt import NavigationToolbar2QT
        self.toolbar = NavigationToolbar2QT(self, self.parent())

        # Store the navigation toolbar for external access
        self.navigation_toolbar = self.toolbar

    def apply_navigation_theme(self, base_fg="#495057", surface_bg="#f8f9fa", border_color="#e9ecef"):
        """Apply theme-aware styling to the navigation toolbar."""
        if hasattr(self, "navigation_toolbar"):
            hover_bg = border_color
            pressed_bg = "#dee2e6"

            # More aggressive styling for matplotlib NavigationToolbar2QT
            self.navigation_toolbar.setStyleSheet(f"""
                QToolBar {{
                    background-color: {surface_bg};
                    border: 1px solid {border_color};
                    border-radius: 3px;
                    margin: 2px;
                    color: {base_fg};
                    spacing: 2px;
                }}
                QToolBar QToolButton {{
                    background-color: {surface_bg};
                    color: {base_fg};
                    border: 1px solid {border_color};
                    padding: 4px 6px;
                    margin: 1px;
                    border-radius: 3px;
                    font-size: 12px;
                    min-width: 24px;
                    min-height: 24px;
                }}
                QToolBar QToolButton:hover {{
                    background-color: {hover_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:pressed {{
                    background-color: {pressed_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:checked {{
                    background-color: {pressed_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:disabled {{
                    color: #999999;
                    background-color: {surface_bg};
                    border-color: #cccccc;
                }}
                QToolBar QLabel {{
                    color: {base_fg};
                    background-color: transparent;
                    padding: 2px;
                }}
                QToolBar QLineEdit {{
                    background-color: {surface_bg};
                    border: 1px solid {border_color};
                    color: {base_fg};
                    padding: 2px;
                    border-radius: 2px;
                }}
            """)

            # Force icon color update by setting the toolbar's palette
            # This is crucial for matplotlib's _icon() method to work correctly
            from PySide6.QtGui import QColor, QPalette
            palette = self.navigation_toolbar.palette()

            # Convert hex color to QColor
            fg_color = QColor(base_fg)
            bg_color = QColor(surface_bg)

            # Set palette colors that matplotlib's _icon() method checks
            # Matplotlib checks: self.palette().color(self.backgroundRole()).value() < 128
            # and uses: self.palette().color(self.foregroundRole())
            palette.setColor(QPalette.ColorRole.WindowText, fg_color)
            palette.setColor(QPalette.ColorRole.ButtonText, fg_color)
            palette.setColor(QPalette.ColorRole.Text, fg_color)
            palette.setColor(QPalette.ColorRole.Window, bg_color)
            palette.setColor(QPalette.ColorRole.Button, bg_color)
            palette.setColor(QPalette.ColorRole.Base, bg_color)

            self.navigation_toolbar.setPalette(palette)

            # Force toolbar to regenerate icons with new colors
            # This triggers matplotlib's icon color logic
            if hasattr(self.navigation_toolbar, "_actions"):
                for action_name, action in self.navigation_toolbar._actions.items():
                    if hasattr(action, "setIcon"):
                        # Get the original icon file name and regenerate it
                        # This forces matplotlib to re-evaluate the colors
                        try:
                            # Get the icon file from the toolbar's _icon method
                            # Based on matplotlib's NavigationToolbar2QT.toolitems
                            icon_mapping = {
                                "home": "home",
                                "back": "back",
                                "forward": "forward",
                                "pan": "move",
                                "zoom": "zoom_to_rect",
                                "configure_subplots": "subplots",
                                "edit_parameters": "qt4_editor_options",  # Edit axis button
                                "save_figure": "filesave"  # Save figure button
                            }
                            if action_name in icon_mapping:
                                new_icon = self.navigation_toolbar._icon(
                                    f"{icon_mapping[action_name]}.png")
                                action.setIcon(new_icon)
                        except Exception as e:
                            # If regeneration fails, continue with other actions
                            # Add some debug info
                            if hasattr(self, "logger"):
                                self.logger.debug(
                                    f"Failed to regenerate icon for {action_name}: {e}")
                            pass

    def store_original_limits(self):
        """Store the original axis limits for reset functionality."""
        if self.original_xlim is None:
            self.original_xlim = self.axes.get_xlim()
        if self.original_ylim is None:
            self.original_ylim = self.axes.get_ylim()

    def reset_zoom(self):
        """Reset zoom to original view."""
        if self.original_xlim and self.original_ylim:
            self.axes.set_xlim(self.original_xlim)
            self.axes.set_ylim(self.original_ylim)
            self.draw()

    def set_size(self, width, height):
        """Change the figure size."""
        self.fig.set_size_inches(width, height)
        self.fig.tight_layout()
        self.draw()
