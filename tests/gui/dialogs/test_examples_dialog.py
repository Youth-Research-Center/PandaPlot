"""Tests for ExamplesDialog's example cards."""
import sys

from PySide6.QtWidgets import QApplication, QLabel

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.examples_dialog import ExamplesDialog
from pandaplot.models.project.example_info import ExampleLevel, ExampleSection
from pandaplot.utils.examples import ExampleProject


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_example_card_exposes_its_title_and_description_to_assistive_tech():
    """The visible text lives in child QLabels, which leaves the card
    button itself unnamed unless it is set explicitly."""
    _qapp()
    dialog = ExamplesDialog(build_app_context())
    try:
        card = dialog._create_example_item(
            ExampleProject(
                path="/examples/demo.ppp", name="Damped Oscillator", summary="A fitted decay curve.", description="A fitted decay curve.",
                section=ExampleSection.GETTING_STARTED, level=ExampleLevel.BEGINNER, tags=(), featured_chart_ids=(), start_note_id=None,
                data_credit="", cover_image=None, dataset_count=0, chart_count=0, note_count=0))

        assert card.accessibleName() == "Damped Oscillator"
        assert card.accessibleDescription() == "A fitted decay curve."
    finally:
        dialog.deleteLater()


def test_example_card_shows_summary_not_description():
    _qapp()
    dialog = ExamplesDialog(build_app_context())
    try:
        card = dialog._create_example_item(
            ExampleProject(
                path="/examples/demo.ppp", name="Demo", summary="Short summary.", description="Long description. With more.",
                section=ExampleSection.GETTING_STARTED, level=ExampleLevel.BEGINNER, tags=(), featured_chart_ids=(), start_note_id=None,
                data_credit="", cover_image=None, dataset_count=0, chart_count=0, note_count=0))

        texts = [label.text() for label in card.findChildren(QLabel)]
        assert "Short summary." in texts
        assert "Long description. With more." not in texts
    finally:
        dialog.deleteLater()
