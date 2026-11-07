"""Tests for the help-request UI event."""

from pandaplot.models.events.event_types import EventHierarchy, UIEvents


def test_help_requested_event_value():
    assert UIEvents.HELP_REQUESTED == "ui.help_requested"


def test_help_requested_hierarchy_is_itself():
    assert EventHierarchy.get_hierarchy(UIEvents.HELP_REQUESTED) == [UIEvents.HELP_REQUESTED]
