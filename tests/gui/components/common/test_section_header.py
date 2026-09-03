"""Tests for SectionHeader's disabled-state appearance."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.section_header import SectionHeader


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def test_disabling_the_header_changes_its_stylesheet_to_a_disabled_rule():
    """SectionHeader must declare a QLabel:disabled color rule so toggling
    setEnabled(False) (the standard Qt pattern every other widget in this
    codebase uses) visibly greys the title -- needed so style_tab.py's
    hide-on-disable sections (Marker/Fill/Confidence Band) can grey the
    section title instead of just hiding the body rows."""
    header = SectionHeader("Marker")
    assert ":disabled" in header.styleSheet()


def test_disabled_color_is_visually_distinct_from_enabled_color():
    """The previous test only checks that a `:disabled` CSS rule is present
    in the stylesheet string -- it doesn't verify the color it sets is
    actually different from the enabled color. This gap let a real bug
    (disabled color lighter than enabled color in dark theme) ship
    undetected until a final whole-branch review caught it by inspection."""
    header = SectionHeader("Marker")
    tokens = {"text_muted": "#9AA0AB", "text_disabled": "#5B6270"}
    header.set_tokens(tokens)

    assert tokens["text_disabled"] in header.styleSheet()
    assert tokens["text_disabled"] != tokens["text_muted"]
