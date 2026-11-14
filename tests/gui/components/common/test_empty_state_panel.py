"""EmptyStatePanel shows a heading, description and up to two actions."""

from unittest.mock import Mock

import pytest

from pandaplot.gui.components.common.empty_state_panel import EmptyStatePanel
from pandaplot.models.state.app_context import AppContext
from tests.gui.theme_testing import design_tokens


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens()
    return ctx


def test_button_clicks_call_their_callbacks(qtbot, app_context):
    first, second = Mock(), Mock()
    panel = EmptyStatePanel(app_context, heading="H", description="D", actions=[("One", first), ("Two", second)])
    qtbot.addWidget(panel)

    panel.action_buttons[0].click()
    first.assert_called_once_with()
    second.assert_not_called()
    panel.action_buttons[1].click()
    second.assert_called_once_with()
    assert first.call_count == 1


def test_no_actions_creates_no_buttons(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D")
    qtbot.addWidget(panel)

    assert panel.action_buttons == []
    assert panel.icon_label is None


def test_one_action_is_primary(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D", actions=[("One", Mock())])
    qtbot.addWidget(panel)

    assert [b.text() for b in panel.action_buttons] == ["One"]
    assert panel.action_buttons[0].property("primary") is True


def test_two_actions_are_primary_then_secondary(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D", actions=[("One", Mock()), ("Two", Mock())])
    qtbot.addWidget(panel)

    assert [b.text() for b in panel.action_buttons] == ["One", "Two"]
    assert panel.action_buttons[0].property("primary") is True
    assert panel.action_buttons[1].property("secondary") is True
    assert panel.action_buttons[1].property("primary") is False


def test_more_than_two_actions_are_rejected(qtbot, app_context):
    with pytest.raises(ValueError, match="at most 2"):
        EmptyStatePanel(app_context, heading="H", description="D", actions=[("A", Mock()), ("B", Mock()), ("C", Mock())])


def test_initial_text_and_accessibility(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="No data", description="Import some data.")
    qtbot.addWidget(panel)

    assert panel.heading_label.text() == "No data"
    assert panel.description_label.text() == "Import some data."
    assert panel.accessibleName() == "No data"
    assert panel.accessibleDescription() == "Import some data."
    assert panel.description_label.wordWrap()


def test_setters_update_text_and_accessibility(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D")
    qtbot.addWidget(panel)

    panel.set_heading("New heading")
    panel.set_description("New description")

    assert panel.heading_label.text() == "New heading"
    assert panel.description_label.text() == "New description"
    assert panel.accessibleName() == "New heading"
    assert panel.accessibleDescription() == "New description"


def test_icon_is_shown_and_retinted_by_set_tokens(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D", icon_name="chart-line")
    qtbot.addWidget(panel)

    assert panel.icon_label is not None
    assert panel.icon_label.icon_name == "chart-line"
    assert not panel.icon_label.pixmap().isNull()
    panel.icon_label.retint = Mock()
    panel.set_tokens(design_tokens())
    panel.icon_label.retint.assert_called_once_with()


def test_set_tokens_applies_colours(qtbot, app_context):
    panel = EmptyStatePanel(app_context, heading="H", description="D")
    qtbot.addWidget(panel)

    # Distinct sentinels tell the heading colour (text_primary) from the description colour (text_muted).
    panel.set_tokens(design_tokens(text_primary="#111111", text_muted="#222222"))

    assert "#111111" in panel.heading_label.styleSheet()
    assert "font-weight: 600" in panel.heading_label.styleSheet()
    assert "#222222" in panel.description_label.styleSheet()
