"""Recovery copy of an untitled project written by AutoSaveManager (#629)."""
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest

from pandaplot.app import build_app_context
from pandaplot.commands.project.project.save_project_command import SaveProjectCommand
from pandaplot.models.events import ProjectEvents
from pandaplot.models.project.project import Project
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.autosave.recovery import delete_recovery_copy, recovery_file_path, recovery_temp_path
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


def test_recovery_path_is_under_the_isolated_home(isolated_home: Path) -> None:
    assert recovery_file_path() == isolated_home / ".pandaplot" / "recovery" / "untitled-recovery.pplot"


def test_modified_untitled_project_writes_a_recovery_copy_and_stays_untitled_and_modified(context) -> None:
    project = _open_untitled(context, modified=True)

    context.get_manager(AutoSaveManager)._on_timer()

    path = recovery_file_path()
    assert path.is_file()
    assert not recovery_temp_path().exists()
    assert project.project_file_path is None
    assert context.app_state.is_modified
    restored = context.get_manager(ProjectManager).load_project(str(path))
    assert restored.name == "Untitled work"


def test_untouched_untitled_project_writes_nothing(context) -> None:
    _open_untitled(context, modified=False)

    context.get_manager(AutoSaveManager)._on_timer()

    assert not recovery_file_path().exists()


def test_unchanged_project_is_not_rewritten_but_a_new_edit_is(context) -> None:
    _open_untitled(context, modified=True)
    manager = context.get_manager(AutoSaveManager)
    manager._on_timer()
    first = recovery_file_path().stat().st_mtime_ns

    manager._on_timer()
    assert recovery_file_path().stat().st_mtime_ns == first

    context.app_state.mark_modified()
    manager._on_timer()
    assert recovery_file_path().stat().st_mtime_ns != first


def test_a_save_in_flight_postpones_the_recovery_copy(context) -> None:
    _open_untitled(context, modified=True)
    context.app_state.begin_save()

    context.get_manager(AutoSaveManager)._on_timer()

    assert not recovery_file_path().exists()


def test_failed_recovery_write_leaves_the_previous_copy_and_no_temp_file(context, monkeypatch: pytest.MonkeyPatch) -> None:
    _open_untitled(context, modified=True)
    manager = context.get_manager(AutoSaveManager)
    manager._on_timer()
    good = recovery_file_path().read_bytes()
    context.app_state.mark_modified()

    def fail(_self, _project, file_path: str) -> bool:
        Path(file_path).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(ProjectManager, "save_project", fail)
    manager._on_timer()

    assert recovery_file_path().read_bytes() == good
    assert not recovery_temp_path().exists()


def test_titled_project_still_saves_in_place_and_writes_no_recovery_copy(context, tmp_path: Path) -> None:
    project = Project(name="Titled")
    project.project_file_path = str(tmp_path / "titled.pplot")
    context.app_state.load_project(project)
    context.app_state.mark_modified()
    executor = Mock()
    context.get_command_executor = lambda: executor

    context.get_manager(AutoSaveManager)._on_timer()

    command = executor.execute_command.call_args.args[0]
    assert isinstance(command, SaveProjectCommand)
    assert not recovery_file_path().exists()


def test_recovery_copy_is_deleted_when_an_untitled_project_gets_its_first_path(context) -> None:
    project = _open_untitled(context, modified=True)
    context.get_manager(AutoSaveManager)._on_timer()
    assert recovery_file_path().exists()

    context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": "/x/a.pplot", "previous_path": None})

    assert not recovery_file_path().exists()


def test_titled_autosave_event_does_not_delete_a_pending_recovery_copy(context) -> None:
    path = recovery_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pending restore offer")

    context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": Mock(), "file_path": "/x/a.pplot", "previous_path": "/x/a.pplot"})

    assert path.exists()


def test_delete_recovery_copy_removes_both_files_and_tolerates_missing(context) -> None:
    delete_recovery_copy()
    recovery_file_path().parent.mkdir(parents=True, exist_ok=True)
    recovery_file_path().write_bytes(b"a")
    recovery_temp_path().write_bytes(b"b")

    delete_recovery_copy()

    assert not recovery_file_path().exists()
    assert not recovery_temp_path().exists()
