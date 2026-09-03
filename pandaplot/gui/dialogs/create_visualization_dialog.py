"""Dialog for the Welcome tab's "Create Visualizations" getting-started step.

Lists the current project's charts (if any) so the user can jump back into
one, and always offers a "Create Chart" action that opens the chart wizard --
creating more charts is always a valid next step, unlike Explore Data's
import-or-create choice.
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
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.project.items import Chart
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_display_options import chart_display_options


class CreateVisualizationDialog(PDialog):
    """Lets the user jump to an existing chart, or create a new one via the wizard."""

    def __init__(self, app_context, on_create_chart: Callable[[], None], parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self._on_create_chart = on_create_chart
        self._initialize()

    def _get_project(self):
        app_state = self.app_context.get_app_state()
        return app_state.current_project if app_state.has_project else None

    def _get_charts(self) -> list[Chart]:
        project = self._get_project()
        if project is None:
            return []
        return [item for item in project.get_all_items() if isinstance(item, Chart)]

    @override
    def _init_ui(self):
        self.setWindowTitle("Create Visualizations")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        self.icon_label = QLabel("📊")
        icon_font = self.icon_label.font()
        icon_font.setPointSize(22)
        self.icon_label.setFont(icon_font)
        header_layout.addWidget(self.icon_label)

        self.title_label = QLabel("Create Visualizations")
        title_font = self.title_label.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.intro_label = QLabel(
            "Use the wizard to pick from line, scatter, bar, heatmap, and other series "
            "types, and combine multiple series on one chart to compare data."
        )
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        charts = self._get_charts()
        if charts:
            self.subtitle_label = QLabel("Select a chart to open it, or create a new one.")
            self.subtitle_label.setWordWrap(True)
            layout.addWidget(self.subtitle_label)
            display_names = dict(chart_display_options(self._get_project()))
            self._build_chart_list(layout, charts, display_names)
        else:
            self.subtitle_label = QLabel(
                "You don't have any charts yet. Create one to turn your data into a visualization."
            )
            self.subtitle_label.setWordWrap(True)
            layout.addWidget(self.subtitle_label)

        # Imported locally to avoid a circular import: pandaplot.gui.components.__init__
        # imports TabContainer -> WelcomeTab -> this module, so a top-level import of
        # PButton (under gui.components.common) would fail (see ExamplesDialog).
        from pandaplot.gui.components.common.p_button import PButton

        button_layout = QHBoxLayout()
        self.create_btn = PButton("Create Chart", role="primary", on_click=self._handle_create_chart)
        button_layout.addWidget(self.create_btn)
        button_layout.addStretch()
        self.close_btn = PButton("Close", role="secondary", on_click=self.accept)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)

    def _build_chart_list(self, layout: QVBoxLayout, charts: list[Chart], display_names: dict[str, str]):
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
        for chart in charts:
            display_name = display_names.get(chart.id, chart.name)
            list_layout.addWidget(self._create_chart_item(chart, display_name))
        list_layout.addStretch()

        scroll_area.setWidget(list_widget)
        layout.addWidget(scroll_area)

    def _create_chart_item(self, chart: Chart, display_name: str) -> QPushButton:
        series_count = len(chart.data_series)
        type_name = get_chart_type_spec(chart.chart_type).display_name
        detail_text = f"{type_name} chart · {series_count} series"
        button = QPushButton()
        button.setObjectName("ChartItemButton")
        button.setMinimumHeight(56)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Visible text lives in child QLabels (for independent name/detail
        # styling), which leaves the button itself unnamed for assistive tech.
        # display_name (not chart.name) is used here since two charts can
        # share a plain name -- see chart_display_options.
        button.setAccessibleName(display_name)
        button.setAccessibleDescription(detail_text)

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

        detail_label = QLabel(detail_text)
        detail_label.setProperty("secondary", True)  # noqa: FBT003 - Qt method, no keyword args
        detail_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item_layout.addWidget(detail_label)

        button.clicked.connect(lambda: self._open_chart(chart))
        return button

    def _open_chart(self, chart: Chart):
        from pandaplot.models.events.event_data import TabOpenRequestedData
        from pandaplot.models.events.event_types import UIEvents

        self.app_context.get_app_state().event_bus.emit(
            UIEvents.TAB_OPEN_REQUESTED,
            TabOpenRequestedData(item_id=chart.id, item_name=chart.name).to_dict(),
        )
        self.accept()

    def _handle_create_chart(self):
        self._on_create_chart()
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
            QPushButton#ChartItemButton {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                text-align: left;
            }}
            QPushButton#ChartItemButton:hover {{
                background-color: {card_hover};
                border-color: {accent};
            }}
            QPushButton#ChartItemButton:pressed {{
                background-color: {card_pressed};
            }}
            QPushButton#ChartItemButton QLabel {{
                background: transparent;
                border: 0px;
            }}
        """)
        self.intro_label.setStyleSheet(f"color: {secondary_fg};")
        self.subtitle_label.setStyleSheet(f"color: {secondary_fg};")
