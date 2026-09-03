"""Dialog offering the ways to get a project open, shown from the Welcome
tab's "Create or Open a Project" getting-started step."""

from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.services.theme.theme_manager import ThemeManager

# Public action identifiers returned via `selected_action`.
ACTION_NEW_PROJECT = "new_project"
ACTION_OPEN_PROJECT = "open_project"
ACTION_BROWSE_EXAMPLES = "browse_examples"


class CreateOrOpenProjectDialog(PDialog):
    """Lets the user pick how to get a project open.

    On acceptance, `selected_action` holds one of the ACTION_* constants.
    """

    def __init__(self, app_context, parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self.selected_action: Optional[str] = None
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle("Create or Open a Project")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("Create or Open a Project")
        title_font = self.title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Choose how you'd like to get started.")
        layout.addWidget(self.subtitle_label)

        options_layout = QVBoxLayout()
        options_layout.setSpacing(10)
        options_layout.addWidget(self._create_option_item(
            "📊  New Project", "Start a fresh, empty project", ACTION_NEW_PROJECT
        ))
        options_layout.addWidget(self._create_option_item(
            "📂  Open Project", "Open an existing project file from disk", ACTION_OPEN_PROJECT
        ))
        options_layout.addWidget(self._create_option_item(
            "📚  Browse Examples", "Explore a bundled sample project", ACTION_BROWSE_EXAMPLES
        ))
        layout.addLayout(options_layout)

        # Imported locally to avoid a circular import: pandaplot.gui.components.__init__
        # imports TabContainer -> WelcomeTab -> this module, so a top-level import of
        # PButton (under gui.components.common) would fail (see ExamplesDialog).
        from pandaplot.gui.components.common.p_button import PButton

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_btn = PButton("Cancel", role="secondary", on_click=self.reject)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def _create_option_item(self, title: str, description: str, action: str) -> QPushButton:
        """Create a clickable card for one option."""
        button = QPushButton()
        button.setObjectName("OptionItemButton")
        button.setMinimumHeight(60)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Visible text lives in child QLabels (for independent title/description
        # styling), which leaves the button itself unnamed for assistive tech.
        button.setAccessibleName(title)
        button.setAccessibleDescription(description)

        item_layout = QVBoxLayout(button)
        item_layout.setContentsMargins(14, 10, 14, 10)
        item_layout.setSpacing(4)

        title_label = QLabel(title)
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
        desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(desc_label)

        button.clicked.connect(lambda: self._on_option_chosen(action))
        return button

    def _on_option_chosen(self, action: str):
        self.selected_action = action
        self.accept()

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#f8f9fa")
        card_hover = palette.get("card_hover", "#e9ecef")
        card_pressed = palette.get("card_pressed", "#dee2e6")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")
        accent = palette.get("accent", "#4A90E2")

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
            QPushButton#OptionItemButton {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                text-align: left;
            }}
            QPushButton#OptionItemButton:hover {{
                background-color: {card_hover};
                border-color: {accent};
            }}
            QPushButton#OptionItemButton:pressed {{
                background-color: {card_pressed};
            }}
            QPushButton#OptionItemButton QLabel {{
                background: transparent;
                border: 0px;
            }}
        """)
        self.subtitle_label.setStyleSheet(f"color: {secondary_fg};")
