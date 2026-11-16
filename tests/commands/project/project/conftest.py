"""Shared fixtures for project lifecycle command tests that touch the disk."""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from pandaplot.models.events import EventBus
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import UnsavedChangesRegistry
from pandaplot.models.state.app_state import AppState
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.session import SessionPersistenceManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.project_data_manager import ProjectDataManager


@dataclass
class DiskEnv:
    """A real AppState, ProjectManager and storage stack; only the UI and session store are fakes."""

    app_context: Mock
    app_state: AppState
    ui_controller: Mock
    project_manager: ProjectManager
    session: Mock
    unsaved_changes: Mock


@pytest.fixture
def disk_env(sync_task_scheduler) -> DiskEnv:
    factory = ItemDataManagerFactory()
    factory.register("dataset", Dataset, DatasetDataManager(), "dataset")
    project_manager = ProjectManager(ProjectDataManager(factory))
    app_state = AppState(EventBus())
    ui_controller = Mock()
    session = Mock(spec=SessionPersistenceManager)
    unsaved_changes = Mock(spec=UnsavedChangesRegistry)
    unsaved_changes.flush_all.return_value = True
    managers = {
        ProjectManager: project_manager,
        SessionPersistenceManager: session,
        UnsavedChangesRegistry: unsaved_changes,
    }

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = app_state.event_bus
    app_context.get_ui_controller.return_value = ui_controller
    app_context.get_task_scheduler.return_value = sync_task_scheduler
    app_context.get_manager.side_effect = managers.__getitem__
    return DiskEnv(app_context, app_state, ui_controller, project_manager, session, unsaved_changes)
