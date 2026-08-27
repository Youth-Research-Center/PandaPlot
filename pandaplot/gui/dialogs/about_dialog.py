"""About dialog for the PandaPlot application."""

import platform
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.version import __app_name__, __description__, __version__


class AboutDialog(PDialog):
    """Shows application version, description, and runtime environment info."""

    def __init__(self, app_context, parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle(f"About {__app_name__}")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        self.icon_label = QLabel("🐼")
        icon_font = self.icon_label.font()
        icon_font.setPointSize(40)
        self.icon_label.setFont(icon_font)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(__app_name__)
        name_font = self.name_label.font()
        name_font.setPointSize(20)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        self.version_label = QLabel(f"Version {__version__}")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        self.description_label = QLabel(__description__)
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.description_label)

        self.info_frame = QFrame()
        self.info_frame.setObjectName("aboutInfoFrame")
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setHorizontalSpacing(16)
        info_layout.setVerticalSpacing(6)

        import matplotlib
        import pandas
        import PySide6

        environment_rows = [
            ("Python", platform.python_version()),
            ("PySide6 (Qt)", PySide6.__version__),
            ("pandas", pandas.__version__),
            ("Matplotlib", matplotlib.__version__),
            ("Platform", f"{platform.system()} {platform.release()}"),
        ]
        self.info_value_labels = []
        for row, (label_text, value_text) in enumerate(environment_rows):
            key_label = QLabel(f"{label_text}:")
            key_label.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
            value_label = QLabel(value_text)
            info_layout.addWidget(key_label, row, 0)
            info_layout.addWidget(value_label, row, 1)
            self.info_value_labels.append(value_label)
        layout.addWidget(self.info_frame)

        self.license_label = QLabel(
            "Released under the MIT License.\nCopyright © 2025 Youth Research Center."
        )
        self.license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.license_label.setWordWrap(True)
        layout.addWidget(self.license_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = PButton("Close", role="secondary", on_click=self.accept)
        self.close_btn.setDefault(True)
        button_layout.addWidget(self.close_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QLabel {{
                color: {base_fg};
            }}
            QLabel[secondary="true"] {{
                color: {secondary_fg};
            }}
        """)
        self.info_frame.setStyleSheet(f"""
            QFrame#aboutInfoFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
        """)
        self.version_label.setStyleSheet(f"color: {secondary_fg};")
        self.description_label.setStyleSheet(f"color: {secondary_fg};")
        self.license_label.setStyleSheet(f"color: {secondary_fg}; font-size: 11px;")
