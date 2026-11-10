"""StatusMessage shows a kind-coloured icon next to plain, wrapped text and hides while empty."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.status_message import StatusKind, StatusMessage
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, fresh_icon_tokens, strongest_pixel

KIND_TOKENS = {
    StatusKind.SUCCESS: "status_success",
    StatusKind.ERROR: "status_danger",
    StatusKind.WARNING: "status_modified_text",
    StatusKind.INFO: "accent",
}


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = fresh_icon_tokens()
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

    assert _text(widget).palette().windowText().color().name().lower() == ICON_TOKENS["text_primary"].lower()
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

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), ICON_TOKENS[KIND_TOKENS[kind]])


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

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), ICON_TOKENS["status_success"])


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
    app_context.get_manager.return_value.get_design_tokens.return_value = {**ICON_TOKENS, "status_danger": "#00AA00"}

    widget.retint()

    assert_tinted(strongest_pixel(_icon(widget).pixmap()), "#00AA00")


def test_retint_recolours_the_text_with_the_primary_text_token(qapp, app_context):
    widget = StatusMessage(app_context)
    widget.set_message(StatusKind.INFO, "Hello")
    app_context.get_manager.return_value.get_design_tokens.return_value = {**ICON_TOKENS, "text_primary": "#00AA00"}

    widget.retint()

    assert _text(widget).palette().color(QPalette.ColorRole.WindowText).name().lower() == "#00aa00"
    assert not _text(widget).styleSheet()


def test_retint_on_an_empty_widget_is_a_no_op(qapp, app_context):
    StatusMessage(app_context).retint()


@pytest.mark.parametrize(
    ("kind", "word"),
    [(StatusKind.SUCCESS, "Success"), (StatusKind.ERROR, "Error"), (StatusKind.WARNING, "Warning"), (StatusKind.INFO, "Information")],
)
def test_accessible_description_names_the_kind(qapp, app_context, kind, word):
    widget = StatusMessage(app_context)

    widget.set_message(kind, "Boom")

    assert widget.accessibleDescription() == f"{word}: Boom"
