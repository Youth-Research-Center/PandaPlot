"""Tests for NoteFinder."""
import logging
from unittest.mock import Mock

from pandaplot.commands.project.note.note_finder import NoteFinder
from pandaplot.models.project.items import Note


def test_find_returns_the_note_when_it_exists():
    note = Note(name="Test Note")
    project = Mock()
    project.find_item.return_value = note

    assert NoteFinder.find(project, note.id) is note


def test_find_returns_none_when_item_not_found():
    project = Mock()
    project.find_item.return_value = None

    assert NoteFinder.find(project, "missing") is None


def test_find_returns_none_and_logs_a_warning_when_item_is_not_a_note(caplog):
    wrong_item = Mock()
    project = Mock()
    project.find_item.return_value = wrong_item

    with caplog.at_level(logging.WARNING):
        result = NoteFinder.find(project, "some-id")

    assert result is None
    assert "some-id" in caplog.text
