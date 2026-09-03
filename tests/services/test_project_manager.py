"""Tests for ProjectManager (#218): it now owns a ProjectDataManager
internally and delegates the actual file I/O to it, instead of every
caller (commands, app.py) reaching into ProjectDataManager directly.
"""
from unittest.mock import Mock

import pytest

from pandaplot.models.project.project import Project
from pandaplot.services.data_managers.project_manager import ProjectManager


@pytest.fixture
def data_manager():
    return Mock()


@pytest.fixture
def manager(data_manager):
    return ProjectManager(data_manager)


def test_create_project_returns_a_new_empty_project(manager):
    project = manager.create_project("My Project")

    assert isinstance(project, Project)
    assert project.name == "My Project"


def test_load_project_delegates_to_the_data_manager(manager, data_manager, tmp_path):
    file_path = tmp_path / "sample.pplot"
    file_path.write_bytes(b"not a real zip, just needs to exist")
    loaded = Project(name="Loaded")
    data_manager.load.return_value = loaded

    result = manager.load_project(str(file_path))

    assert result is loaded
    data_manager.load.assert_called_once_with(str(file_path))


def test_load_project_raises_when_file_missing(manager, data_manager, tmp_path):
    missing = tmp_path / "missing.pplot"

    with pytest.raises(FileNotFoundError):
        manager.load_project(str(missing))
    data_manager.load.assert_not_called()


def test_load_project_raises_on_unsupported_extension(manager, data_manager, tmp_path):
    wrong_ext = tmp_path / "sample.txt"
    wrong_ext.write_text("hello")

    with pytest.raises(ValueError, match="Unsupported file format"):
        manager.load_project(str(wrong_ext))
    data_manager.load.assert_not_called()


def test_save_project_delegates_to_the_data_manager(manager, data_manager, tmp_path):
    project = Project(name="P")
    file_path = tmp_path / "out.pplot"

    result = manager.save_project(project, str(file_path))

    assert result is True
    data_manager.save.assert_called_once_with(project, str(file_path))


def test_save_project_creates_parent_directories(manager, tmp_path):
    project = Project(name="P")
    file_path = tmp_path / "nested" / "dir" / "out.pplot"

    manager.save_project(project, str(file_path))

    assert file_path.parent.is_dir()


def test_save_project_raises_on_unsupported_extension(manager, data_manager, tmp_path):
    project = Project(name="P")
    file_path = tmp_path / "out.json"

    with pytest.raises(ValueError, match="Unsupported file format"):
        manager.save_project(project, str(file_path))
    data_manager.save.assert_not_called()


def test_validate_project_file_true_for_existing_pplot_file(manager, tmp_path):
    file_path = tmp_path / "sample.pplot"
    file_path.write_bytes(b"anything")

    assert manager.validate_project_file(str(file_path)) is True


def test_validate_project_file_false_for_missing_file(manager, tmp_path):
    assert manager.validate_project_file(str(tmp_path / "nope.pplot")) is False


def test_validate_project_file_false_for_wrong_extension(manager, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hi")

    assert manager.validate_project_file(str(file_path)) is False


def test_get_recent_projects_returns_empty_list(manager):
    assert manager.get_recent_projects() == []
