"""Save As... choice of the unsaved-changes guard for untitled projects (#629)."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.project.unsaved_changes import confirm_discard_unsaved_changes
from pandaplot.models.events import ProjectEvents
from pandaplot.models.state import AppContext
from pandaplot.services.autosave.recovery import recovery_file_path
from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.session import SessionPersistenceManager


@pytest.fixture
def setup():
    project = SimpleNamespace(name="Untitled", project_file_path=None)
    app_state = Mock()
    app_state.has_project = True
    app_state.is_modified = True
    app_state.is_saving = False
    app_state.current_project = project
    app_state.project_file_path = None
    ui_controller = Mock()
    project_manager = Mock()
    config_manager = Mock()
    config_manager.config.recent_projects = ["/old/a.pplot"]
    session_manager = Mock()
    managers = {ProjectManager: project_manager, ConfigManager: config_manager, SessionPersistenceManager: session_manager}
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.get_manager.side_effect = lambda manager_type: managers.get(manager_type, Mock())
    app_context.event_bus = Mock()
    return SimpleNamespace(
        ctx=app_context, state=app_state, ui=ui_controller, project=project,
        pm=project_manager, config=config_manager, session=session_manager,
    )


def _make_recovery_file() -> Path:
    path = recovery_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"recovery")
    return path


def test_save_as_saves_sets_the_path_and_proceeds(setup, tmp_path):
    target = str(tmp_path / "mine.pplot")
    setup.ui.show_save_as_discard_cancel.return_value = "save_as"
    setup.ui.show_save_project_dialog.return_value = target
    recovery = _make_recovery_file()

    assert confirm_discard_unsaved_changes(setup.ctx, will_autosave=True) is True

    setup.ui.show_save_project_dialog.assert_called_once_with(default_name="Untitled.pplot")
    setup.pm.save_project.assert_called_once_with(setup.project, target)
    assert setup.project.project_file_path == target
    setup.state.mark_saved.assert_called_once()
    setup.config.update.assert_called_once_with({"recent_projects": [target, "/old/a.pplot"]}, save=True)
    setup.session.update_project.assert_called_once_with(target)
    assert not recovery.exists()
    event_name, payload = setup.ctx.event_bus.emit.call_args.args
    assert event_name == ProjectEvents.PROJECT_SAVED
    assert payload["file_path"] == target
    assert payload["previous_path"] is None


def test_save_as_adds_the_project_suffix_when_the_picker_returns_none(setup, tmp_path):
    setup.ui.show_save_as_discard_cancel.return_value = "save_as"
    setup.ui.show_save_project_dialog.return_value = str(tmp_path / "mine")

    assert confirm_discard_unsaved_changes(setup.ctx) is True

    assert setup.project.project_file_path == str(tmp_path / "mine.pplot")


def test_cancelled_save_dialog_cancels_the_close_and_keeps_the_project_untitled(setup):
    setup.ui.show_save_as_discard_cancel.return_value = "save_as"
    setup.ui.show_save_project_dialog.return_value = None
    recovery = _make_recovery_file()

    assert confirm_discard_unsaved_changes(setup.ctx) is False

    setup.pm.save_project.assert_not_called()
    assert setup.project.project_file_path is None
    setup.state.mark_saved.assert_not_called()
    assert recovery.exists()


def test_failed_save_reports_the_error_and_cancels(setup, tmp_path):
    error = OSError("disk full")
    setup.pm.save_project.side_effect = error
    setup.ui.show_save_as_discard_cancel.return_value = "save_as"
    setup.ui.show_save_project_dialog.return_value = str(tmp_path / "mine.pplot")
    recovery = _make_recovery_file()

    assert confirm_discard_unsaved_changes(setup.ctx) is False

    setup.ui.show_error_message.assert_called_once_with("Save Failed", "Couldn't save the project.", error=error)
    assert setup.project.project_file_path is None
    setup.state.mark_saved.assert_not_called()
    setup.session.update_project.assert_not_called()
    assert recovery.exists()


def test_save_as_refuses_while_another_save_is_in_flight(setup):
    setup.state.is_saving = True
    setup.ui.show_save_as_discard_cancel.return_value = "save_as"

    assert confirm_discard_unsaved_changes(setup.ctx) is False

    setup.ui.show_save_project_dialog.assert_not_called()
    setup.ui.show_info_message.assert_called_once()


def test_discard_proceeds_and_deletes_the_recovery_copy(setup):
    setup.ui.show_save_as_discard_cancel.return_value = "discard"
    recovery = _make_recovery_file()

    assert confirm_discard_unsaved_changes(setup.ctx) is True

    setup.ui.show_save_project_dialog.assert_not_called()
    assert not recovery.exists()


def test_cancel_refuses_and_keeps_the_recovery_copy(setup):
    setup.ui.show_save_as_discard_cancel.return_value = "cancel"
    recovery = _make_recovery_file()

    assert confirm_discard_unsaved_changes(setup.ctx) is False

    assert recovery.exists()


@pytest.mark.parametrize("flags", [{}, {"will_autosave": True}, {"offer_save": True}])
def test_every_guard_variant_offers_save_as_for_an_untitled_project(setup, flags):
    setup.ui.show_save_as_discard_cancel.return_value = "discard"

    assert confirm_discard_unsaved_changes(setup.ctx, **flags) is True

    setup.ui.show_save_as_discard_cancel.assert_called_once()
    setup.ui.show_question.assert_not_called()
    setup.ui.show_save_discard_cancel.assert_not_called()
    _, message = setup.ui.show_save_as_discard_cancel.call_args.args
    assert "autosave" not in message.lower()


def test_titled_project_never_sees_the_save_as_prompt(setup):
    setup.state.project_file_path = "/p/titled.pplot"
    setup.ui.show_question.return_value = True

    assert confirm_discard_unsaved_changes(setup.ctx) is True

    setup.ui.show_save_as_discard_cancel.assert_not_called()
    setup.ui.show_question.assert_called_once()


def test_unmodified_untitled_project_is_not_prompted(setup):
    setup.state.is_modified = False

    assert confirm_discard_unsaved_changes(setup.ctx) is True

    setup.ui.show_save_as_discard_cancel.assert_not_called()
