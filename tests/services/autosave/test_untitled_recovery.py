"""This session's recovery copy of an untitled project, written by AutoSaveManager (#629)."""
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytestqt.qtbot import QtBot

from pandaplot.app import build_app_context
from pandaplot.commands.project.project.save_project_command import SaveProjectCommand
from pandaplot.models.events import ProjectEvents
from pandaplot.models.project.project import Project
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.autosave.recovery import (
    SESSION_ID,
    delete_session_recovery_copy,
    recovery_dir,
    session_recovery_path,
    session_recovery_temp_path,
)
from pandaplot.services.data_managers.project_manager import ProjectManager


@pytest.fixture
def context() -> Iterator:
    ctx = build_app_context()
    yield ctx
    ctx.get_manager(AutoSaveManager).stop()


def _open_untitled(context, *, modified: bool) -> Project:
    project = Project(name="Untitled work")
    context.app_state.load_project(project)
    if modified:
        context.app_state.mark_modified()
    return project


def _tick(context, qtbot: QtBot) -> None:
    """Run one auto-save tick and wait for its background recovery write to finish."""
    manager = context.get_manager(AutoSaveManager)
    manager._on_timer()
    qtbot.waitUntil(lambda: not manager._recovery_write_in_flight, timeout=10000)


def _other_sessions_copy(name: str = "untitled-other-session.pplot") -> Path:
    path = recovery_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"another session's copy")
    return path


def test_session_copy_is_per_process_and_under_the_isolated_home(isolated_home: Path) -> None:
    assert session_recovery_path() == isolated_home / ".pandaplot" / "recovery" / f"untitled-{SESSION_ID}.pplot"
    assert SESSION_ID.startswith(f"{os.getpid()}-")


def test_modified_untitled_project_writes_a_recovery_copy_and_stays_untitled_and_modified(context, qtbot: QtBot) -> None:
    project = _open_untitled(context, modified=True)

    _tick(context, qtbot)

    path = session_recovery_path()
    assert path.is_file()
    assert not session_recovery_temp_path().exists()
    assert project.project_file_path is None
    assert context.app_state.is_modified
    restored = context.get_manager(ProjectManager).load_project(str(path))
    assert restored.name == "Untitled work"


def test_recovery_copy_is_written_off_the_gui_thread(context, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression (#629 review): serialising a large untitled project on every tick froze the UI."""
    import threading

    threads: list[threading.Thread] = []
    original = ProjectManager.save_project

    def record_thread(self, project, file_path: str):
        threads.append(threading.current_thread())
        return original(self, project, file_path)

    monkeypatch.setattr(ProjectManager, "save_project", record_thread)
    _open_untitled(context, modified=True)

    _tick(context, qtbot)

    assert threads
    assert threads[0] is not threading.main_thread()
    assert session_recovery_path().is_file()


def test_untouched_untitled_project_writes_nothing(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=False)

    _tick(context, qtbot)

    assert not session_recovery_path().exists()


def test_unchanged_project_is_not_rewritten_but_a_new_edit_is(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=True)
    _tick(context, qtbot)
    first = session_recovery_path().stat().st_mtime_ns

    _tick(context, qtbot)
    assert session_recovery_path().stat().st_mtime_ns == first

    context.app_state.mark_modified()
    _tick(context, qtbot)
    assert session_recovery_path().stat().st_mtime_ns != first


def test_a_save_in_flight_postpones_the_recovery_copy(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=True)
    context.app_state.begin_save()

    _tick(context, qtbot)

    assert not session_recovery_path().exists()


def test_failed_recovery_write_leaves_the_previous_copy_and_no_temp_file(context, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    _open_untitled(context, modified=True)
    _tick(context, qtbot)
    good = session_recovery_path().read_bytes()
    context.app_state.mark_modified()

    def fail(_self, _project, file_path: str) -> bool:
        Path(file_path).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(ProjectManager, "save_project", fail)
    _tick(context, qtbot)

    assert session_recovery_path().read_bytes() == good
    assert not session_recovery_temp_path().exists()


def test_a_copy_that_became_stale_during_a_background_write_is_not_recreated(context, qtbot: QtBot) -> None:
    """The project is saved (or closed) while its copy is still being written: the finished write is dropped."""
    project = _open_untitled(context, modified=True)
    manager = context.get_manager(AutoSaveManager)

    manager._on_timer()
    assert manager._recovery_write_in_flight
    context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": "/x/a.pplot", "previous_path": None})
    qtbot.waitUntil(lambda: not manager._recovery_write_in_flight, timeout=10000)

    assert not session_recovery_path().exists()
    assert not session_recovery_temp_path().exists()


def test_titled_project_still_saves_in_place_and_writes_no_recovery_copy(context, qtbot: QtBot, tmp_path: Path) -> None:
    project = Project(name="Titled")
    project.project_file_path = str(tmp_path / "titled.pplot")
    context.app_state.load_project(project)
    context.app_state.mark_modified()
    executor = Mock()
    context.get_command_executor = lambda: executor

    _tick(context, qtbot)

    command = executor.execute_command.call_args.args[0]
    assert isinstance(command, SaveProjectCommand)
    assert not session_recovery_path().exists()


def test_recovery_copy_is_deleted_when_an_untitled_project_gets_its_first_path(context, qtbot: QtBot) -> None:
    project = _open_untitled(context, modified=True)
    _tick(context, qtbot)
    assert session_recovery_path().exists()

    context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": "/x/a.pplot", "previous_path": None})

    assert not session_recovery_path().exists()


def test_titled_autosave_event_does_not_delete_the_session_copy(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=True)
    _tick(context, qtbot)

    context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": Mock(), "file_path": "/x/a.pplot", "previous_path": "/x/a.pplot"})

    assert session_recovery_path().exists()


def test_delete_session_recovery_copy_removes_both_files_and_tolerates_missing(context) -> None:
    delete_session_recovery_copy()
    recovery_dir().mkdir(parents=True, exist_ok=True)
    session_recovery_path().write_bytes(b"a")
    session_recovery_temp_path().write_bytes(b"b")

    delete_session_recovery_copy()

    assert not session_recovery_path().exists()
    assert not session_recovery_temp_path().exists()


def test_closing_an_unmodified_untitled_project_deletes_the_copy(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=True)
    _tick(context, qtbot)
    context.app_state.mark_saved()  # e.g. the edits were undone
    assert session_recovery_path().exists()

    context.app_state.close_project()

    assert not session_recovery_path().exists()


def test_closed_project_is_rewritten_after_the_stamp_reset(context, qtbot: QtBot) -> None:
    project = _open_untitled(context, modified=True)
    _tick(context, qtbot)
    context.app_state.close_project()
    context.app_state.load_project(project)
    context.app_state.mark_modified()

    _tick(context, qtbot)

    assert session_recovery_path().is_file()


def test_replacing_an_untitled_project_deletes_the_session_copy(context, qtbot: QtBot) -> None:
    _open_untitled(context, modified=True)
    _tick(context, qtbot)

    context.app_state.load_project(Project(name="Other"))

    assert not session_recovery_path().exists()


@pytest.mark.parametrize("event", ["closed", "replaced", "first_save"])
def test_session_cleanup_never_deletes_another_sessions_copy(context, qtbot: QtBot, event: str) -> None:
    """Regression (#629 review): one global recovery file meant this session's cleanup (closing or
    replacing a project, a first save) deleted a copy left by a crashed session or written by another
    running instance."""
    other = _other_sessions_copy()
    project = _open_untitled(context, modified=True)
    _tick(context, qtbot)

    if event == "closed":
        context.app_state.close_project()
    elif event == "replaced":
        context.app_state.load_project(Project(name="Other"))
    else:
        context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": "/x/a.pplot", "previous_path": None})

    assert other.read_bytes() == b"another session's copy"
    assert not session_recovery_path().exists()


def test_writing_the_session_copy_never_overwrites_another_sessions_copy(context, qtbot: QtBot) -> None:
    other = _other_sessions_copy()
    _open_untitled(context, modified=True)

    _tick(context, qtbot)

    assert other.read_bytes() == b"another session's copy"
    assert session_recovery_path().is_file()
