"""Offering the untitled-project recovery copy on launch (#629)."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytestqt.qtbot import QtBot

from pandaplot.app import build_app_context, offer_recovered_untitled_project, restore_last_session
from pandaplot.models.project.project import Project
from pandaplot.services.autosave.recovery import recovery_file_path
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.session import SessionPersistenceManager


@pytest.fixture
def context():
    ctx = build_app_context()
    ctx.ui_controller.show_choice = Mock()
    ctx.ui_controller.show_info_message = Mock()
    return ctx


def _write_recovery(context, name: str = "Recovered") -> None:
    path = recovery_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    context.get_manager(ProjectManager).save_project(Project(name=name), str(path))


def test_no_recovery_file_asks_nothing(context) -> None:
    offer_recovered_untitled_project(context)

    context.ui_controller.show_choice.assert_not_called()


def test_restore_loads_the_copy_untitled_and_modified(context, qtbot: QtBot) -> None:
    _write_recovery(context)
    context.ui_controller.show_choice.return_value = True

    offer_recovered_untitled_project(context)

    qtbot.waitUntil(lambda: context.app_state.has_project and context.app_state.is_modified, timeout=10000)
    assert context.app_state.current_project.name == "Recovered"
    assert context.app_state.project_file_path is None
    assert context.get_manager(SessionPersistenceManager).last_project_path is None
    _title, message, accept, reject = context.ui_controller.show_choice.call_args.args
    assert "untitled project" in message
    assert (accept, reject) == ("Restore", "Discard")
    assert recovery_file_path().exists()  # kept until the user saves or discards the restored project


def test_discard_deletes_the_copy_and_opens_nothing(context) -> None:
    _write_recovery(context)
    context.ui_controller.show_choice.return_value = False

    offer_recovered_untitled_project(context)

    assert not recovery_file_path().exists()
    assert not context.app_state.has_project


def test_launch_without_a_remembered_project_offers_the_copy_straight_away(context) -> None:
    _write_recovery(context)
    context.ui_controller.show_choice.return_value = False

    restore_last_session(context, Mock())

    context.ui_controller.show_choice.assert_called_once()


def test_remembered_titled_project_is_restored_first_then_the_copy_is_offered(context, qtbot: QtBot, tmp_path: Path) -> None:
    titled = tmp_path / "titled.pplot"
    context.get_manager(ProjectManager).save_project(Project(name="Titled"), str(titled))
    context.get_manager(SessionPersistenceManager).update_project(str(titled))
    _write_recovery(context)
    context.ui_controller.show_choice.return_value = False
    window = Mock()

    restore_last_session(context, window)

    qtbot.waitUntil(lambda: context.ui_controller.show_choice.called, timeout=10000)
    assert context.app_state.current_project.name == "Titled"
    assert context.app_state.project_file_path == str(titled)
    window.tab_container.restore_tab_session.assert_called_once()
    assert not recovery_file_path().exists()
