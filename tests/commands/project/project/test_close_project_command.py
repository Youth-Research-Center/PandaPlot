"""Tests for CloseProjectCommand."""

from unittest.mock import Mock

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.close_project_command import CloseProjectCommand
from pandaplot.models.state import AppContext, AppState


def _make_app_context(*, has_project=True, is_modified=False, project_file_path=None):
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = has_project
    app_state.is_modified = is_modified
    app_state.is_saving = False
    app_state.current_project.name = "P"
    app_state.project_file_path = project_file_path
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


def test_execute_closes_the_project():
    app_context, app_state = _make_app_context()
    command = CloseProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    app_state.close_project.assert_called_once()


def test_execute_surfaces_unexpected_failure_to_the_user():
    app_context, app_state = _make_app_context()
    app_state.close_project.side_effect = RuntimeError("disk error")

    command = CloseProjectCommand(app_context)
    assert command.execute() is CommandResult.FAILURE
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
    assert "disk error" in message


def test_execute_closes_without_asking_when_unmodified():
    """No unsaved changes to lose -- must not interrupt with a confirmation."""
    app_context, app_state = _make_app_context(is_modified=False)
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    app_context.get_ui_controller.return_value.show_question.assert_not_called()
    app_state.close_project.assert_called_once()


def test_execute_asks_for_confirmation_when_modified():
    app_context, app_state = _make_app_context(is_modified=True)
    app_context.get_ui_controller.return_value.show_question.return_value = True
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    app_context.get_ui_controller.return_value.show_question.assert_called_once()
    app_state.close_project.assert_called_once()


def test_execute_aborts_close_when_user_declines_confirmation():
    app_context, app_state = _make_app_context(is_modified=True)
    app_context.get_ui_controller.return_value.show_question.return_value = False
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.NOOP
    app_state.close_project.assert_not_called()


def test_execute_offers_save_discard_cancel_when_project_has_a_file_path():
    """Regression (#409): closing a project (unlike exiting) has no
    save-on-quit safety net, so a saved project's close prompt must offer an
    explicit save option instead of only discard/cancel."""
    app_context, app_state = _make_app_context(is_modified=True, project_file_path="/tmp/p.pplot")
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_save_discard_cancel.return_value = "discard"
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    ui_controller.show_save_discard_cancel.assert_called_once()
    ui_controller.show_question.assert_not_called()
    app_state.close_project.assert_called_once()


def test_execute_saves_then_closes_when_user_chooses_save():
    app_context, app_state = _make_app_context(is_modified=True, project_file_path="/tmp/p.pplot")
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_save_discard_cancel.return_value = "save"
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.SUCCESS
    app_context.get_manager.return_value.save_project.assert_called_once_with(
        app_state.current_project, "/tmp/p.pplot"
    )
    app_state.mark_saved.assert_called_once()
    app_state.close_project.assert_called_once()


def test_execute_aborts_close_when_user_cancels_save_discard_dialog():
    app_context, app_state = _make_app_context(is_modified=True, project_file_path="/tmp/p.pplot")
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_save_discard_cancel.return_value = "cancel"
    command = CloseProjectCommand(app_context)

    assert command.execute() is CommandResult.NOOP
    app_state.close_project.assert_not_called()


def test_marks_project_modified_is_false():
    """CloseProjectCommand manages AppState's dirty flag itself (via
    close_project) and must not be double-counted by CommandExecutor's
    generic on_project_modified hook."""
    app_context, _app_state = _make_app_context()
    command = CloseProjectCommand(app_context)
    assert command.marks_project_modified() is False


def test_cleanup_does_not_raise():
    app_context, _app_state = _make_app_context()
    command = CloseProjectCommand(app_context)
    command.cleanup()


def test_does_not_occupy_undo_slot():
    app_context, _app_state = _make_app_context()
    command = CloseProjectCommand(app_context)
    assert command.occupies_undo_slot() is False
