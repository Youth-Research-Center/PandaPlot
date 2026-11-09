"""The Chart Properties panel has a "?" button that opens its help topic."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import (
    CHART_PROPERTIES_TAB_TITLES,
    ChartPropertiesPanel,
)
from pandaplot.models.events import UIEvents
from pandaplot.services.help.content import panels
from pandaplot.services.help.help_types import PANEL_TOPIC_CHART_PROPERTIES


def _qapp() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_panel_has_a_focusable_help_button_for_its_topic() -> None:
    _qapp()
    panel = ChartPropertiesPanel(app_context=build_app_context())

    assert panel.help_topic == PANEL_TOPIC_CHART_PROPERTIES
    assert panel.help_button is not None
    assert panel.help_button.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_clicking_the_help_button_publishes_help_requested(monkeypatch) -> None:
    _qapp()
    panel = ChartPropertiesPanel(app_context=build_app_context())
    published: list[tuple[object, dict]] = []
    monkeypatch.setattr(panel, "publish_event", lambda event_type, data=None: published.append((event_type, data)))

    panel.help_button.click()

    assert len(published) == 1
    event_type, data = published[0]
    assert event_type == UIEvents.HELP_REQUESTED
    assert data["topic_id"] == PANEL_TOPIC_CHART_PROPERTIES


def test_panel_topic_text_names_every_tab() -> None:
    topic = next(t for t in panels.topics() if t.id == PANEL_TOPIC_CHART_PROPERTIES)
    text = " ".join((topic.summary, *topic.steps, topic.explanation))

    for title in CHART_PROPERTIES_TAB_TITLES:
        assert title in text
