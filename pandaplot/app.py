
import logging
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers import UIController
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.events import EventBus
from pandaplot.models.project.items import Chart, Dataset, Folder, Note
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme import ThemeManager
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.utils.log import setup_logging


def create_project_data_manager() -> ProjectDataManager:
    """Register item data managers and build the project data manager."""
    factory = ItemDataManagerFactory()
    # TODO: verify extension usage
    factory.register("note", Note, NoteDataManager(), "note")
    factory.register("folder", Folder, FolderDataManager(), "folder")
    factory.register("chart", Chart, ChartDataManager(), "chart")
    factory.register("dataset", Dataset, DatasetDataManager(), "dataset")
    return ProjectDataManager(factory)


def build_app_context(logger: logging.Logger) -> AppContext:
    """Create and return a fully initialized AppContext (no Qt widgets yet)."""
    event_bus = EventBus()
    project_data_manager = create_project_data_manager()
    app_state = AppState(event_bus, project_data_manager=project_data_manager)
    config_manager = ConfigManager(event_bus)
    config_manager.load()
    theme_manager = ThemeManager(event_bus, config_manager)
    ui_controller = UIController()
    command_executor = CommandExecutor()
    return AppContext(
        app_state=app_state,
        event_bus=event_bus,
        command_executor=command_executor,
        ui_controller=ui_controller,
        config_manager=config_manager,
        theme_manager=theme_manager,
    )


def create_qt_application(app_context: AppContext, argv: list[str] | None = None) -> tuple[QApplication, PandaMainWindow]:
    """Instantiate QApplication and the main window.

    Returns (app, main_window)
    """
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    # Global simple baseline stylesheet (theme manager can override specifics)
    app.setStyleSheet("""* { color: black; background-color: white; }""")

    main_window = PandaMainWindow(app_context)
    theme_mgr = app_context.get_theme_manager()
    theme_mgr.set_qt_app(app)
    try:
        theme_mgr.apply_current()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Failed applying initial theme")
    app_context.ui_controller.set_parent_widget(main_window)
    return app, main_window


def launch(app_context: AppContext | None = None) -> int:
    """Launch the GUI event loop.

    Returns the Qt application's exit code.
    """
    logger = logging.getLogger(__name__)
    if app_context is None:
        if not logging.getLogger().handlers:
            setup_logging(level=logging.DEBUG)
        logger.info("Building default AppContext inside launch()")
        app_context = build_app_context(logger)
    app, main_window = create_qt_application(app_context)
    main_window.show()
    return app.exec()


def main() -> None:
    """CLI entry point for `python -m pandaplot.app`."""
    logger = setup_logging(level=logging.DEBUG)
    logger.info("--------------Starting PandaPlot application--------------")
    app_context = build_app_context(logger)
    sys.exit(launch(app_context))


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
    # TODO: improve how we handle styles and themes
    # TODO: ask whether open project needs to be saved before closing - either a new project or open documents that have been modified. We can track modifications somewhere if needed.
    # TODO: save on an existing project is acting as save as, we need to fix this behavior.
    # TODO: enable chart creation without opening a dataset
    # TODO: remove dialog on project open success
    # TODO: improve project info display in sidebar
    # TODO: fix saved state tracking - when opening a project it should say it's saved until modified
    # TODO: disable chart properties and curve fitting sidepanels on dataset view
    # TODO: close open tabs related to a project when closing project
    # TODO: in chart properties panel, fix tab display, ensure buttons are visible
    # TODO: fix how we use font size across the app.
    # TODO: fix dark theme colors
    # TODO: make chart area scrollable
    # TODO: in dataset tab we should show all of the data, but we should load it lazily