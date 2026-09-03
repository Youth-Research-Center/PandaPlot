"""Chart Transform panel.

Applies a transform expression -- the same expression syntax the dataset
Transform panel uses -- to a chart series' X or Y values and stores the
result as a new dataset. The chart-series-scoped analogue of Chart
Analysis, powered by the transform expression engine instead of the
analysis engine (#268).
"""

import re
from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.chart.transform_chart_series_command import (
    TransformChartSeriesCommand,
)
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    populate_series_fit_sources,
    series_source_hint,
)
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ChartEvents, UIEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.services.transform import expression_engine

_EXPRESSION_REFERENCE_HTML = (
    "<b>Variables</b>: <code>x</code> and <code>y</code> are the series' full "
    "current axes -- both are always available, whichever one is the Target.<br>"
    "<b>Math</b>: <code>np.sqrt</code>, <code>np.log</code>, <code>np.log10</code>, "
    "<code>np.exp</code>, <code>np.abs</code>, <code>np.sin/cos/tan</code>, "
    "<code>np.sign</code>.<br>"
    "<b>Stats</b>: <code>x.mean()</code>, <code>x.std()</code>, "
    "<code>x.rolling(n).mean()</code>, <code>x.shift(1)</code>."
)


class ChartTransformPanel(PWidget):
    """Side panel for expression transforms on chart data/fit series."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.current_chart: Optional[Chart] = None
        self.current_chart_id: Optional[str] = None

        self._initialize()
        self._connect_signals()
        self._update_target_hint()

    @override
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.title_label = QLabel("🔧 Chart Transform")
        main_layout.addWidget(self.title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self._create_source_section(content_layout)
        self._create_target_section(content_layout)
        self._create_expression_section(content_layout)
        self._create_result_section(content_layout)
        self._create_preview_section(content_layout)
        self._create_action_buttons(content_layout)
        content_layout.addStretch()

        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)

    def _create_source_section(self, layout):
        group = QGroupBox("Series")
        form = QFormLayout(group)
        self.source_combo = QComboBox()
        form.addRow("Transform:", self.source_combo)
        self.source_hint = QLabel("Data series and fitted curves of this chart.")
        self.source_hint.setWordWrap(True)
        form.addRow(self.source_hint)
        layout.addWidget(group)

    def _create_target_section(self, layout):
        group = QGroupBox("Target")
        form = QFormLayout(group)
        self.target_combo = QComboBox()
        self.target_combo.addItem("Y", "y")
        self.target_combo.addItem("X", "x")
        form.addRow("Replace:", self.target_combo)
        self.target_hint = QLabel()
        self.target_hint.setWordWrap(True)
        form.addRow(self.target_hint)
        layout.addWidget(group)

    def _update_target_hint(self):
        """Spell out, in the UI, which axis the expression's result replaces
        -- both x and y stay available in the expression regardless of which
        one is the Target, so this is the only place that says which one
        actually changes (#268 follow-up: this was reported as unclear)."""
        target = self.target_combo.currentData() or "y"
        other = "x" if target == "y" else "y"
        self.target_hint.setText(
            f"The expression's result becomes the series' new {target.upper()} values "
            f"-- {other} stays as-is. Write the expression in terms of x and/or y."
        )

    def _create_expression_section(self, layout):
        group = QGroupBox("Transform Expression")
        vbox = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        self.insert_function_btn = QToolButton()
        self.insert_function_btn.setText("ƒ  Insert function ▾")
        self.insert_function_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.insert_function_btn.setMenu(self._build_function_menu())
        self.reference_btn = QToolButton()
        self.reference_btn.setText("?")
        self.reference_btn.setToolTip("Show the variables and functions you can use")
        self.reference_btn.clicked.connect(self._toggle_reference)
        toolbar.addWidget(self.insert_function_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.reference_btn)
        vbox.addLayout(toolbar)

        self.expression_text = QTextEdit()
        self.expression_text.setMaximumHeight(100)
        self.expression_text.setPlaceholderText(
            "x and y are the series' current axes -- e.g.\n"
            "  y * 2                (double the plotted values)\n"
            "  np.sqrt(y)           (square root)\n"
            "  (x - x.min()) / (x.max() - x.min())   (normalize x to 0-1)"
        )
        vbox.addWidget(self.expression_text)

        self.reference_label = QLabel(_EXPRESSION_REFERENCE_HTML)
        self.reference_label.setWordWrap(True)
        self.reference_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reference_label.setVisible(False)
        vbox.addWidget(self.reference_label)

        layout.addWidget(group)

    def _build_function_menu(self) -> QMenu:
        menu = QMenu(self)
        for category, entries in expression_engine.get_transformation_templates().items():
            submenu = menu.addMenu(category)
            for entry in entries:
                action = submenu.addAction(entry["name"])
                action.setToolTip(f"{entry['description']}  →  {entry['code']}")
                action.triggered.connect(
                    lambda _checked=False, code=entry["code"]: self._insert_function_code(code)
                )
        menu.setToolTipsVisible(True)
        return menu

    def _insert_function_code(self, code: str):
        """Insert a template's code, rewritten to the current Target axis.

        The templates (shared with the dataset Transform panel) are all
        written in terms of ``x``, e.g. ``"x * 2"``. Here that's a stand-in
        for "whichever axis you're replacing" -- so when Target is Y, insert
        ``"y * 2"`` instead, matching what the user is actually about to
        produce. \\b word-boundaries keep this from corrupting an
        identifier that merely contains an "x", e.g. ``np.exp(x)``.
        """
        target = self.target_combo.currentData() or "y"
        if target != "x":
            code = re.sub(r"\bx\b", target, code)
        if not self.expression_text.toPlainText().strip():
            self.expression_text.setPlainText(code)
        else:
            self.expression_text.insertPlainText(code)
        self.expression_text.setFocus()

    def _toggle_reference(self):
        self.reference_label.setVisible(not self.reference_label.isVisible())

    def _create_result_section(self, layout):
        group = QGroupBox("Result")
        form = QFormLayout(group)
        self.result_name = QLineEdit()
        self.result_name.setPlaceholderText("Auto-named from series and target")
        form.addRow("Dataset name:", self.result_name)
        layout.addWidget(group)

    def _create_preview_section(self, layout):
        group = QGroupBox("Preview")
        vbox = QVBoxLayout(group)
        self.preview_btn = PButton("Preview", role="secondary", on_click=self.preview)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(140)
        self.preview_text.setPlaceholderText("Preview results will appear here...")
        vbox.addWidget(self.preview_btn)
        vbox.addWidget(self.preview_text)
        layout.addWidget(group)

    def _create_action_buttons(self, layout):
        row = QHBoxLayout()
        self.apply_btn = PButton("Apply", role="primary", on_click=self.apply)
        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear_inputs)
        row.addWidget(self.apply_btn)
        row.addWidget(self.clear_btn)
        layout.addLayout(row)

    def _connect_signals(self):
        self.source_combo.currentIndexChanged.connect(self._auto_name)
        self.target_combo.currentIndexChanged.connect(self._auto_name)
        self.target_combo.currentIndexChanged.connect(self._update_target_hint)

    # -- config -------------------------------------------------------

    def _selected_source(self):
        return self.source_combo.currentData()

    def _make_command(self) -> Optional[TransformChartSeriesCommand]:
        source = self._selected_source()
        if source is None or self.current_chart_id is None:
            return None
        kind, index = source
        expression = self.expression_text.toPlainText().strip()
        if not expression:
            return None
        name = self.result_name.text().strip() or None
        folder_id = self.current_chart.parent_id if self.current_chart else None
        return TransformChartSeriesCommand(
            self.app_context,
            chart_id=self.current_chart_id,
            source_kind=kind,
            source_index=index,
            target=self.target_combo.currentData(),
            expression=expression,
            result_name=name,
            folder_id=folder_id,
        )

    # -- actions -------------------------------------------------------

    def preview(self):
        command = self._make_command()
        if command is None:
            self.preview_text.setText("❌ Select a series and enter an expression to transform.")
            return
        try:
            df, default_name = command.run_transform()
            lines = [
                f"Target: {self.target_combo.currentText()}",
                f"Series: {self.source_combo.currentText()}",
                f"Result: {len(df)} points → dataset '{self.result_name.text().strip() or default_name}'",
                "",
                "First rows:",
                df.head(5).to_string(index=False),
            ]
            self.preview_text.setText("\n".join(lines))
        except Exception as e:
            self.preview_text.setText(f"❌ Preview error: {e}")

    def apply(self):
        command = self._make_command()
        if command is None:
            self.preview_text.setText("❌ Select a series and enter an expression to transform.")
            return
        if self.app_context.get_command_executor().execute_command(command):
            self.preview_text.setText(
                "✅ Created a new dataset and added it to the chart as a series."
            )
        else:
            self.preview_text.setText(
                "❌ Could not transform the series. See the log for details."
            )

    def clear_inputs(self):
        self.result_name.clear()
        self.expression_text.clear()
        self.target_combo.setCurrentIndex(0)
        self.preview_text.clear()

    # -- chart context ---------------------------------------------------

    def _auto_name(self):
        if self.source_combo.count() == 0:
            return
        target = self.target_combo.currentText()
        self.result_name.setPlaceholderText(f"{self.source_combo.currentText()} ({target} transformed)")

    def _populate_sources(self):
        has_sources, any_series_excluded = populate_series_fit_sources(self.source_combo, self.current_chart)
        self.apply_btn.setEnabled(has_sources)
        self.preview_btn.setEnabled(has_sources)
        self.source_hint.setText(
            series_source_hint(has_sources=has_sources, any_series_excluded=any_series_excluded)
        )
        self._auto_name()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)

    def _on_tab_changed(self, event_data):
        if event_data.get("tab_type") == "chart":
            chart_id = event_data.get("tab_id")
            self.current_chart_id = chart_id
            project = self.app_context.get_app_state().current_project
            chart = project.find_item(chart_id) if project and chart_id else None
            self.current_chart = chart if isinstance(chart, Chart) else None
        else:
            self.current_chart = None
            self.current_chart_id = None
        self._populate_sources()

    def _on_chart_updated(self, event_data):
        chart = event_data.get("chart")
        if not chart or (self.current_chart_id and chart.id != self.current_chart_id):
            return
        if isinstance(chart, Chart):
            self.current_chart = chart
            self.current_chart_id = chart.id
            self._populate_sources()

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        self.setStyleSheet(f"""
            ChartTransformPanel {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 9pt;
                color: {base_fg};
                margin-top: 5px;
                padding-top: 10px;
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: {card_bg};
            }}
        """)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                color: {base_fg};
                padding: 5px;
                background-color: {card_border};
                border-radius: 3px;
            }}
        """)
        self.source_hint.setStyleSheet(
            f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        )
        self.target_hint.setStyleSheet(
            f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        )
