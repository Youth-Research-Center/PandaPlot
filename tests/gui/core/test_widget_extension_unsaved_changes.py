"""Tests for WidgetExtension's opt-in unsaved-changes registration
(design doc 2026-09-05): a widget can register itself as a source
flush_pending_edits() must commit, and is automatically deregistered by the
same synchronous teardown (unsubscribe_all / unsubscribe_widget_tree) that
already detaches it from the event bus."""
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.core.widget_extension import PWidget, unsubscribe_widget_tree
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _FakeAppContext:
    def __init__(self):
        self.registry = UnsavedChangesRegistry()

    def get_manager(self, manager_type):
        assert manager_type is UnsavedChangesRegistry
        return self.registry


class _Source(PWidget):
    """A minimal PWidget implementing the UnsavedChangesSource protocol."""

    def _init_ui(self):
        pass

    def _apply_theme(self):
        pass


def _widget(app_context):
    widget = _Source(app_context=app_context)
    widget.has_unsaved_changes = Mock(return_value=True)
    widget.save = Mock(return_value=True)
    return widget


def test_register_unsaved_changes_source_is_included_in_the_next_flush():
    app_context = _FakeAppContext()
    widget = _widget(app_context)

    widget.register_unsaved_changes_source()

    assert app_context.registry.flush_all() is True
    widget.save.assert_called_once()


def test_unsubscribe_all_deregisters_the_widget():
    app_context = _FakeAppContext()
    widget = _widget(app_context)
    widget.register_unsaved_changes_source()

    widget.unsubscribe_all()
    app_context.registry.flush_all()

    widget.save.assert_not_called()


def test_unsubscribe_widget_tree_deregisters_it_too():
    """Same synchronous teardown path every tab close already goes through
    (see test_unsubscribe_widget_tree.py) must also remove this widget from
    the unsaved-changes registry, not just the event bus."""
    app_context = _FakeAppContext()
    widget = _widget(app_context)
    widget.register_unsaved_changes_source()

    unsubscribe_widget_tree(widget)
    app_context.registry.flush_all()

    widget.save.assert_not_called()


def test_unsubscribe_all_is_a_noop_when_never_registered():
    app_context = _FakeAppContext()
    widget = _widget(app_context)

    widget.unsubscribe_all()  # must not raise
