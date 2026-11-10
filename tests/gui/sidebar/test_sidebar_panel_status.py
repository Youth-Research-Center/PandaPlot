"""SidebarPanel's shared status helpers: `_status_output`, `_show_status` and `_show_error`."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

from pandaplot.gui.components.common.status_message import StatusKind, StatusMessage
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import fresh_icon_tokens


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **fresh_icon_tokens()}
    return ctx


class _TextPanel(SidebarPanel):
    """A panel whose text area is a QTextEdit called `preview_text`."""

    def __init__(self, app_context):
        super().__init__(app_context)
        self.preview_text = QTextEdit()
        self.status_message = StatusMessage(app_context, parent=self)

    def _status_output(self) -> QTextEdit:
        return self.preview_text

    def _apply_theme(self):
        pass


class _PlainTextPanel(SidebarPanel):
    """A panel whose text area is a QPlainTextEdit called `results_text`."""

    def __init__(self, app_context):
        super().__init__(app_context)
        self.results_text = QPlainTextEdit()
        self.status_message = StatusMessage(app_context, parent=self)

    def _status_output(self) -> QPlainTextEdit:
        return self.results_text

    def _apply_theme(self):
        pass


class _HooklessPanel(SidebarPanel):
    def __init__(self, app_context):
        super().__init__(app_context)
        self.status_message = StatusMessage(app_context, parent=self)

    def _apply_theme(self):
        pass


def test_show_status_clears_the_text_area_and_shows_the_message(qapp, app_context):
    panel = _TextPanel(app_context)
    panel.preview_text.setPlainText("stale preview")

    panel._show_status(StatusKind.WARNING, "Careful")

    assert panel.preview_text.toPlainText() == ""
    assert panel.status_message.kind() is StatusKind.WARNING
    assert panel.status_message.message() == "Careful"


def test_show_status_works_with_a_plain_text_edit(qapp, app_context):
    panel = _PlainTextPanel(app_context)
    panel.results_text.setPlainText("old report")

    panel._show_status(StatusKind.INFO, "Nothing to report")

    assert panel.results_text.toPlainText() == ""
    assert panel.status_message.kind() is StatusKind.INFO
    assert panel.status_message.message() == "Nothing to report"


def test_show_error_shows_an_error(qapp, app_context):
    panel = _PlainTextPanel(app_context)
    panel.results_text.setPlainText("old report")

    panel._show_error("Boom")

    assert panel.results_text.toPlainText() == ""
    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Boom"


def test_a_panel_without_a_status_output_raises_a_clear_error(qapp, app_context):
    panel = _HooklessPanel(app_context)

    with pytest.raises(NotImplementedError, match="_HooklessPanel"):
        panel._show_status(StatusKind.ERROR, "Boom")

    with pytest.raises(NotImplementedError, match="_status_output"):
        panel._show_error("Boom")
