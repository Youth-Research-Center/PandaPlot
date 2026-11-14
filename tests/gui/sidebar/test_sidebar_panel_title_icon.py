"""The bundled icon SidebarPanel shows before its title, from `ICON_NAME`."""

from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import Theme
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens(Theme.LIGHT)
    return ctx


class _IconPanel(SidebarPanel):
    ICON_NAME = "chart-bar"

    def __init__(self, app_context, help_topic="panel.analysis"):
        super().__init__(app_context)
        self._topic = help_topic
        self._init_ui()

    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("Analysis Operations", help_topic=self._topic)

    def _apply_theme(self):
        pass


class _NoIconPanel(_IconPanel):
    ICON_NAME = None


def _strongest(label: IconLabel) -> QColor:
    image = label.pixmap().toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def _row_widgets(panel: SidebarPanel) -> list:
    layout = panel._title_row.layout()
    return [layout.itemAt(index).widget() for index in range(layout.count())]


def test_title_icon_sits_before_the_title_label(app_context):
    panel = _IconPanel(app_context)

    assert isinstance(panel.title_icon, IconLabel)
    assert panel.title_icon.icon_name == "chart-bar"
    assert _row_widgets(panel) == [panel.title_icon, panel.title_label, panel.help_button]


def test_title_text_has_no_icon_and_help_name_uses_the_full_title(app_context):
    panel = _IconPanel(app_context)

    assert panel.title_label.text() == "Analysis Operations"
    assert panel.help_button.accessibleName() == "Help: Analysis Operations"
    assert panel.help_button.accessibleDescription() == "Opens the Help window on the Analysis Operations topic"


def test_panel_without_icon_name_has_no_title_icon(app_context):
    panel = _NoIconPanel(app_context)

    assert panel.title_icon is None
    assert _row_widgets(panel) == [panel.title_label, panel.help_button]


def test_theme_change_retints_the_title_icon(app_context):
    panel = _IconPanel(app_context)
    dark = design_tokens(Theme.DARK)
    app_context.get_manager.return_value.get_design_tokens.return_value = dark

    panel._on_theme_changed({})

    wanted = QColor(dark["text_primary"])
    actual = _strongest(panel.title_icon)
    assert abs(actual.red() - wanted.red()) < 12
    assert abs(actual.green() - wanted.green()) < 12
    assert abs(actual.blue() - wanted.blue()) < 12


def test_title_without_help_topic_still_shows_the_icon(app_context):
    panel = _IconPanel(app_context, help_topic=None)

    assert panel.help_button is None
    assert isinstance(panel.title_icon, IconLabel)
    assert _row_widgets(panel) == [panel.title_icon, panel.title_label]
    assert panel.main_layout.itemAt(0).widget() is panel._title_row


@pytest.mark.parametrize("help_topic", [None, "panel.analysis"])
def test_title_band_covers_the_icon_row(app_context, help_topic):
    panel = _IconPanel(app_context, help_topic=help_topic)

    panel._apply_title_theme("#111111", "#dddddd")

    assert "#dddddd" in panel._title_row.styleSheet()
    assert "transparent" in panel.title_label.styleSheet()
