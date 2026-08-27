from typing import override

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

from pandaplot.commands.app.exit_command import ExitCommand
from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.commands.project.dataset import ImportDataCommand
from pandaplot.commands.project.dataset.add_rows_columns_command import (
    AddRowsColumnsCommand,
)
from pandaplot.commands.project.dataset.create_empty_dataset_command import (
    CreateEmptyDatasetCommand,
)
from pandaplot.commands.project.note import CreateNoteCommand
from pandaplot.commands.project.project import (
    CloseProjectCommand,
    LoadProjectCommand,
    NewProjectCommand,
    OpenProjectCommand,
    SaveProjectAsCommand,
    SaveProjectCommand,
)
from pandaplot.gui.core.widget_extension import PMenuBar
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class MainMenu(PMenuBar):
    def __init__(self, parent: QWidget, app_context: AppContext):
        super().__init__(app_context=app_context, parent=parent)
        # Dataset of the currently active tab, if any -- used to preselect the
        # dataset in dialogs opened from the menu.
        self.active_dataset_id: str | None = None
        self._initialize()

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to the main menu based on current theme."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        card_bg = palette.get("card_bg", "#F0F0F0")
        base_fg = palette.get("base_fg", "#000000")
        card_border = palette.get("card_border", "#D0D0D0")
        accent = palette.get("accent", "#4A90E2")
        card_pressed = palette.get("card_pressed", "#dee2e6")
        
        # Apply dynamic theme-based styling
        self.setStyleSheet(f"""
            QMenuBar {{
                background-color: {card_bg};
                color: {base_fg};
                border-bottom: 1px solid {card_border};
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 4px 8px;
                margin: 2px;
                border-radius: 3px;
            }}
            QMenuBar::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenuBar::item:pressed {{
                background-color: {card_pressed};
                color: {base_fg};
            }}
            QMenu {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                color: {base_fg};
                margin: 2px;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 6px 20px;
                margin: 1px;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: white;
            }}
            QMenu::item:pressed {{
                background-color: {card_pressed};
                color: {base_fg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {card_border};
                margin: 2px 10px;
            }}
        """)
        
        self.logger.debug("Applied theme.")
    
    @override
    def _init_ui(self):
        self.logger.debug("Creating main menu")
        
        # File menu
        file_menu = self._create_file_menu()
        self.addMenu(file_menu)

        # Edit menu
        edit_menu = self._create_edit_menu()
        self.addMenu(edit_menu)

        # Data menu
        data_menu = self._create_data_menu()
        self.addMenu(data_menu)

        # Chart menu
        chart_menu = self._create_chart_menu()
        self.addMenu(chart_menu)

        # Settings menu
        settings_menu = QMenu("Settings", self)
        self.addMenu(settings_menu)

        preferences_action = QAction("Preferences...", self)
        # TODO(#216): consider showing settings dialog by triggering event which invokes a command
        preferences_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = QMenu("Help", self)
        self.addMenu(help_menu)

        open_example_project_action = QAction("Open Example Project...", self)
        open_example_project_action.triggered.connect(self.show_examples_dialog)
        help_menu.addAction(open_example_project_action)

        help_menu.addSeparator()

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def _create_file_menu(self) -> QMenu:
        file_menu = QMenu("Project", self)
        new_action = QAction("New", self)
        new_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(NewProjectCommand(self.app_context)))
        file_menu.addAction(new_action)

        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(OpenProjectCommand(self.app_context)))
        file_menu.addAction(open_action)

        close_action = QAction("Close", self)
        close_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(CloseProjectCommand(self.app_context)))
        file_menu.addAction(close_action)

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(SaveProjectCommand(self.app_context)))
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(SaveProjectAsCommand(self.app_context)))
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(ExitCommand(self.app_context)))
        file_menu.addAction(exit_action)

        return file_menu
    
    def _create_edit_menu(self) -> QMenu:
        edit_menu = QMenu("Edit", self)

        # TODO(#206): disable undo/redo when there are no actions to undo/redo
        # self.undo_button.setEnabled(False)  # start disabled
        # we need to listen to app event based on command executor
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(
            lambda: self.app_context.get_command_executor().undo())
        edit_menu.addAction(undo_action)

        

        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(
            lambda: self.app_context.get_command_executor().redo())
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)
        return edit_menu

    def _create_data_menu(self) -> QMenu:
        data_menu = QMenu("Data", self)

        import_data_action = QAction("Import Data...", self)
        import_data_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(ImportDataCommand(self.app_context)))
        data_menu.addAction(import_data_action)

        create_empty_dataset_action = QAction("Add Dataset", self)
        create_empty_dataset_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(CreateEmptyDatasetCommand(self.app_context)))
        data_menu.addAction(create_empty_dataset_action)

        import_images_action = QAction("Import Images...", self)
        import_images_action.triggered.connect(self._on_import_images_from_menu)
        data_menu.addAction(import_images_action)

        self.add_rows_columns_action = QAction("Add Rows / Columns...", self)
        self.add_rows_columns_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(AddRowsColumnsCommand(self.app_context, dataset_id=self.active_dataset_id)))
        data_menu.addAction(self.add_rows_columns_action)

        data_menu.addSeparator()

        new_note_action = QAction("New Note", self)
        new_note_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(CreateNoteCommand(self.app_context)))
        data_menu.addAction(new_note_action)
        return data_menu

    def _on_import_images_from_menu(self):
        """Import Images from the Data menu always targets a brand-new top-level
        gallery -- unlike the sidebar's version, this menu has no tree
        selection context to reuse an existing gallery from."""
        from PySide6.QtWidgets import QDialog

        from pandaplot.commands.project.image import CreateImageGalleryCommand, ImportImagesCommand
        from pandaplot.gui.dialogs.image.image_import_dialog import ImageImportDialog

        dialog = ImageImportDialog(self.app_context, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        create_command = CreateImageGalleryCommand(self.app_context, parent_id=None)
        self.app_context.get_command_executor().execute_command(create_command)
        gallery_id = create_command.created_gallery_id
        if gallery_id is None:
            return

        import_command = ImportImagesCommand(
            self.app_context, gallery_id=gallery_id,
            sources=dialog.get_sources(), copy_into_project=dialog.get_copy_into_project(),
        )
        self.app_context.get_command_executor().execute_command(import_command)

    def _create_chart_menu(self) -> QMenu:
        chart_menu = QMenu("Chart", self)

        self.create_chart_action = QAction("Create New", self)
        self.create_chart_action.triggered.connect(lambda: self.app_context.get_command_executor(
        ).execute_command(CreateChartFromWizardCommand(self.app_context)))
        chart_menu.addAction(self.create_chart_action)

        self._update_dataset_dependent_actions()
        return chart_menu

    def _update_dataset_dependent_actions(self):
        """Enable the action that needs an existing dataset (row/column
        insertion) to act on. Chart creation is always enabled -- it now
        offers to create a project on the spot if none is open (see
        CreateChartFromWizardCommand / ensure_project_or_offer_create)."""
        app_state = self.app_context.get_app_state()
        has_project = bool(app_state.has_project and app_state.current_project)
        has_datasets = False
        if has_project:
            has_datasets = any(
                isinstance(item, Dataset) for item in app_state.current_project.get_all_items()
            )
        self.add_rows_columns_action.setEnabled(has_datasets)

    def _on_tab_changed(self, event_data: dict):
        """Track the active tab's dataset so menu dialogs can preselect it."""
        self.active_dataset_id = event_data.get("dataset_id")

    @override
    def setup_event_subscriptions(self):
        from pandaplot.models.events import ProjectEvents, UIEvents
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_ADDED, lambda _data: self._update_dataset_dependent_actions())
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_REMOVED, lambda _data: self._update_dataset_dependent_actions())
        self.subscribe_to_event(ProjectEvents.PROJECT_LOADED, lambda _data: self._update_dataset_dependent_actions())
        self.subscribe_to_event(ProjectEvents.PROJECT_CLOSED, lambda _data: self._update_dataset_dependent_actions())
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)

    def show_settings_dialog(self):
        """Show the settings dialog."""
        from pandaplot.gui.dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.app_context, self.parent())
        dialog.exec()

    def show_examples_dialog(self):
        """Open the examples dialog and load the chosen example project, if any."""
        from pandaplot.gui.dialogs.examples_dialog import ExamplesDialog

        dialog = ExamplesDialog(self.app_context, self.parent())
        if not dialog.exec() or not dialog.selected_path:
            return

        if self.app_context.get_app_state().has_project:
            should_continue = self.app_context.get_ui_controller().show_question(
                "Open Example Project",
                "Opening the example project will close the current project.\nAny unsaved changes will be lost.\n\nDo you want to continue?",
            )
            if not should_continue:
                return

        self.app_context.get_command_executor().execute_command(
            LoadProjectCommand(self.app_context, dialog.selected_path)
        )

    def show_about_dialog(self):
        """Show the about dialog."""
        from pandaplot.gui.dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(self.app_context, self.parent())
        dialog.exec()
