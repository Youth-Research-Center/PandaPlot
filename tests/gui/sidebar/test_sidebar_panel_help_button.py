"""Tests for the "?" help button that SidebarPanel can show beside its title."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart_analysis.chart_analysis_panel import ChartAnalysisPanel
from pandaplot.gui.components.sidebar.chart_signal.chart_signal_analysis_panel import ChartSignalAnalysisPanel
from pandaplot.gui.components.sidebar.chart_transform.chart_transform_panel import ChartTransformPanel
from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.gui.components.sidebar.preprocessing.preprocessing_panel import PreprocessingPanel
from pandaplot.gui.components.sidebar.signal.signal_panel import SignalPanel
from pandaplot.gui.components.sidebar.statistics.descriptive_panel import DescriptiveStatsPanel
from pandaplot.gui.components.sidebar.statistics.statistics_panel import StatisticsPanel
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.help_types import (
    PANEL_TOPIC_ANALYSIS,
    PANEL_TOPIC_CHART_ANALYSIS,
    PANEL_TOPIC_CHART_SIGNAL,
    PANEL_TOPIC_CHART_TRANSFORM,
    PANEL_TOPIC_DESCRIPTIVE,
    PANEL_TOPIC_FIT,
    PANEL_TOPIC_PREPROCESSING,
    PANEL_TOPIC_SIGNAL,
    PANEL_TOPIC_STATISTICS,
    PANEL_TOPIC_TRANSFORM,
)

# Sidebar panels draw a title icon from these design tokens, so a mocked theme manager must provide them.
ICON_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **ICON_TOKENS}
    return ctx


class _TitlePanel(SidebarPanel):
    """Minimal panel that sets a title (optionally with a help topic)."""

    def __init__(self, app_context, title, help_topic=None):
        super().__init__(app_context)
        self._title_text = title
        self._topic = help_topic
        self._init_ui()

    def _init_ui(self):
        self._init_panel_layout()
        self._set_title(self._title_text, help_topic=self._topic)

    def _apply_theme(self):
        pass


def _make(app_context, title="Analysis Operations", help_topic="panel.analysis"):
    panel = _TitlePanel(app_context, title, help_topic)
    return panel


def test_help_button_exists_and_is_keyboard_focusable(app_context):
    panel = _make(app_context)

    assert panel.help_button is not None
    assert panel.help_topic == "panel.analysis"
    assert panel.help_button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert panel.help_button.toolTip() == "Open help for this panel"
    assert panel.title_label is not None
    assert panel.title_label.text() == "Analysis Operations"


@pytest.mark.parametrize("name", ["Analysis Operations", "Preprocessing"])
def test_help_button_accessible_text_uses_the_full_title(app_context, name):
    panel = _make(app_context, title=name)

    assert panel.help_button.accessibleName() == f"Help: {name}"
    assert panel.help_button.accessibleDescription() == f"Opens the Help window on the {name} topic"


def test_clicking_help_button_publishes_help_requested(app_context):
    panel = _make(app_context)

    panel.help_button.click()

    app_context.event_bus.emit.assert_called_once()
    event_type, data = app_context.event_bus.emit.call_args.args
    assert event_type == UIEvents.HELP_REQUESTED
    assert data["topic_id"] == "panel.analysis"


def test_without_topic_there_is_no_button_and_title_lives_in_the_row_container(app_context):
    panel = _make(app_context, help_topic=None)

    assert panel.help_button is None
    assert panel.help_topic is None
    row = panel.main_layout.itemAt(0).widget()
    assert row is panel._title_row
    assert panel.title_label.parentWidget() is row


def test_with_topic_title_lives_in_a_row_container(app_context):
    panel = _make(app_context)

    row = panel.main_layout.itemAt(0).widget()
    assert row is not panel.title_label
    assert panel.title_label.parentWidget() is row
    assert panel.help_button.parentWidget() is row


@pytest.mark.parametrize("help_topic", [None, "panel.analysis"])
def test_apply_title_theme_styles_title_row_and_button(app_context, help_topic):
    panel = _make(app_context, help_topic=help_topic)

    panel._apply_title_theme("#111111", "#dddddd")

    if help_topic is None:
        assert panel.title_label.styleSheet() == SidebarPanel.title_stylesheet("#111111", "#dddddd")
        return
    assert "#dddddd" in panel._title_row.styleSheet()
    assert "transparent" in panel.title_label.styleSheet()
    button_style = panel.help_button.styleSheet()
    assert "#111111" in button_style
    assert ":focus" in button_style


@pytest.mark.parametrize(
    ("panel_class", "expected"),
    [
        (TransformPanel, PANEL_TOPIC_TRANSFORM),
        (PreprocessingPanel, PANEL_TOPIC_PREPROCESSING),
        (AnalysisPanel, PANEL_TOPIC_ANALYSIS),
        (DescriptiveStatsPanel, PANEL_TOPIC_DESCRIPTIVE),
        (StatisticsPanel, PANEL_TOPIC_STATISTICS),
        (SignalPanel, PANEL_TOPIC_SIGNAL),
        (FitPanel, PANEL_TOPIC_FIT),
        (ChartAnalysisPanel, PANEL_TOPIC_CHART_ANALYSIS),
        (ChartSignalAnalysisPanel, PANEL_TOPIC_CHART_SIGNAL),
        (ChartTransformPanel, PANEL_TOPIC_CHART_TRANSFORM),
    ],
)
def test_analysis_panels_have_their_help_topic(app_context, panel_class, expected):
    panel = panel_class(app_context)

    assert isinstance(panel, QWidget)
    assert panel.help_button is not None
    assert panel.help_topic == expected
