"""Dialog for the Welcome tab's "Explore Data" getting-started step.

Shows the currently open project's datasets to jump straight into one, or
-- when there's no project open or it has no datasets yet -- offers to
import data or create a blank dataset instead.
"""

from typing import Callable, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.items import Dataset
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_display_options import dataset_display_options


class ExploreDataDialog(PDialog):
    """Lets the user jump to an existing dataset, or start one when none exist."""

    def __init__(self, app_context, on_import_data: Callable[[], None],
                 on_create_dataset: Callable[[], None], parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self._on_import_data = on_import_data
        self._on_create_dataset = on_create_dataset
        self._initialize()

    def _get_project(self):
        app_state = self.app_context.get_app_state()
        return app_state.current_project if app_state.has_project else None

    def _get_datasets(self) -> list[Dataset]:
        project = self._get_project()
        if project is None:
            return []
        return [item for item in project.get_all_items() if isinstance(item, Dataset)]

    @override
    def _init_ui(self):
        self.setWindowTitle("Explore Data")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        self.icon_label = QLabel("📈")
        icon_font = self.icon_label.font()
        icon_font.setPointSize(22)
        self.icon_label.setFont(icon_font)
        header_layout.addWidget(self.icon_label)

        self.title_label = QLabel("Explore Data")
        title_font = self.title_label.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.intro_label = QLabel(
            "Once you're in a dataset's data view, you can sort and filter columns, "
            "add computed columns, or transform values via the column/cell context menus."
        )
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        datasets = self._get_datasets()
        if datasets:
            self._build_dataset_list(layout, datasets)
        else:
            self._build_empty_state(layout)

        # Imported locally to avoid a circular import: pandaplot.gui.components.__init__
        # imports TabContainer -> WelcomeTab -> this module, so a top-level import of
        # PButton (under gui.components.common) would fail (see ExamplesDialog).
        from pandaplot.gui.components.common.p_button import PButton

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = PButton("Close", role="secondary", on_click=self.accept)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)

    def _build_dataset_list(self, layout: QVBoxLayout, datasets: list[Dataset]):
        self.subtitle_label = QLabel("Select a dataset to open it in the data view.")
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setMaximumHeight(260)
        scroll_area.setStyleSheet("background: transparent;")
        scroll_area.viewport().setStyleSheet("background: transparent;")

        list_widget = QWidget()
        list_widget.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        display_names = dict(dataset_display_options(self._get_project()))
        for dataset in datasets:
            display_name = display_names.get(dataset.id, dataset.name)
            list_layout.addWidget(self._create_dataset_item(dataset, display_name))
        list_layout.addStretch()

        scroll_area.setWidget(list_widget)
        layout.addWidget(scroll_area)

    def _create_dataset_item(self, dataset: Dataset, display_name: str) -> QPushButton:
        rows, cols = dataset.data.shape
        button = QPushButton()
        button.setObjectName("DatasetItemButton")
        button.setMinimumHeight(56)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Visible text lives in child QLabels (for independent name/shape
        # styling), which leaves the button itself unnamed for assistive tech.
        # display_name (not dataset.name) is used here since two datasets can
        # share a plain name -- see dataset_display_options.
        button.setAccessibleName(display_name)
        button.setAccessibleDescription(f"{rows} rows × {cols} columns")

        item_layout = QVBoxLayout(button)
        item_layout.setContentsMargins(14, 8, 14, 8)
        item_layout.setSpacing(2)

        name_label = QLabel(display_name)
        name_font = name_label.font()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(name_label)

        shape_label = QLabel(f"{rows} rows × {cols} columns")
        shape_label.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
        shape_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        shape_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(shape_label)

        button.clicked.connect(lambda: self._open_dataset(dataset))
        return button

    def _open_dataset(self, dataset: Dataset):
        from pandaplot.models.events.event_data import TabOpenRequestedData
        from pandaplot.models.events.event_types import UIEvents

        self.app_context.get_app_state().event_bus.emit(
            UIEvents.TAB_OPEN_REQUESTED,
            TabOpenRequestedData(item_id=dataset.id, item_name=dataset.name).to_dict(),
        )
        self.accept()

    def _build_empty_state(self, layout: QVBoxLayout):
        self.subtitle_label = QLabel(
            "You don't have any datasets yet. Import a file or start from a blank dataset."
        )
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        # Imported locally to avoid a circular import (see the PButton import in _init_ui).
        from pandaplot.gui.components.common.p_button import PButton

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        self.import_btn = PButton("Import Data", role="primary", on_click=self._handle_import_data)
        self.create_btn = PButton("Create Dataset", role="secondary", on_click=self._handle_create_dataset)
        actions_layout.addWidget(self.import_btn)
        actions_layout.addWidget(self.create_btn)
        layout.addLayout(actions_layout)

    def _handle_import_data(self):
        self._on_import_data()
        self.accept()

    def _handle_create_dataset(self):
        self._on_create_dataset()
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
            QPushButton#DatasetItemButton {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                text-align: left;
            }}
            QPushButton#DatasetItemButton:hover {{
                background-color: {card_hover};
                border-color: {accent};
            }}
            QPushButton#DatasetItemButton:pressed {{
                background-color: {card_pressed};
            }}
            QPushButton#DatasetItemButton QLabel {{
                background: transparent;
                border: 0px;
            }}
        """)
        self.intro_label.setStyleSheet(f"color: {secondary_fg};")
        self.subtitle_label.setStyleSheet(f"color: {secondary_fg};")
