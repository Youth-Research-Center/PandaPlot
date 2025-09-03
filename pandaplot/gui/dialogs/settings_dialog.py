"""
Modern Settings dialog for the pandaplot application.
Provides a user interface for changing application preferences with modern PySide6 styling.
"""

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTabWidget, QWidget, QLabel, QGroupBox, QComboBox,
                             QSpinBox, QCheckBox, QFrame, QColorDialog,
                             QMessageBox, QScrollArea)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from typing import Dict, Any, Optional, override


from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.events.event_types import ConfigEvents
from pandaplot.models.state.config import ApplicationConfig

THEME_DISPLAY = {
    'light': 'Light',
    'dark': 'Dark',
    'system': 'Auto (System)'
}
THEME_REVERSE = {v: k for k, v in THEME_DISPLAY.items()}


class SettingsDialog(PDialog):
    """Modern settings dialog for configuring application preferences."""
    
    settings_changed = Signal(dict)  # Emitted when settings are applied
    
    def __init__(self, app_context, parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self.original_settings: Dict[str, Any] = {}
        self.current_settings: Dict[str, Any] = {}
        self._config_manager = self.app_context.get_config_manager()
        self._applying = False  # guard to prevent feedback loops

        self._init_ui()
        self._apply_theme()
        self.load_current_settings()
        self.setup_event_subscriptions()
    
    @override
    def _init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("⚙️ Application Settings")
        self.setModal(True)
        self.resize(700, 500)
        self.setMinimumSize(650, 450)
        
        # Remove hardcoded styling - will be applied in _apply_theme
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        self.create_header(layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_general_tab()
        self.create_appearance_tab()
        self.create_editor_tab()

        # Buttons
        self.create_buttons(layout)

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
        
        # Apply main dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QTabWidget::pane {{
                border: 1px solid {card_border};
                border-radius: 6px;
                background-color: {card_bg};
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background-color: {card_hover};
                border: 1px solid {card_border};
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: bold;
                color: {base_fg};
            }}
            QTabBar::tab:selected {{
                background-color: {card_bg};
                border-bottom: 1px solid {card_bg};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {card_bg};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {card_border};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: {card_bg};
                color: {secondary_fg};
            }}
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {accent};
                opacity: 0.8;
            }}
            QPushButton:pressed {{
                background-color: {accent};
                opacity: 0.6;
            }}
            QLabel {{
                color: {base_fg};
            }}
            QSpinBox, QComboBox {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 3px;
                padding: 2px 5px;
                color: {base_fg};
            }}
            QSpinBox:focus, QComboBox:focus {{
                border-color: {accent};
            }}
            QCheckBox {{
                color: {base_fg};
            }}
        """)
        
        # Apply specific button styling
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {secondary_fg};
                color: white;
            }}
            QPushButton:hover {{
                background-color: #545b62;
            }}
        """)
        
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {secondary_fg};
                color: white;
            }}
            QPushButton:hover {{
                background-color: #545b62;
            }}
        """)
        
        # Apply styling to button frame
        self.button_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
        """)
        
        # Apply styling to header labels
        self.title_label.setStyleSheet(f"font-size:18px; font-weight:600; color: {base_fg};")
        self.subtitle_label.setStyleSheet(f"color: {secondary_fg};")

    def create_header(self, parent_layout: QVBoxLayout):
        """Create dialog header area."""
        header_box = QFrame()
        hb_layout = QVBoxLayout(header_box)
        self.title_label = QLabel("Application Settings")
        # Remove hardcoded styling - will be applied in _apply_theme
        self.subtitle_label = QLabel("Adjust preferences for appearance, editing and behavior")
        # Remove hardcoded styling - will be applied in _apply_theme
        hb_layout.addWidget(self.title_label)
        hb_layout.addWidget(self.subtitle_label)
        parent_layout.addWidget(header_box)

    def create_general_tab(self):
        """Create general settings tab with auto-save options."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        autosave_group = QGroupBox("💾 Auto Save")
        ag_layout = QVBoxLayout(autosave_group)
        self.auto_save_check = QCheckBox("Enable automatic project saving")
        ag_layout.addWidget(self.auto_save_check)
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))
        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(10, 3600)
        self.auto_save_interval.setSuffix(" s")
        self.auto_save_interval.setSingleStep(10)
        interval_layout.addWidget(self.auto_save_interval)
        interval_layout.addStretch()
        ag_layout.addLayout(interval_layout)
        layout.addWidget(autosave_group)

        # Chart display group (preview settings like DPI)
        chart_group = QGroupBox("📈 Chart Display Settings")
        cd_layout = QVBoxLayout(chart_group)
        
        # DPI setting
        dpi_layout = QHBoxLayout()
        dpi_label = QLabel("Preview DPI:")
        dpi_label.setStyleSheet("color: #495057;")
        dpi_layout.addWidget(dpi_label)
        self.chart_dpi_spin = QSpinBox()
        self.chart_dpi_spin.setRange(50, 600)
        self.chart_dpi_spin.setSingleStep(10)
        self.chart_dpi_spin.setSuffix(" dpi")
        self.chart_dpi_spin.setValue(100)  # default fallback; overwritten when loading settings
        self.chart_dpi_spin.setToolTip("Chart resolution for previews and exports")
        dpi_layout.addWidget(self.chart_dpi_spin)
        dpi_layout.addStretch()
        cd_layout.addLayout(dpi_layout)
        
        # Default chart size
        size_layout = QHBoxLayout()
        size_label = QLabel("Default size:")
        size_label.setStyleSheet("color: #495057;")
        size_layout.addWidget(size_label)
        self.chart_width_spin = QSpinBox()
        self.chart_width_spin.setRange(4, 20)
        self.chart_width_spin.setValue(8)
        self.chart_width_spin.setSuffix(" in")
        self.chart_width_spin.setToolTip("Default chart width in inches")
        size_layout.addWidget(self.chart_width_spin)
        
        multiply_label = QLabel("×")
        multiply_label.setStyleSheet("color: #495057;")
        size_layout.addWidget(multiply_label)
        
        self.chart_height_spin = QSpinBox()
        self.chart_height_spin.setRange(3, 15)
        self.chart_height_spin.setValue(6)
        self.chart_height_spin.setSuffix(" in")
        self.chart_height_spin.setToolTip("Default chart height in inches")
        size_layout.addWidget(self.chart_height_spin)
        size_layout.addStretch()
        cd_layout.addLayout(size_layout)
        
        layout.addWidget(chart_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "⚙️ General")

    def create_appearance_tab(self):
        """Create the appearance settings tab with scroll area to avoid clipping."""
        tab = QWidget()
        outer_layout = QVBoxLayout(tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll)

        container = QWidget()
        cont_layout = QVBoxLayout(container)
        cont_layout.setContentsMargins(20, 20, 20, 20)
        cont_layout.setSpacing(18)

        # Theme group
        theme_group = QGroupBox("🎨 Theme and Colors")
        theme_layout = QVBoxLayout(theme_group)
        theme_selection_layout = QHBoxLayout()
        theme_selection_layout.addWidget(QLabel("Application theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Auto (System)"])
        self.theme_combo.setCurrentText("Auto (System)")
        self.theme_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.theme_combo.setMinimumWidth(220)
        self.theme_combo.setToolTip("Select application theme (Light / Dark / Auto)")
        theme_selection_layout.addWidget(self.theme_combo)
        theme_selection_layout.addStretch()
        theme_layout.addLayout(theme_selection_layout)
        accent_layout = QHBoxLayout()
        accent_layout.addWidget(QLabel("Accent color:"))
        self.accent_color_btn = QPushButton()
        self.accent_color_btn.setFixedSize(70, 30)
        self.accent_color_btn.setStyleSheet("background-color: #007bff; border-radius: 4px;")
        self.accent_color_btn.clicked.connect(self.choose_accent_color)
        accent_layout.addWidget(self.accent_color_btn)
        accent_layout.addStretch()
        theme_layout.addLayout(accent_layout)
        cont_layout.addWidget(theme_group)

        # Font group
        font_group = QGroupBox("🔤 Fonts")
        font_layout = QVBoxLayout(font_group)
        interface_font_layout = QHBoxLayout()
        interface_font_layout.addWidget(QLabel("Interface font size:"))
        self.interface_font_size = QSpinBox()
        self.interface_font_size.setRange(8, 36)
        self.interface_font_size.setValue(12)
        self.interface_font_size.setSuffix(" pt")
        interface_font_layout.addWidget(self.interface_font_size)
        interface_font_layout.addStretch()
        font_layout.addLayout(interface_font_layout)
        editor_font_layout = QHBoxLayout()
        editor_font_layout.addWidget(QLabel("Editor font size:"))
        self.editor_font_size = QSpinBox()
        self.editor_font_size.setRange(8, 48)
        self.editor_font_size.setValue(12)
        self.editor_font_size.setSuffix(" pt")
        editor_font_layout.addWidget(self.editor_font_size)
        editor_font_layout.addStretch()
        font_layout.addLayout(editor_font_layout)
        cont_layout.addWidget(font_group)
        cont_layout.addStretch()

        scroll.setWidget(container)
        self.tab_widget.addTab(tab, "🎨 Appearance")
    
    def create_editor_tab(self):
        """Create the editor settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Text editing group
        editing_group = QGroupBox("📝 Text Editing")
        editing_layout = QVBoxLayout(editing_group)
        
        # Word wrap
        self.word_wrap_check = QCheckBox("Enable word wrap in note editor")
        self.word_wrap_check.setChecked(True)
        editing_layout.addWidget(self.word_wrap_check)
        
        # Show line numbers
        self.line_numbers_check = QCheckBox("Show line numbers")
        self.line_numbers_check.setChecked(False)
        editing_layout.addWidget(self.line_numbers_check)
        
        # Tab size
        tab_size_layout = QHBoxLayout()
        tab_size_layout.addWidget(QLabel("Tab size:"))
        self.tab_size_spin = QSpinBox()
        self.tab_size_spin.setRange(2, 8)
        self.tab_size_spin.setValue(4)
        self.tab_size_spin.setSuffix(" spaces")
        tab_size_layout.addWidget(self.tab_size_spin)
        tab_size_layout.addStretch()
        editing_layout.addLayout(tab_size_layout)
        
        layout.addWidget(editing_group)
        layout.addStretch()
        self.tab_widget.addTab(tab, "📝 Editor")
    
    def create_buttons(self, layout):
        """Create the button frame."""
        self.button_frame = QFrame()
        # Remove hardcoded styling - will be applied in _apply_theme
        button_layout = QHBoxLayout(self.button_frame)
        button_layout.setContentsMargins(16, 12, 16, 12)
        
        # Reset button
        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        # Remove hardcoded styling - will be applied in _apply_theme
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.reset_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        self.cancel_btn = QPushButton("❌ Cancel")
        # Remove hardcoded styling - will be applied in _apply_theme
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # Apply button
        self.apply_btn = QPushButton("✅ Apply")
        self.apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_btn)
        
        # OK button
        self.ok_btn = QPushButton("💾 OK")
        self.ok_btn.clicked.connect(self.accept_settings)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)
        
        layout.addWidget(self.button_frame)
    
    def load_current_settings(self):
        """Load current settings from the configuration manager (or defaults)."""
        cfg: Optional[ApplicationConfig] = None
        if self._config_manager is not None:
            cfg = self._config_manager.config
        if cfg is None:
            cfg = ApplicationConfig.default()

        self.original_settings = {
            'auto_save': cfg.auto_save.enabled,
            'auto_save_interval': cfg.auto_save.interval_seconds,
            'theme': THEME_DISPLAY.get(cfg.appearance.theme.value, 'Auto (System)'),
            'accent_color': cfg.appearance.accent_color,
            'interface_font_size': cfg.appearance.interface_font_size,
            'editor_font_size': cfg.appearance.editor_font_size,
            'word_wrap': cfg.editor.word_wrap,
            'line_numbers': cfg.editor.line_numbers,
            'tab_size': cfg.editor.tab_size,
            'chart_dpi': getattr(getattr(cfg, 'chart_display', None), 'dpi', 100),
        }
        self.current_settings = self.original_settings.copy()

        # TODO: call apply only if the settings changed
        self.apply_settings_to_ui()

    def setup_event_subscriptions(self):
        """Subscribe to config update events to reflect external changes while dialog open."""
        super().setup_event_subscriptions()

        # Subscribe to both updated and reset events
        self.subscribe_to_event(ConfigEvents.CONFIG_UPDATED, self._on_config_event)
    
    def _on_config_event(self, data: Dict[str, Any]):
        if self._applying:
            return
        config = data.get('config')
        if not config:
            return
        # Re-load from live config
        self.load_current_settings()

    def apply_settings_to_ui(self):
        """Apply current settings to UI controls."""
        self.auto_save_check.setChecked(self.current_settings['auto_save'])
        self.auto_save_interval.setValue(self.current_settings['auto_save_interval'])
        self.theme_combo.setCurrentText(self.current_settings['theme'])
        self.interface_font_size.setValue(self.current_settings['interface_font_size'])
        self.editor_font_size.setValue(self.current_settings['editor_font_size'])
        self.word_wrap_check.setChecked(self.current_settings['word_wrap'])
        self.line_numbers_check.setChecked(self.current_settings['line_numbers'])
        self.tab_size_spin.setValue(self.current_settings['tab_size'])
        if 'chart_dpi' in self.current_settings:
            self.chart_dpi_spin.setValue(self.current_settings['chart_dpi'])
        if 'chart_width' in self.current_settings:
            self.chart_width_spin.setValue(self.current_settings['chart_width'])
        if 'chart_height' in self.current_settings:
            self.chart_height_spin.setValue(self.current_settings['chart_height'])
        
        # Update accent color button
        color = self.current_settings['accent_color']
        self.accent_color_btn.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
    
    def get_current_settings_from_ui(self) -> Dict[str, Any]:
        """Get current settings from UI controls."""
        return {
            'auto_save': self.auto_save_check.isChecked(),
            'auto_save_interval': self.auto_save_interval.value(),
            'theme': self.theme_combo.currentText(),
            'accent_color': self.current_settings['accent_color'],  # Updated via color picker
            'interface_font_size': self.interface_font_size.value(),
            'editor_font_size': self.editor_font_size.value(),
            'word_wrap': self.word_wrap_check.isChecked(),
            'line_numbers': self.line_numbers_check.isChecked(),
            'tab_size': self.tab_size_spin.value(),
            'chart_dpi': self.chart_dpi_spin.value(),
            'chart_width': self.chart_width_spin.value(),
            'chart_height': self.chart_height_spin.value()
        }
    
    def choose_accent_color(self):
        """Open color picker for accent color."""
        current_color = QColor(self.current_settings['accent_color'])
        color = QColorDialog.getColor(current_color, self, "Choose Accent Color")
        
        if color.isValid():
            color_str = color.name()
            self.current_settings['accent_color'] = color_str
            self.accent_color_btn.setStyleSheet(f"background-color: {color_str}; border-radius: 4px;")
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self._config_manager:
                self._config_manager.reset(save=True)
            self.load_current_settings()
    
    def apply_settings(self):
        """Apply settings without closing the dialog."""
        self.current_settings = self.get_current_settings_from_ui()
        self._applying = True
        try:
            if self._config_manager:
                # Build mapping for config update
                mapping = {
                    'auto_save': {
                        'enabled': self.current_settings['auto_save'],
                        'interval_seconds': self.current_settings['auto_save_interval'],
                    },
                    'appearance': {
                        'theme': THEME_REVERSE.get(self.current_settings['theme'], 'system'),
                        'accent_color': self.current_settings['accent_color'],
                        'interface_font_size': self.current_settings['interface_font_size'],
                        'editor_font_size': self.current_settings['editor_font_size'],
                    },
                    'editor': {
                        'word_wrap': self.current_settings['word_wrap'],
                        'line_numbers': self.current_settings['line_numbers'],
                        'tab_size': self.current_settings['tab_size'],
                    },
                    'chart_display': {
                        'dpi': self.current_settings.get('chart_dpi', 100)
                    }
                }
                self._config_manager.update(mapping, save=True)
            self.settings_changed.emit(self.current_settings)
        finally:
            self._applying = False
    
    def accept_settings(self):
        """Apply settings and close the dialog."""
        self.apply_settings()
        self.accept()
    
    def reject(self):
        """Cancel and close the dialog without applying changes."""
        # Check if settings have changed
        current_ui_settings = self.get_current_settings_from_ui()
        
        if current_ui_settings != self.original_settings:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to close without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        super().reject()
    
    @staticmethod
    def show_settings_dialog(app_context, parent=None):
        """Convenient static method to show the settings dialog."""
        dialog = SettingsDialog(app_context, parent)
        return dialog.exec()
