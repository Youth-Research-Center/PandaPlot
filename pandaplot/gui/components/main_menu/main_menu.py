from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QWidget
from PySide6.QtGui import QAction

from pandaplot.commands.app.exit_command import ExitCommand
from pandaplot.commands.project.project.new_project_command import NewProjectCommand
from pandaplot.commands.project.project.open_project_command import OpenProjectCommand
from pandaplot.commands.project.project.save_project_command import SaveProjectAsCommand, SaveProjectCommand
from pandaplot.commands.project.note.create_note_command import CreateNoteCommand
from pandaplot.commands.project.dataset.import_csv_command import ImportCsvCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
from pandaplot.models.state.app_context import AppContext
import logging

def show_about():
    # TODO: Implement a proper about dialog
    QMessageBox.about(None, "About", "This is a sample app")


class MainMenu(QMenuBar):
    def __init__(self, parent: QWidget, app_context:AppContext):
        super().__init__(parent)
        self.app_context = app_context
        self.logger = logging.getLogger(__name__)
        self.create_menu()

    def create_menu(self):
        # File menu
        file_menu = QMenu("Project", self)
        self.addMenu(file_menu)
        
        new_action = QAction("New", self)
        new_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(NewProjectCommand(self.app_context)))
        file_menu.addAction(new_action)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(OpenProjectCommand(self.app_context)))
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(SaveProjectCommand(self.app_context)))
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(SaveProjectAsCommand(self.app_context)))
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(ExitCommand(self.app_context)))
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = QMenu("Edit", self)
        self.addMenu(edit_menu)
        
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(lambda: self.app_context.get_command_executor().undo())
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(lambda: self.app_context.get_command_executor().redo())
        edit_menu.addAction(redo_action)

        # Data menu
        data_menu = QMenu("Data", self)
        self.addMenu(data_menu)
        
        import_csv_action = QAction("Import CSV...", self)
        import_csv_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(ImportCsvCommand(self.app_context)))
        data_menu.addAction(import_csv_action)
        
        create_empty_dataset_action = QAction("Create Empty Dataset", self)
        create_empty_dataset_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(CreateEmptyDatasetCommand(self.app_context)))
        data_menu.addAction(create_empty_dataset_action)

        data_menu.addSeparator()
        
        new_note_action = QAction("New Note", self)
        new_note_action.triggered.connect(lambda: self.app_context.get_command_executor().execute_command(CreateNoteCommand(self.app_context)))
        data_menu.addAction(new_note_action)

        # Settings menu
        settings_menu = QMenu("Settings", self)
        self.addMenu(settings_menu)
        
        preferences_action = QAction("⚙️ Preferences...", self)
        preferences_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = QMenu("Help", self)
        self.addMenu(help_menu)
        
        about_action = QAction("About", self)
        about_action.triggered.connect(show_about)
        help_menu.addAction(about_action)

    def show_settings_dialog(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self.app_context, self.parent())
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()
    
    def on_settings_changed(self, settings):
        """Handle settings changes."""
        self.logger.info("MainMenu settings changed: %s", settings)
        # TODO: Apply settings to the application
