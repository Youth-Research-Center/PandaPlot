"""Tests for AutoSaveManager's choice of which projects to save."""

from unittest.mock import Mock

from pandaplot.app import _flush_save_on_quit
from pandaplot.services.autosave.auto_save_manager import AutoSaveManager


def _examples_dir(tmp_path, monkeypatch):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    monkeypatch.setattr("pandaplot.utils.examples.get_examples_dir", lambda: examples_dir)
    return examples_dir


def _manager(project_file_path: str) -> tuple[AutoSaveManager, Mock]:
    app_state = Mock()
    app_state.has_project = True
    app_state.project_file_path = project_file_path
    app_state.is_saving = False
    manager = AutoSaveManager(Mock(), Mock(), app_state)
    app_context = Mock()
    manager.set_app_context(app_context)
    return manager, app_context


def test_auto_save_skips_a_project_whose_path_is_inside_the_examples_dir(tmp_path, monkeypatch):
    """Regression (#607 review): auto-save must never write over a bundled example (nor pop up the Save
    dialog that SaveProjectCommand shows for such a path)."""
    examples_dir = _examples_dir(tmp_path, monkeypatch)
    manager, app_context = _manager(str(examples_dir / "demo.pplot"))

    manager._on_timer()

    app_context.get_command_executor.return_value.execute_command.assert_not_called()


def test_auto_save_saves_a_project_outside_the_examples_dir(tmp_path, monkeypatch):
    _examples_dir(tmp_path, monkeypatch)
    manager, app_context = _manager(str(tmp_path / "mine.pplot"))

    manager._on_timer()

    app_context.get_command_executor.return_value.execute_command.assert_called_once()


def test_flush_save_on_quit_never_writes_into_the_examples_dir(tmp_path, monkeypatch):
    examples_dir = _examples_dir(tmp_path, monkeypatch)
    app_context = Mock()
    app_state = app_context.get_app_state.return_value
    app_state.has_project = True
    app_state.project_file_path = str(examples_dir / "demo.pplot")

    _flush_save_on_quit(app_context)

    app_context.get_manager.return_value.save_project.assert_not_called()


def test_flush_save_on_quit_saves_a_project_outside_the_examples_dir(tmp_path, monkeypatch):
    _examples_dir(tmp_path, monkeypatch)
    app_context = Mock()
    app_state = app_context.get_app_state.return_value
    app_state.has_project = True
    app_state.project_file_path = str(tmp_path / "mine.pplot")

    _flush_save_on_quit(app_context)

    app_context.get_manager.return_value.save_project.assert_called_once_with(app_state.current_project, str(tmp_path / "mine.pplot"))
