import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog

from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.commands.project.dataset import ImportDataCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import (
    CreateEmptyDatasetCommand,
)
from pandaplot.commands.project.folder import CreateFolderCommand
from pandaplot.commands.project.image import CreateImageGalleryCommand, ImportImagesCommand
from pandaplot.commands.project.item import DeleteItemCommand
from pandaplot.commands.project.note import CreateNoteCommand
from pandaplot.commands.project.project import RenameProjectCommand
from pandaplot.commands.project.sketch import CreateSketchCommand
from pandaplot.models.events.event_data import TabOpenRequestedData
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.state.app_context import AppContext


class ProjectPanelCommandManager:
    def __init__(self,
                 app_context: AppContext,
                 get_target_folder_id,
                 get_current_item,
                 get_selected_item_info,
                 edit_item,
                 parent_widget=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.get_target_folder_id = get_target_folder_id
        self.get_current_item = get_current_item
        self.get_selected_item_info = get_selected_item_info
        self.edit_item = edit_item
        self.parent_widget = parent_widget

    def add_folder(self):
        """Add a new folder."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateFolderCommand(self.app_context, parent_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def add_note(self):
        """Add a new note."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateNoteCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def add_sketch(self):
        """Add a new sketch."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateSketchCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def import_data(self):
        """Import a data file (CSV/TSV or single-sheet Excel) as a dataset."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = ImportDataCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def add_image_gallery(self):
        """Add a new image gallery."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateImageGalleryCommand(self.app_context, parent_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def import_images(self):
        """Import images into the selected image gallery, creating one first if none is selected."""
        if not self.app_state.has_project:
            return

        selected_info = self.get_selected_item_info()
        gallery_id = None
        if selected_info and selected_info["type"] == "imagegallery":
            gallery_id = selected_info["id"]

        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.image.image_import_dialog import ImageImportDialog

        dialog = ImageImportDialog(self.app_context, parent=self.parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if gallery_id is None:
            create_command = CreateImageGalleryCommand(self.app_context, parent_id=self.get_target_folder_id())
            self.app_context.get_command_executor().execute_command(create_command)
            gallery_id = create_command.created_gallery_id
            if gallery_id is None:
                return

        import_command = ImportImagesCommand(
            self.app_context, gallery_id=gallery_id,
            sources=dialog.get_sources(), copy_into_project=dialog.get_copy_into_project(),
        )
        self.app_context.get_command_executor().execute_command(import_command)

    def create_empty_dataset(self):
        """Create a new empty dataset."""
        if not self.app_state.has_project:
            return

        folder_id = self.get_target_folder_id()

        command = CreateEmptyDatasetCommand(
            self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def _preselected_column_ids(self, dataset_id) -> list[str]:
        """Columns already selected in that dataset's table view, if its tab is open.

        The dataset tab commonly is *not* open when charting from the project
        tree; that simply means there is no selection to honour, so an empty
        list is the expected result rather than an error.
        """
        from pandaplot.gui.components.tabs.tab_container import TabContainer

        if not dataset_id:
            return []
        try:
            tab_container = self.app_context.get_manager(TabContainer)
            dataset_tab = tab_container.get_tab_widget(dataset_id)
            if dataset_tab is None:
                return []
            table_view = getattr(dataset_tab, "table_view", None)
            if table_view is None:
                return []
            return table_view.get_selected_column_ids()
        except Exception as e:
            self.logger.warning(
                "Could not read the current column selection for dataset %s: %s", dataset_id, e)
            return []

    def create_chart_from_dataset(self):
        """Create a chart from the selected dataset."""
        selected_item = self.get_current_item()
        if not selected_item:
            return

        # Get dataset information
        item_data = selected_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data or item_data.get("type") != "dataset":
            return

        dataset_id = item_data.get("id")

        command = CreateChartFromWizardCommand(
            self.app_context,
            dataset_id=dataset_id,
            preselected_column_ids=self._preselected_column_ids(dataset_id),
        )
        self.app_context.get_command_executor().execute_command(command)

    def rename_selected_item(self):
        """Rename the selected item.

        The project root has no `Item` to inline-edit, so it is renamed
        through a dialog and a dedicated command instead.
        """
        selected_info = self.get_selected_item_info()
        if not selected_info:
            return

        if selected_info["type"] == "project":
            self.rename_project()
            return

        # Start inline editing on the current item
        current_item = selected_info["item"]
        if current_item:
            # Start editing the first column (name)
            self.edit_item(current_item, 0)

    def rename_project(self):
        """Prompt for a new project name and execute the rename."""
        if not self.app_state.has_project or not self.app_state.current_project:
            return

        project = self.app_state.current_project
        new_name, ok = QInputDialog.getText(
            self.parent_widget, "Rename Project", "New project name:", text=project.name)
        if not ok:
            return
        command = RenameProjectCommand(self.app_context, new_name)
        self.app_context.get_command_executor().execute_command(command)

    def delete_selected_item(self):
        """Delete the selected item."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info["type"] == "project":
            return

        item_id = selected_info["id"]
        command = DeleteItemCommand(self.app_context, item_id)
        self.app_context.get_command_executor().execute_command(command)

    def open_selected_item(self):
        """Open the selected item."""
        current_item = self.get_current_item()
        if not current_item:
            return

        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        item_type = item_data.get("type", "")
        item_id = item_data.get("id", "")

        # Handle different item types
        if item_type == "folder":
            # Toggle folder expansion
            current_item.setExpanded(not current_item.isExpanded())
        else:
            item = item_data.get("data")
            item_name = item.name if item else "Unnamed Item"

            if self.app_state:
                self.app_state.event_bus.emit(UIEvents.TAB_OPEN_REQUESTED, TabOpenRequestedData(
                    item_id=item_id,
                    item_name=item_name
                ).to_dict())

    def on_item_double_clicked(self, item, column):
        """Handle double-click on tree item."""
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if item_data:
            item_type = item_data.get("type", "")

            # For folders, toggle expansion
            if item_type == "folder":
                item.setExpanded(not item.isExpanded())
            # Image galleries (and nested albums) open their grid-view tab
            # rather than merely expanding, since that's how you browse them.
            elif item_type == "imagegallery":
                self.open_selected_item()
                return
            # Images have no standalone tab; open their parent gallery instead.
            elif item_type == "image":
                self._open_parent_gallery(item_data)
                return
            # For other items that can be opened, don't start editing
            elif item_type in ["note", "dataset", "chart", "sketch"]:
                self.open_selected_item()
                return

        # For project root or items without actions, do nothing
        # Inline editing is triggered by single click when item is selected

    def _open_parent_gallery(self, item_data):
        """Open the tab for an Image's parent ImageGallery (images have no own tab)."""
        image = item_data.get("data")
        if image is None or not image.parent_id:
            return

        project = self.app_state.current_project
        if not project:
            return

        gallery = project.find_item(image.parent_id)
        if gallery is None:
            return

        self.app_state.event_bus.emit(UIEvents.TAB_OPEN_REQUESTED, TabOpenRequestedData(
            item_id=gallery.id,
            item_name=gallery.name
        ).to_dict())
