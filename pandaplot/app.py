
import logging
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.utils.log import setup_logging
from pandaplot.services.config_manager import ConfigManager
from pandaplot.services.theme_manager import ThemeManager


def create_project_data_manager() -> ProjectDataManager:
    item_data_manager_factory = ItemDataManagerFactory()

    item_data_manager_factory.register(
        type_name="note",
        item_class=Note,
        manager=NoteDataManager(),
        extension="note" # TODO: verify if we need file extension at all
    )

    item_data_manager_factory.register(
        type_name="folder",
        item_class=Folder,
        manager=FolderDataManager(),
        extension="folder"
    )

    item_data_manager_factory.register(
        type_name="chart",
        item_class=Chart,
        manager=ChartDataManager(),
        extension="chart"
    )

    item_data_manager_factory.register(
        type_name="dataset",
        item_class=Dataset,
        manager=DatasetDataManager(),
        extension="dataset"
    )

    project_data_manager = ProjectDataManager(item_data_manager_factory)
    return project_data_manager


def main():
    # Setup logging
    logger = setup_logging(level = logging.DEBUG)
    # Load configuration
    logger.info("--------------Starting PandaPlot application--------------")
    # Initialize application state
    event_bus = EventBus()
    project_data_manager = create_project_data_manager()
    app_state = AppState(event_bus,
                         project_data_manager=project_data_manager)

    # Configuration manager
    config_manager = ConfigManager(event_bus)
    config_manager.load()
    theme_manager = ThemeManager(event_bus, config_manager)

    # Create UI controller (will be updated with main window reference later)
    ui_controller = UIController()

    # Create command executor
    command_executor = CommandExecutor()
    app_context = AppContext(
        app_state=app_state,
        event_bus=event_bus,
        command_executor=command_executor,
        ui_controller=ui_controller,
        config_manager=config_manager,
        theme_manager=theme_manager,
    )

    # Initialize GUI components
    app = QApplication(sys.argv)

    # Set global application stylesheet with black text color as default
    # TODO: improve how we handle styles and themes
    app.setStyleSheet("""
        * {
            color: black;
            background-color: white;
        }
    """)

    main_window = PandaMainWindow(app_context)
    theme_manager.set_qt_app(app)
    try:
        theme_manager.apply_current()
    except Exception:  # noqa: BLE001
        logger.exception("Failed applying initial theme")

    # Update UI controller with main window reference
    ui_controller.set_parent_widget(main_window)

    main_window.show()

    # Start the main event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    # TODO: fix add (load damped pendulum project, try to add series to energy graph)
    # TODO: fix remove series
    # TODO: log error messages to the user
    # TODO: fix how we treat transformed columns, they aren't saved correctly
    # TODO: allow project rename, consider creating project creation dialog
    # TODO: improve view of project name
    # TODO: create process for multi-threaded operations
    # TODO: improve initial loading of the app
    # TODO: clean state on opening new project or add support for multiple projects
    # TODO: list and implement copy paste capabilities we want to support
