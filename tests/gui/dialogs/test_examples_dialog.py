"""Tests for ExamplesDialog's example cards."""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.examples_dialog import ExamplesDialog


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_example_card_exposes_its_title_and_description_to_assistive_tech():
    """The visible text lives in child QLabels, which leaves the card
    button itself unnamed unless it is set explicitly."""
    _qapp()
    dialog = ExamplesDialog(build_app_context())
    try:
        card = dialog._create_example_item(
            {"name": "Damped Oscillator", "description": "A fitted decay curve.", "path": "/examples/demo.ppp"})

        assert card.accessibleName() == "Damped Oscillator"
        assert card.accessibleDescription() == "A fitted decay curve."
    finally:
        dialog.deleteLater()
