"""StatusMessage shows a kind-coloured icon next to plain, wrapped text and hides while empty."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QAccessibleEvent, QPalette
from PySide6.QtWidgets import QLabel

from pandaplot.gui.components.common import status_message
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.status_message import StatusKind, StatusMessage
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens

KIND_TOKENS = {
    StatusKind.SUCCESS: "status_success",
    StatusKind.ERROR: "status_danger",
    StatusKind.WARNING: "status_modified_text",
    StatusKind.INFO: "accent",
}


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens()
    return ctx


def _icon(widget: StatusMessage) -> IconLabel:
    return widget.findChild(IconLabel)


def _text(widget: StatusMessage) -> QLabel:
    return next(label for label in widget.findChildren(QLabel) if not isinstance(label, IconLabel))


def test_starts_hidden_and_empty(qapp, app_context):
    widget = StatusMessage(app_context)

    assert widget.isHidden()
    assert widget.message() == ""
    assert widget.kind() is None


def test_set_message_shows_the_message_and_kind(qapp, app_context):
    widget = StatusMessage(app_context)

    widget.set_message(StatusKind.ERROR, "Boom")

    assert not widget.isHidden()
    assert widget.message() == "Boom"
    assert widget.kind() is StatusKind.ERROR
    assert _text(widget).text() == "Boom"


def test_text_is_plain_and_word_wrapped(qapp, app_context):
    widget = StatusMessage(app_context)

    widget.set_message(StatusKind.INFO, "<b>x</b>")

    label = _text(widget)
    assert label.textFormat() == Qt.TextFormat.PlainText
    assert label.wordWrap()
    assert label.text() == "<b>x</b>"


def test_text_uses_the_primary_text_colour_via_the_palette(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.INFO, "Hello")

    assert _text(widget).palette().windowText().color().name().lower() == design_tokens()["text_primary"].lower()
    assert not _text(widget).styleSheet()


def test_icon_is_top_aligned_and_decorative(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.INFO, "Hello")

    icon = _icon(widget)
    assert not icon.accessibleName()
    assert widget.layout().itemAt(0).widget() is icon
    assert widget.layout().itemAt(0).alignment() & Qt.AlignmentFlag.AlignTop


@pytest.mark.parametrize("kind", list(StatusKind))
def test_icon_is_tinted_with_the_kind_token(qapp, app_context, kind):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Message")

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), design_tokens()[KIND_TOKENS[kind]])


@pytest.mark.parametrize(
    ("kind", "icon_name"),
    [(StatusKind.SUCCESS, "check-circle"), (StatusKind.ERROR, "x-circle"), (StatusKind.WARNING, "warning"), (StatusKind.INFO, "info")],
)
def test_each_kind_shows_its_own_icon(qapp, app_context, kind, icon_name):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Message")

    assert kind.icon_name == icon_name
    assert _icon(widget).icon_name == icon_name


def test_icon_changes_when_the_kind_changes(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Bad")

    widget.set_message(StatusKind.SUCCESS, "Good")

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), design_tokens()["status_success"])


def test_clear_hides_and_empties(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")

    widget.clear()

    assert widget.isHidden()
    assert widget.message() == ""
    assert widget.kind() is None
    assert widget.accessibleDescription() == ""


def test_setting_an_empty_message_hides_the_widget(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")

    widget.set_message(StatusKind.ERROR, "")

    assert widget.isHidden()


def test_retint_follows_changed_tokens(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")
    app_context.get_manager.return_value.get_design_tokens.return_value = design_tokens(status_danger="#00AA00")

    widget.retint()

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), "#00AA00")


def test_retint_recolours_the_text_with_the_primary_text_token(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.INFO, "Hello")
    app_context.get_manager.return_value.get_design_tokens.return_value = design_tokens(text_primary="#00AA00")

    widget.retint()

    assert _text(widget).palette().color(QPalette.ColorRole.WindowText).name().lower() == "#00aa00"
    assert not _text(widget).styleSheet()


def test_retint_on_an_empty_widget_is_a_no_op(qapp, app_context):
    widget = StatusMessage(app_context)

    widget.retint()

    assert widget.isHidden()
    assert widget.message() == ""
    assert widget.kind() is None
    assert _icon(widget) is None
    assert _text(widget).text() == ""


@pytest.mark.parametrize(
    ("kind", "word"),
    [(StatusKind.SUCCESS, "Success"), (StatusKind.ERROR, "Error"), (StatusKind.WARNING, "Warning"), (StatusKind.INFO, "Information")],
)
def test_accessible_description_names_the_kind(qapp, app_context, kind, word):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Boom")

    assert widget.accessibleDescription() == f"{word}: Boom"


def _accessible_name(widget: StatusMessage) -> str:
    return QAccessible.queryAccessibleInterface(widget._text).text(QAccessible.Text.Name)


@pytest.mark.parametrize(
    ("kind", "word"),
    [(StatusKind.SUCCESS, "Success"), (StatusKind.ERROR, "Error"), (StatusKind.WARNING, "Warning"), (StatusKind.INFO, "Information")],
)
def test_text_label_accessible_name_is_kind_and_text(qapp, app_context, kind, word):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Boom")

    assert _accessible_name(widget) == f"{word}: Boom"


def test_text_label_accessible_name_follows_the_message_and_is_cleared(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")
    assert _accessible_name(widget) == "Error: Boom"

    widget.set_message(StatusKind.INFO, "Fine")
    assert _accessible_name(widget) == "Information: Fine"

    widget.clear()
    assert _accessible_name(widget) == ""


@pytest.fixture
def alerts(monkeypatch):
    """Record every accessibility event the widget sends."""
    sent: list[QAccessibleEvent] = []
    monkeypatch.setattr(status_message.QAccessible, "updateAccessibility", sent.append)
    return sent


@pytest.mark.parametrize("kind", [StatusKind.ERROR, StatusKind.WARNING])
def test_error_and_warning_send_an_alert_event_from_the_text_label(qapp, app_context, alerts, kind):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Boom")

    assert len(alerts) == 1
    assert alerts[0].type() == QAccessible.Event.Alert
    assert alerts[0].object() is widget._text


@pytest.mark.parametrize("kind", [StatusKind.SUCCESS, StatusKind.INFO])
def test_success_and_information_send_no_alert(qapp, app_context, alerts, kind):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Done")

    assert alerts == []


def test_clear_sends_no_alert(qapp, app_context, alerts):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")
    alerts.clear()

    widget.clear()

    assert alerts == []


def test_an_unchanged_message_sends_the_alert_once(qapp, app_context, alerts):
    widget = StatusMessage(app_context)

    widget.set_message(StatusKind.ERROR, "Boom")
    widget.set_message(StatusKind.ERROR, "Boom")

    assert len(alerts) == 1


def test_a_changed_text_or_kind_sends_a_new_alert(qapp, app_context, alerts):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")

    widget.set_message(StatusKind.ERROR, "Bang")
    widget.set_message(StatusKind.WARNING, "Bang")

    assert len(alerts) == 3


def test_the_same_message_after_a_clear_alerts_again(qapp, app_context, alerts):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.ERROR, "Boom")
    widget.clear()

    widget.set_message(StatusKind.ERROR, "Boom")

    assert len(alerts) == 2


def test_sending_alerts_does_not_raise_without_an_accessibility_client(qapp, app_context):
    widget = StatusMessage(app_context)

    widget.set_message(StatusKind.ERROR, "Boom")
    widget.set_message(StatusKind.WARNING, "Careful")

    assert widget.kind() is StatusKind.WARNING
    assert widget.message() == "Careful"
    assert widget.accessibleDescription() == "Warning: Careful"
    assert not widget.isHidden()
