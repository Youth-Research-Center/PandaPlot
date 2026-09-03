"""Richer informational dialog for Welcome tab getting-started steps that have
no concrete navigation target from the welcome tab (they describe actions
that only make sense inside an already-open project)."""

from typing import Sequence, override

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.services.theme.theme_manager import ThemeManager


class GettingStartedStepDialog(PDialog):
    """Shows a step's icon, an intro paragraph, and a bulleted list of tips."""

    def __init__(self, app_context, icon: str, title: str, intro: str,
                 tips: Sequence[str], parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self._icon = icon
        self._title = title
        self._intro = intro
        self._tips = tips
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle(self._title)
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        self.icon_label = QLabel(self._icon)
        icon_font = self.icon_label.font()
        icon_font.setPointSize(22)
        self.icon_label.setFont(icon_font)
        header_layout.addWidget(self.icon_label)

        self.title_label = QLabel(self._title)
        title_font = self.title_label.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.intro_label = QLabel(self._intro)
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        self.tips_labels = []
        for tip in self._tips:
            tip_label = QLabel(f"•  {tip}")
            tip_label.setWordWrap(True)
            layout.addWidget(tip_label)
            self.tips_labels.append(tip_label)

        # Imported locally to avoid a circular import: pandaplot.gui.components.__init__
        # imports TabContainer -> WelcomeTab -> this module, so a top-level import of
        # PButton (under gui.components.common) would fail (see ExamplesDialog).
        from pandaplot.gui.components.common.p_button import PButton

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = PButton("Got it", role="primary", on_click=self.accept)
        self.close_btn.setDefault(True)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#f8f9fa")
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
        """)
        self.intro_label.setStyleSheet(f"color: {secondary_fg};")
        for tip_label in self.tips_labels:
            tip_label.setStyleSheet(f"color: {secondary_fg};")
