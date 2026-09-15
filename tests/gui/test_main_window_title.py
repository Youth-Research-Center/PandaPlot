"""Tests for PandaMainWindow._update_window_title (#209) and closeEvent
(PR #235 review: the OS window-close button/Cmd+Q previously bypassed every
unsaved-changes check).

Exercises these methods directly against a lightweight stand-in (rather
than constructing a full PandaMainWindow, which builds the entire app UI)
since they only touch self.app_context, self._is_closing, and
self.setWindowTitle/the passed-in close event.
"""
from unittest.mock import Mock

from pandaplot.gui.main_window import PandaMainWindow


class _FakeMainWindow:
    """Stand-in exposing just what _update_window_title/closeEvent read/write."""

    def __init__(self, app_context):
        self.app_context = app_context
        self.title = None
        self._is_closing = False

    def setWindowTitle(self, title):  # noqa: N802 - matches Qt's method name
        self.title = title


class _FakeCloseEvent:
    """Stand-in for QCloseEvent -- records whether accept()/ignore() won."""

    def __init__(self):
        self.accepted = None

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def _make_window(*, has_project, project_name="P", is_modified=False, project_file_path="/p.pplot"):
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = has_project
    app_context.get_app_state.return_value.current_project.name = project_name
    app_context.get_app_state.return_value.is_modified = is_modified
    app_context.get_app_state.return_value.project_file_path = project_file_path
    app_context.get_app_state.return_value.is_saving = False  # no in-flight save to wait for, by default
    return _FakeMainWindow(app_context)


def test_no_project_shows_plain_app_name():
    window = _make_window(has_project=False)
    PandaMainWindow._update_window_title(window)
    assert window.title == "PandaPlot"


def test_unmodified_project_shows_name_without_marker():
    window = _make_window(has_project=True, project_name="My Project", is_modified=False)
    PandaMainWindow._update_window_title(window)
    assert window.title == "My Project - PandaPlot"


def test_modified_project_shows_unsaved_marker():
    window = _make_window(has_project=True, project_name="My Project", is_modified=True)
    PandaMainWindow._update_window_title(window)
    assert window.title == "My Project* - PandaPlot"


def test_close_event_accepts_when_no_unsaved_changes():
    window = _make_window(has_project=False)
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    window.app_context.get_ui_controller.return_value.show_question.assert_not_called()
    assert event.accepted is True


def test_close_event_asks_and_accepts_when_confirmed():
    window = _make_window(has_project=True, is_modified=True)
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    window.app_context.get_ui_controller.return_value.show_question.assert_called_once()
    assert event.accepted is True


def test_close_event_ignores_the_close_when_declined():
    """Regression (PR #235 review): previously there was no closeEvent
    override at all, so Qt's default always accepted -- the OS window-close
    button/Cmd+Q could silently discard unsaved changes."""
    window = _make_window(has_project=True, is_modified=True)
    window.app_context.get_ui_controller.return_value.show_question.return_value = False
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    assert event.accepted is False


def test_close_event_prompt_says_autosave_not_discard_for_an_already_saved_project():
    """Regression (PR #235 review): app.launch()'s aboutToQuit handler
    unconditionally flushes a save for an existing saved project before the
    process exits, so this prompt must not claim continuing will discard
    those edits."""
    window = _make_window(has_project=True, is_modified=True, project_file_path="/p.pplot")
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    _, message = window.app_context.get_ui_controller.return_value.show_question.call_args[0]
    assert "saved automatically" in message
    assert "discard" not in message


def test_close_event_prompt_says_discard_for_a_never_saved_project():
    """A project with no file path yet has nothing for
    _flush_save_on_quit to write to, so closing really does discard it."""
    window = _make_window(has_project=True, is_modified=True, project_file_path=None)
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    _, message = window.app_context.get_ui_controller.return_value.show_question.call_args[0]
    assert "discard" in message


def test_close_event_confirming_an_autosave_actually_saves_before_closing():
    """Regression (PR #235 review): the prompt promises an automatic save,
    but the actual save previously only happened later, in
    app._flush_save_on_quit -- after the point of no return, with every
    exception swallowed into a log line. Make sure the save genuinely runs
    (and clears is_modified) as part of confirming, not just the promise of
    one."""
    window = _make_window(has_project=True, is_modified=True, project_file_path="/p.pplot")
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    project_manager = Mock()
    window.app_context.get_manager.return_value = project_manager
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    project = window.app_context.get_app_state.return_value.current_project
    project_manager.save_project.assert_called_once_with(project, "/p.pplot")
    window.app_context.get_app_state.return_value.mark_saved.assert_called_once()
    assert event.accepted is True


def test_close_event_a_failed_autosave_cancels_the_close_instead_of_losing_edits():
    """Regression (PR #235 review): _flush_save_on_quit catches every save
    exception and lets shutdown continue anyway, so a disk-full/permission/
    serialization failure would silently close the app having lost the
    edits it just promised to keep. The save must instead be checked here,
    before the close is accepted."""
    window = _make_window(has_project=True, is_modified=True, project_file_path="/p.pplot")
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    project_manager = Mock()
    project_manager.save_project.side_effect = OSError("disk full")
    window.app_context.get_manager.return_value = project_manager
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    window.app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    window.app_context.get_app_state.return_value.mark_saved.assert_not_called()
    assert event.accepted is False


def test_close_event_refuses_to_close_while_another_save_is_already_writing_the_file():
    """Regression (PR #235 review): writing here while a SaveProjectCommand
    (manual or auto-save) is already mid-write would be a second,
    uncoordinated writer of the same file -- ProjectDataManager.save() opens
    it in write mode, so two overlapping writers can corrupt it. Refuse to
    proceed instead (the user can just try closing again once the in-flight
    save finishes)."""
    window = _make_window(has_project=True, is_modified=True, project_file_path="/p.pplot")
    window.app_context.get_ui_controller.return_value.show_question.return_value = True
    window.app_context.get_app_state.return_value.is_saving = True
    project_manager = Mock()
    window.app_context.get_manager.return_value = project_manager
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    project_manager.save_project.assert_not_called()
    window.app_context.get_app_state.return_value.mark_saved.assert_not_called()
    assert event.accepted is False


def test_close_event_skips_the_check_when_already_closing_via_exit_command():
    """Avoids asking twice: File > Exit's ExitCommand already confirmed
    before emitting APP_CLOSING, which on_app_closing_event handles by
    setting _is_closing before calling self.close() -- the very thing that
    triggers this method."""
    window = _make_window(has_project=True, is_modified=True)
    window._is_closing = True
    event = _FakeCloseEvent()

    PandaMainWindow.closeEvent(window, event)

    window.app_context.get_ui_controller.return_value.show_question.assert_not_called()
    assert event.accepted is True
