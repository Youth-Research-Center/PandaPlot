
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.utils.log import setup_logging


def create_project_data_manager() -> ProjectDataManager:
    item_data_manager_factory = ItemDataManagerFactory()

    item_data_manager_factory.register(
        type_name="note",
        item_class=Note,
        manager=NoteDataManager(),
        extension="note"  # base name, manager decides if it's `.json`/`.md`
    )

    item_data_manager_factory.register(
        type_name="folder",
        item_class=Folder,
        manager=FolderDataManager(),
        extension="folder"
    )

    project_data_manager = ProjectDataManager(item_data_manager_factory)
    return project_data_manager


def main():
    # Setup logging
    setup_logging()
    # Load configuration

    # Initialize application state
    event_bus = EventBus()
    project_data_manager = create_project_data_manager()
    app_state = AppState(event_bus,
                         project_data_manager=project_data_manager)

    # Create UI controller (will be updated with main window reference later)
    ui_controller = UIController()

    # Create command executor
    command_executor = CommandExecutor()
    app_context = AppContext(
        app_state=app_state,
        event_bus=event_bus,
        command_executor=command_executor,
        ui_controller=ui_controller
    )

    # Initialize GUI components

    app = QApplication(sys.argv)

    # Set global application stylesheet with black text color as default
    app.setStyleSheet("""
        * {
            color: black;
            background-color: white;
        }
    """)

    main_window = PandaMainWindow(app_context)

    # Update UI controller with main window reference
    ui_controller.set_parent_widget(main_window)

    main_window.show()

    # Start the main event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    # TODO: fix remove series
    # TODO: fix file tree widget to get refreshed after deleting items and item collections
