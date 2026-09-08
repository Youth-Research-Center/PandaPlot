"""Tests for UnsavedChangesRegistry: register/unregister/flush_all's
aggregate success/failure contract (design doc 2026-09-05)."""
from unittest.mock import Mock

from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry


def _source(*, unsaved: bool, save_result: bool = True) -> Mock:
    source = Mock()
    source.has_unsaved_changes.return_value = unsaved
    source.save.return_value = save_result
    return source


def test_flush_all_succeeds_on_an_empty_registry():
    assert UnsavedChangesRegistry().flush_all() is True


def test_flush_all_saves_only_dirty_sources():
    registry = UnsavedChangesRegistry()
    dirty = _source(unsaved=True)
    clean = _source(unsaved=False)
    registry.register(dirty)
    registry.register(clean)

    assert registry.flush_all() is True

    dirty.save.assert_called_once()
    clean.save.assert_not_called()


def test_unregister_removes_a_source_from_the_next_flush():
    registry = UnsavedChangesRegistry()
    source = _source(unsaved=True)
    registry.register(source)
    registry.unregister(source)

    registry.flush_all()

    source.save.assert_not_called()


def test_flush_all_reports_failure_when_a_dirty_sources_save_returns_false():
    registry = UnsavedChangesRegistry()
    registry.register(_source(unsaved=True, save_result=False))

    assert registry.flush_all() is False


def test_flush_all_reports_failure_when_a_dirty_sources_save_raises():
    """Other registered sources must still be attempted even if one raises."""
    registry = UnsavedChangesRegistry()
    failing = _source(unsaved=True)
    failing.save.side_effect = RuntimeError("boom")
    other = _source(unsaved=True)
    registry.register(failing)
    registry.register(other)

    assert registry.flush_all() is False

    other.save.assert_called_once()


def test_unregistering_a_source_that_was_never_registered_does_not_raise():
    registry = UnsavedChangesRegistry()
    registry.unregister(Mock())  # must not raise
