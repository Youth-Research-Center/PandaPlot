"""Offering an untitled project's recovery copy on launch, and cleaning it up on quit (#629)."""
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QLockFile
from pytestqt.qtbot import QtBot

from pandaplot.app import _flush_save_on_quit, build_app_context, offer_recovered_untitled_project, restore_last_session
from pandaplot.models.project.project import Project
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.autosave.recovery import recovery_dir, session_recovery_path
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.session import SessionPersistenceManager


@pytest.fixture
def context() -> Iterator:
    ctx = build_app_context()
    ctx.ui_controller.show_choice = Mock()
    ctx.ui_controller.show_info_message = Mock()
    yield ctx
    ctx.get_manager(AutoSaveManager).stop()


def _write_pending(context, name: str = "Recovered", file_name: str = "untitled-crashed-session.pplot") -> Path:
    """A copy left by a session that is no longer running (no lock held)."""
    path = recovery_dir() / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    context.get_manager(ProjectManager).save_project(Project(name=name), str(path))
    return path


def _project_name(context, path: Path) -> str:
    return context.get_manager(ProjectManager).load_project(str(path)).name


def _tick(context, qtbot: QtBot) -> None:
    manager = context.get_manager(AutoSaveManager)
    manager._on_timer()
    qtbot.waitUntil(lambda: not manager._recovery_write_in_flight, timeout=10000)


def test_no_recovery_file_asks_nothing(context) -> None:
    offer_recovered_untitled_project(context)

    context.ui_controller.show_choice.assert_not_called()


def test_restore_loads_the_copy_untitled_and_modified_and_adopts_it(context, qtbot: QtBot) -> None:
    pending = _write_pending(context)
    context.ui_controller.show_choice.return_value = True

    offer_recovered_untitled_project(context)

    qtbot.waitUntil(lambda: context.app_state.has_project and context.app_state.is_modified, timeout=10000)
    assert context.app_state.current_project.name == "Recovered"
    assert context.app_state.project_file_path is None
    assert context.get_manager(SessionPersistenceManager).last_project_path is None
    _title, message, accept, reject = context.ui_controller.show_choice.call_args.args
    assert "untitled project" in message
    assert (accept, reject) == ("Restore", "Discard")
    # Kept, now as this session's own copy, until the user saves or discards the restored project.
    qtbot.waitUntil(session_recovery_path().is_file, timeout=10000)
    assert not pending.exists()
    assert _project_name(context, session_recovery_path()) == "Recovered"


def test_discard_deletes_the_copy_and_opens_nothing(context) -> None:
    pending = _write_pending(context)
    context.ui_controller.show_choice.return_value = False

    offer_recovered_untitled_project(context)

    assert not pending.exists()
    assert not context.app_state.has_project


def test_dismissing_the_prompt_keeps_the_copy_for_the_next_launch(context) -> None:
    pending = _write_pending(context)
    context.ui_controller.show_choice.return_value = None

    offer_recovered_untitled_project(context)

    assert pending.is_file()
    assert not context.app_state.has_project
    # The lock is released, so the next launch (here: the next offer) asks again.
    offer_recovered_untitled_project(context)
    assert context.ui_controller.show_choice.call_count == 2


def test_a_copy_held_by_a_running_instance_is_not_offered(context) -> None:
    """Regression (#629 review): with one global recovery file, a second instance offered (and its
    Discard deleted) the copy a running instance was still writing."""
    live = _write_pending(context, file_name="untitled-live-session.pplot")
    lock = QLockFile(str(recovery_dir() / "untitled-live-session.lock"))
    lock.setStaleLockTime(0)
    assert lock.tryLock(0)
    try:
        offer_recovered_untitled_project(context)
    finally:
        lock.unlock()

    context.ui_controller.show_choice.assert_not_called()
    assert live.is_file()


def test_the_newest_pending_copy_is_offered_first(context) -> None:
    import os

    older = _write_pending(context, name="Older", file_name="untitled-a.pplot")
    newer = _write_pending(context, name="Newer", file_name="untitled-b.pplot")
    os.utime(older, (1_000_000, 1_000_000))
    context.ui_controller.show_choice.return_value = False

    offer_recovered_untitled_project(context)

    assert not newer.exists()
    assert older.is_file()


@pytest.mark.parametrize("then", ["quit_without_project", "new_untitled_edited", "titled_opened_and_closed"])
def test_a_dismissed_copy_survives_the_rest_of_the_session(context, qtbot: QtBot, tmp_path: Path, then: str) -> None:
    """Regression (#629 review): after Not Now, quitting with no project open, editing a new untitled
    project (the next tick overwrote the single file), or closing a titled project deleted the copy the
    user chose to keep."""
    pending = _write_pending(context, name="Crashed work")
    context.ui_controller.show_choice.return_value = None
    offer_recovered_untitled_project(context)

    if then == "quit_without_project":
        _flush_save_on_quit(context)
    elif then == "new_untitled_edited":
        context.app_state.load_project(Project(name="Other"))
        context.app_state.mark_modified()
        _tick(context, qtbot)
        assert _project_name(context, session_recovery_path()) == "Other"
    else:
        titled = Project(name="Titled")
        titled.project_file_path = str(tmp_path / "titled.pplot")
        context.app_state.load_project(titled)
        context.app_state.close_project()

    assert pending.is_file()
    assert _project_name(context, pending) == "Crashed work"


def test_launch_without_a_remembered_project_offers_the_copy_straight_away(context) -> None:
    _write_pending(context)
    context.ui_controller.show_choice.return_value = False

    restore_last_session(context, Mock())

    context.ui_controller.show_choice.assert_called_once()


def test_remembered_titled_project_is_restored_first_then_the_copy_is_offered(context, qtbot: QtBot, tmp_path: Path) -> None:
    titled = tmp_path / "titled.pplot"
    context.get_manager(ProjectManager).save_project(Project(name="Titled"), str(titled))
    context.get_manager(SessionPersistenceManager).update_project(str(titled))
    pending = _write_pending(context)
    context.ui_controller.show_choice.return_value = False
    window = Mock()

    restore_last_session(context, window)

    qtbot.waitUntil(lambda: context.ui_controller.show_choice.called, timeout=10000)
    assert context.app_state.current_project.name == "Titled"
    assert context.app_state.project_file_path == str(titled)
    window.tab_container.restore_tab_session.assert_called_once()
    assert not pending.exists()


def test_restore_replacing_a_titled_project_keeps_the_copy_and_rewrites_it_on_the_next_tick(
    context, qtbot: QtBot, tmp_path: Path
) -> None:
    titled = tmp_path / "titled.pplot"
    context.get_manager(ProjectManager).save_project(Project(name="Titled"), str(titled))
    context.get_manager(SessionPersistenceManager).update_project(str(titled))
    _write_pending(context)
    context.ui_controller.show_choice.return_value = True
    window = Mock()
    restore_last_session(context, window)
    qtbot.waitUntil(
        lambda: context.app_state.has_project and context.app_state.current_project.name == "Recovered" and context.app_state.is_modified,
        timeout=10000,
    )
    qtbot.waitUntil(session_recovery_path().is_file, timeout=10000)

    session_recovery_path().unlink()
    _tick(context, qtbot)
    assert session_recovery_path().is_file()


def _write_session_copy(context) -> None:
    session_recovery_path().parent.mkdir(parents=True, exist_ok=True)
    context.get_manager(ProjectManager).save_project(Project(name="Mine"), str(session_recovery_path()))


def test_clean_quit_without_a_project_deletes_only_this_sessions_copy(context) -> None:
    _write_session_copy(context)
    other = _write_pending(context)

    _flush_save_on_quit(context)

    assert not session_recovery_path().exists()
    assert other.is_file()


def test_clean_quit_with_an_unmodified_untitled_project_deletes_the_copy(context) -> None:
    _write_session_copy(context)
    context.app_state.load_project(Project(name="Untitled"))

    _flush_save_on_quit(context)

    assert not session_recovery_path().exists()


def test_quit_with_a_modified_untitled_project_keeps_the_copy(context) -> None:
    _write_session_copy(context)
    context.app_state.load_project(Project(name="Untitled"))
    context.app_state.mark_modified()

    _flush_save_on_quit(context)

    assert session_recovery_path().is_file()
