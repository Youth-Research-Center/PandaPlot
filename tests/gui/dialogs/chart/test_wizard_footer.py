"""Tests for WizardFooter."""
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter


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
