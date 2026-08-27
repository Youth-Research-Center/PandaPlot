"""Dialog for browsing and opening bundled example projects."""

from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.examples import discover_example_projects


class ExamplesDialog(PDialog):
    """Lets the user browse bundled example projects and pick one to open.

    On acceptance, `selected_path` holds the chosen project's file path.
    """

    def __init__(self, app_context, parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self.selected_path: Optional[str] = None
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle("Examples")
        self.setModal(True)
        self.resize(520, 420)
        self.setMinimumSize(420, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("Example Projects")
        title_font = self.title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Open a bundled example to explore what PandaPlot can do.")
        layout.addWidget(self.subtitle_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent;")
        scroll_area.viewport().setStyleSheet("background: transparent;")

        list_widget = QWidget()
        list_widget.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)

        examples = discover_example_projects()
        if not examples:
            placeholder = QLabel("No example projects were found.")
            placeholder.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(placeholder)
        else:
            for example in examples:
                self.list_layout.addWidget(self._create_example_item(example))
        self.list_layout.addStretch()

        scroll_area.setWidget(list_widget)
        layout.addWidget(scroll_area)

        # Imported locally to avoid a circular import: pandaplot.gui.components.__init__
        # imports TabContainer -> WelcomeTab -> ExamplesDialog (this module), so a
        # top-level import of PButton (under gui.components.common) would fail.
        from pandaplot.gui.components.common.p_button import PButton

        self.close_btn = PButton("Cancel", role="secondary", on_click=self.reject)
        layout.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_example_item(self, example: dict) -> QPushButton:
        """Create a clickable card for one example project."""
        button = QPushButton()
        button.setObjectName("ExampleItemButton")
        button.setMinimumHeight(64)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        item_layout = QVBoxLayout(button)
        item_layout.setContentsMargins(14, 10, 14, 10)
        item_layout.setSpacing(4)

        name_label = QLabel(example["name"])
        name_font = name_label.font()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(name_label)

        if example["description"]:
            desc_label = QLabel(example["description"])
            desc_label.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            item_layout.addWidget(desc_label)

        button.clicked.connect(lambda: self._on_example_chosen(example["path"]))
        return button

    def _on_example_chosen(self, path: str):
        self.selected_path = path
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
            QPushButton#ExampleItemButton {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                text-align: left;
            }}
            QPushButton#ExampleItemButton:hover {{
                background-color: {card_hover};
                border-color: {accent};
            }}
            QPushButton#ExampleItemButton:pressed {{
                background-color: {card_pressed};
            }}
            QPushButton#ExampleItemButton QLabel {{
                background: transparent;
                border: 0px;
            }}
        """)
        self.subtitle_label.setStyleSheet(f"color: {secondary_fg};")
