from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget


class IconBar(QWidget):
    """Icon bar component that holds panel toggle buttons."""

    panel_requested = Signal(str)  # Signal emitted when a panel is requested
    settings_requested = Signal()  # Signal emitted when settings button is clicked

    def __init__(self, width: int = 40, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.icon_width = width
        self.panels = {}  # Store panel names and their buttons
        self.settings_button = None  # Store settings button separately

        self.setFixedWidth(self.icon_width)
        self.setMinimumWidth(self.icon_width)
        self.setMaximumWidth(self.icon_width)
        self.setStyleSheet("background-color: #DCDCDC;")

        # Set size policy to prevent any stretching
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Expanding)

        # Layout for icon buttons
        self.button_layout = QVBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(2)

        # Add stretch to push main panel buttons to top and settings to bottom
        self.button_layout.addStretch()

        # Add settings button at the bottom
        self._create_settings_button()

    def _create_settings_button(self):
        """Create the settings gear button at the bottom of the icon bar."""
        self.settings_button = QPushButton("⚙️")
        # TODO: use command instead of signal
        # TODO: make settings button addition more generic so that icon bar doesn't know about settings
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self.settings_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 5px;
                background-color: transparent;
                color: black;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #BBBBBB;
            }
            QPushButton:pressed {
                background-color: #AAAAAA;
            }
        """)
        self.settings_button.setToolTip("Settings")
        self.button_layout.addWidget(self.settings_button)

    def add_panel_button(self, name: str, icon: str):
        """Add a new panel button to the icon bar."""
        btn = QPushButton(icon)
        btn.clicked.connect(lambda: self.panel_requested.emit(name))
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 5px;
                background-color: transparent;
                color: black;
            }
            QPushButton:hover {
                background-color: #CCCCCC;
            }
            QPushButton:pressed {
                background-color: #BBBBBB;
            }
        """)

        # Insert before the stretch (which is before the settings button)
        # The layout has: [panel_buttons...] [stretch] [settings_button]
        # So we insert at position: layout.count() - 2 (before stretch and settings button)
        insert_position = max(0, self.button_layout.count() - 2)
        self.button_layout.insertWidget(insert_position, btn)
        self.panels[name] = btn
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
            if panel_name == name:
                btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        padding: 5px;
                        background-color: #4A90E2;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #357ABD;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        padding: 5px;
                        background-color: transparent;
                        color: black;
                    }
                    QPushButton:hover {
                        background-color: #CCCCCC;
                    }
                    QPushButton:pressed {
                        background-color: #BBBBBB;
                    }
                """)
