from typing import override

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget

from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class IconBar(PWidget):
    """Icon bar component that holds panel toggle buttons."""

    panel_requested = Signal(str)  # Signal emitted when a panel is requested
    settings_requested = Signal()  # Signal emitted when settings button is clicked

    def __init__(self, app_context: AppContext, parent: QWidget, width: int = 40):
        super().__init__(app_context=app_context, parent=parent)
        self.icon_width = width
        self.panels = {}  # Store panel names and their buttons

        self._initialize()

    @override
    def _init_ui(self):
        """Create the settings gear button at the bottom of the icon bar."""
        self.setFixedWidth(self.icon_width)
        self.setMinimumWidth(self.icon_width)
        self.setMaximumWidth(self.icon_width)
        # Remove hardcoded styling - will be applied in _apply_theme

        # Set size policy to prevent any stretching
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Expanding)

        # Layout for icon buttons
        self.button_layout = QVBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(2)

        # Add stretch to push main panel buttons to top and settings to bottom
        self.button_layout.addStretch()
        
        self.settings_button = QPushButton("⚙️")
        # TODO: use command instead of signal
        # TODO: make settings button addition more generic so that icon bar doesn't know about settings
        self.settings_button.clicked.connect(self.settings_requested.emit)
        # Remove hardcoded styling - will be applied in _apply_theme
        self.settings_button.setToolTip("Settings")
        self.button_layout.addWidget(self.settings_button)

    @override
    def _apply_theme(self):
        """Apply theme styling to icon bar components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme colors for main background
        card_border = palette.get("card_border", "#dee2e6")
        
        # Apply theme to main icon bar background
        self.setStyleSheet(f"""
            IconBar {{
                background-color: {card_border};
            }}
        """)
        
        # Apply theme to settings button
        self._apply_settings_button_theme()
        
        # Apply theme to all panel buttons
        self._apply_panel_buttons_theme()
    
    def _apply_settings_button_theme(self):
        """Apply theme styling to settings button."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        card_hover = palette.get("card_hover", "#e5f3ff")
        card_pressed = palette.get("card_pressed", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        
        self.settings_button.setStyleSheet(f"""
            QPushButton {{
                border: none;
                padding: 5px;
                background-color: transparent;
                color: {base_fg};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {card_hover};
            }}
            QPushButton:pressed {{
                background-color: {card_pressed};
            }}
        """)
    
    def _apply_panel_buttons_theme(self):
        """Apply theme styling to all panel buttons."""
        # Apply styling to all existing panel buttons
        for panel_name, btn in self.panels.items():
            self._apply_button_theme(btn, is_active=False)
    
    def _apply_button_theme(self, button, is_active=False):
        """Apply theme styling to a single button."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        card_hover = palette.get("card_hover", "#e5f3ff")
        card_pressed = palette.get("card_pressed", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        accent = palette.get("accent", "#4A90E2")
        
        if is_active:
            button.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    padding: 5px;
                    background-color: {accent};
                    color: white;
                }}
                QPushButton:hover {{
                    background-color: {accent};
                    opacity: 0.8;
                }}
            """)
        else:
            button.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    padding: 5px;
                    background-color: transparent;
                    color: {base_fg};
                }}
                QPushButton:hover {{
                    background-color: {card_hover};
                }}
                QPushButton:pressed {{
                    background-color: {card_pressed};
                }}
            """)

    def add_panel_button(self, name: str, icon: str):
        """Add a new panel button to the icon bar."""
        btn = QPushButton(icon)
        btn.clicked.connect(lambda: self.panel_requested.emit(name))
        # Remove hardcoded styling - will be applied via theme

        # Insert before the stretch (which is before the settings button)
        # The layout has: [panel_buttons...] [stretch] [settings_button]
        # So we insert at position: layout.count() - 2 (before stretch and settings button)
        insert_position = max(0, self.button_layout.count() - 2)
        self.button_layout.insertWidget(insert_position, btn)
        self.panels[name] = btn
        
        # Apply theme styling to the new button
        self._apply_button_theme(btn, is_active=False)
        
        return btn

    def remove_panel_button(self, name: str):
        """Remove a panel button from the icon bar."""
        if name in self.panels:
            btn = self.panels[name]
            self.button_layout.removeWidget(btn)
            btn.deleteLater()
            del self.panels[name]

    def set_active_button(self, name: str):
        """Set the active button styling."""
        for panel_name, btn in self.panels.items():
            is_active = (panel_name == name)
            self._apply_button_theme(btn, is_active=is_active)
