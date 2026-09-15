"""Tests for the shared unsaved-changes guard (#318, generalized per the
2026-09-05 design doc: flush_pending_edits itself no longer knows about tabs
or TabContainer -- see tests/models/state/test_unsaved_changes_registry.py
for the aggregate-failure contract this delegates to)."""
from unittest.mock import Mock

from pandaplot.commands.project.project.unsaved_changes import (
    confirm_discard_unsaved_changes,
    flush_pending_edits,
)
from pandaplot.models.state import AppContext, AppState
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry


def test_flush_pending_edits_delegates_to_the_registry():
    app_context = Mock(spec=AppContext)
    registry = Mock(spec=UnsavedChangesRegistry)
    registry.flush_all.return_value = True
    app_context.get_manager.return_value = registry

    assert flush_pending_edits(app_context) is True
    registry.flush_all.assert_called_once()


def test_flush_pending_edits_propagates_a_failed_flush():
    app_context = Mock(spec=AppContext)
    registry = Mock(spec=UnsavedChangesRegistry)
    registry.flush_all.return_value = False
    app_context.get_manager.return_value = registry

    assert flush_pending_edits(app_context) is False


def _make_app_context(*, has_project=True, is_modified=False):
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = has_project
    app_state.is_modified = is_modified
    app_state.is_saving = False
    app_state.current_project.name = "P"
    app_state.project_file_path = None
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


def test_confirm_discard_flushes_pending_note_edits_before_checking_is_modified(monkeypatch):
    """Regression (#318): a note's debounced edit must land (flipping
    is_modified to True) before this function decides whether there is
    anything to confirm -- otherwise a fast close/exit racing the note's
    2s auto-save timer silently proceeds with no prompt at all."""
    app_context, app_state = _make_app_context(is_modified=False)
    calls = []

    def fake_flush(ctx):
        calls.append(ctx)
        app_state.is_modified = True  # simulates the debounced EditNoteCommand landing
        return True

    monkeypatch.setattr(
        "pandaplot.commands.project.project.unsaved_changes.flush_pending_edits",
        fake_flush,
    )
    app_context.get_ui_controller.return_value.show_question.return_value = True

    result = confirm_discard_unsaved_changes(app_context)

    assert calls == [app_context]
    assert result is True
    app_context.get_ui_controller.return_value.show_question.assert_called_once()


def test_confirm_discard_still_returns_true_without_asking_when_flush_finds_nothing(monkeypatch):
    """A flush that changes nothing must not turn an already-clean project
    into a spurious confirmation prompt."""
    app_context, _app_state = _make_app_context(is_modified=False)
    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.unsaved_changes.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )

    result = confirm_discard_unsaved_changes(app_context)

    assert calls == [app_context]
    assert result is True
    app_context.get_ui_controller.return_value.show_question.assert_not_called()


def test_confirm_discard_cancels_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): a failed flush is otherwise
    indistinguishable from a successful one -- swallowing it here would read
    an unchanged (stale) is_modified and proceed to discard a note edit that
    never actually got committed. Must refuse to proceed and say why,
    instead of silently continuing as if there were nothing to lose."""
    app_context, _app_state = _make_app_context(is_modified=False)
    monkeypatch.setattr(
        "pandaplot.commands.project.project.unsaved_changes.flush_pending_edits",
        lambda ctx: False,
    )

    result = confirm_discard_unsaved_changes(app_context)

    assert result is False
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.get_ui_controller.return_value.show_question.assert_not_called()
