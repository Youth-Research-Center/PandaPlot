"""Tests for WizardFooter."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_step_1_of_3_shows_next_not_finish():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)
    footer.show()

    assert footer.next_button.isVisible() is True
    assert footer.finish_button.isVisible() is False
    assert footer.back_button.isVisible() is False  # no Back on the first step


def test_last_step_shows_finish_not_next():
    footer = WizardFooter(step_number=3, total_steps=3, show_empty_link=False)
    footer.show()

    assert footer.next_button.isVisible() is False
    assert footer.finish_button.isVisible() is True
    assert footer.back_button.isVisible() is True


def test_empty_link_hidden_when_requested():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=False)

    assert footer.empty_link is None


def test_empty_link_emits_empty_requested():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)
    received = []
    footer.emptyRequested.connect(lambda: received.append(True))

    footer.empty_link.click()

    assert received == [True]


def test_button_clicks_emit_their_signals():
    footer = WizardFooter(step_number=2, total_steps=3, show_empty_link=False)
    events = []
    footer.backClicked.connect(lambda: events.append("back"))
    footer.nextClicked.connect(lambda: events.append("next"))
    footer.cancelClicked.connect(lambda: events.append("cancel"))

    footer.back_button.click()
    footer.next_button.click()
    footer.cancel_button.click()

    assert events == ["back", "next", "cancel"]


def test_next_disabled_when_page_incomplete():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)

    footer.set_next_enabled(enabled=False)

    assert footer.next_button.isEnabled() is False


def test_next_and_finish_both_hidden_when_show_next_is_false():
    footer = WizardFooter(step_number=2, total_steps=3, show_empty_link=False, show_next=False)
    footer.show()

    assert footer.next_button.isVisible() is False
    assert footer.finish_button.isVisible() is False
    assert footer.back_button.isVisible() is True  # unaffected


def test_show_next_defaults_to_true():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)
    footer.show()

    assert footer.next_button.isVisible() is True


def test_no_help_topic_means_no_help_button():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=True)

    assert footer.help_button is None


def test_help_button_is_accessible_and_emits_topic():
    footer = WizardFooter(step_number=2, total_steps=3, show_empty_link=True, help_topic="charts.x", help_label="Data")
    received = []
    footer.helpRequested.connect(received.append)

    button = footer.help_button
    assert button is not None
    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert button.accessibleName() == "Help: Data"
    assert button.accessibleDescription() == "Opens the Help window on this step's topic"
    assert button.toolTip() == "Open help for this step"
    layout = footer.layout()
    assert layout is not None
    assert layout.itemAt(0).widget() is button  # ty: ignore[unresolved-attribute]

    button.click()

    assert received == ["charts.x"]


def test_help_button_without_label_uses_generic_name():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=False, help_topic="charts.x")

    assert footer.help_button is not None
    assert footer.help_button.accessibleName() == "Help: this step"


def test_set_tokens_styles_help_button_with_text_primary():
    footer = WizardFooter(step_number=1, total_steps=3, show_empty_link=False, help_topic="charts.x")

    # A sentinel text_primary that no other token has, so the assertion proves which token styles the button.
    footer.set_tokens(design_tokens(text_primary="#123456"))

    assert footer.help_button is not None
    assert "#123456" in footer.help_button.styleSheet()
