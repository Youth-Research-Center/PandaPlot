import os
import uuid
from dataclasses import replace
from typing import Any, Callable, List, Optional, Tuple, override

import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.dataset.add_imported_datasets_command import AddImportedDatasetsCommand
from pandaplot.commands.project.require_project import ensure_project_or_offer_create
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.data_import import ImportOptions, data_importer
from pandaplot.services.data_import.data_importer import (
    EXCEL_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
)
from pandaplot.services.qtasks import TaskScheduler


class ImportDataCommand(Command):
    """
    Command to import a data file (CSV/TSV, or one or more sheets of an Excel
    workbook) as dataset(s) in the project, via one unified "Import Data" action.

    The command drives the interactive import wizard
    (:class:`ImportWizardDialog`), which handles format detection, parse
    options, and preview. Once the user confirms, the full file is read on a
    background thread using the chosen :class:`ImportOptions`.

    This command itself never occupies an undo slot (see
    occupies_undo_slot()) -- execute() only dispatches the background read.
    Once the read completes, its own result callback constructs and executes
    an :class:`AddImportedDatasetsCommand`, which is what actually lands on
    the undo stack.
    """

    def __init__(self, app_context: AppContext, folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler: TaskScheduler = app_context.get_task_scheduler()

        self.folder_id = folder_id
        self.file_path = None  # Path to the data file, can be set later
        self.dataset_name = None
        # Parse options chosen in the wizard; drives the background read.
        self.import_options: Optional[ImportOptions] = None
        # Excel worksheets to import, in workbook order, as chosen in the
        # wizard. None for CSV/TSV/JSON or until the wizard has run.
        self.selected_sheets: Optional[List[str]] = None

        # Datasets read by the background task, kept alive for
        # test/introspection purposes; the real, undo-tracked effect of
        # adding them to the project happens via AddImportedDatasetsCommand
        # (see _on_import_result and occupies_undo_slot()).
        self.imported_datasets: List[Dataset] = []
        self.project = None

        # Task state
        self.is_importing = False

    @override
    def occupies_undo_slot(self) -> bool:
        """This command only dispatches the background read; the real,
        undoable effect is AddImportedDatasetsCommand, executed separately
        once the read completes (see _on_import_result). Exempting this
        command from the stacks fixes #301: an Undo triggered while the
        import is still running used to pop this command off undo_stack
        (and onto redo_stack) despite nothing having actually happened yet,
        since its own undo() found dataset_ids still empty."""
        return False

    @override
    def execute(self) -> CommandResult:
        """Execute the import data command."""
        try:
            self.logger.info("Executing ImportDataCommand")

            # Prevent concurrent imports
            if self.is_importing:
                self.logger.warning("Import operation already in progress")
                self.ui_controller.show_info_message("Import In Progress", "A data import is already in progress.")
                return CommandResult.FAILURE

            # Check if we have a project loaded
            if not self.app_state.has_project or not self.app_state.current_project:
                self.logger.warning("ImportDataCommand.execute: no project is currently loaded")
                if not ensure_project_or_offer_create(
                    self.app_context, "Import Data",
                    "Importing data requires a project. Create a new project to continue?",
                ):
                    return CommandResult.FAILURE

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning("ImportDataCommand.execute: has_project is True but current_project is None")
                return CommandResult.FAILURE

            # Collect the file, parse options, and dataset name via the wizard.
            if not self._collect_import_settings():
                return CommandResult.FAILURE  # User cancelled

            # Preflight check: validate file still exists before starting import
            if not self.file_path or not os.path.exists(self.file_path):
                error_msg = f"Selected file does not exist: {self.file_path}"
                self.ui_controller.show_error_message("Import Data Error", error_msg)
                self.logger.error(error_msg)
                return CommandResult.FAILURE

            # Preflight check: validate the file extension is supported
            extension = os.path.splitext(self.file_path)[1].lower()
            if extension not in SUPPORTED_EXTENSIONS:
                supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
                error_msg = f"Unsupported file type '{extension}'. Supported types: {supported}"
                self.ui_controller.show_error_message("Import Data Error", error_msg)
                self.logger.error(error_msg)
                return CommandResult.FAILURE

            # Start background import operation
            self.is_importing = True

            # Run import in background thread
            self.task_scheduler.run_task(
                task=self._import_data_task,
                task_arguments={},
                on_result=self._on_import_result,
                on_error=self._on_import_error,
                on_finished=self._on_import_finished,
                on_progress=self._on_import_progress,
            )

            return CommandResult.SUCCESS  # Command initiated successfully

        except Exception as e:
            error_msg = f"Failed to initiate data import: {e}"
            self.logger.error("ImportDataCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Import Data Error", error_msg)
            self.is_importing = False  # Reset flag on error
            return CommandResult.FAILURE

    def _collect_import_settings(self) -> bool:
        """
        Show the import wizard and capture the chosen file, parse options, and
        dataset name. Returns False if the user cancels.

        When `self.file_path` is already set (e.g. programmatic import), it
        seeds the wizard so tests and callers can pre-select a file.
        """
        # Imported lazily to keep the wizard dialog (and its widgets) off the
        # startup import path; it is only needed when an import actually runs.
        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.import_wizard_dialog import ImportWizardDialog

        dialog = ImportWizardDialog(
            self.app_context,
            parent=self.ui_controller.parent_widget,
            initial_file_path=self.file_path,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.logger.info("Import wizard cancelled by user")
            return False

        self.file_path = dialog.get_file_path()
        self.import_options = dialog.get_import_options()
        self.dataset_name = dialog.get_dataset_name()
        # Excel workbooks may import several sheets at once, each as its own
        # dataset; empty for other formats. None lets redo() re-run cleanly.
        self.selected_sheets = dialog.get_selected_sheets() or None
        return True

    def _read_frames(self) -> List[Tuple[str, pd.DataFrame]]:
        """
        Read the file into (dataset_name, dataframe) pairs, honoring the parse
        options chosen in the wizard. Excel workbooks yield one pair per
        selected sheet; other formats yield a single pair.

        A lone sheet is named after the file (matching CSV behaviour); multiple
        sheets are suffixed with " - <sheet>" so their datasets stay distinct.
        """
        assert self.file_path is not None
        options = self.import_options or data_importer.default_options(self.file_path)
        base_name = self.dataset_name or os.path.splitext(os.path.basename(self.file_path))[0]

        extension = os.path.splitext(self.file_path)[1].lower()
        if extension in EXCEL_EXTENSIONS:
            sheets = self.selected_sheets or [options.sheet_name]
            frames = []
            for sheet in sheets:
                df = data_importer.read_dataframe(self.file_path, replace(options, sheet_name=sheet))
                name = base_name if len(sheets) == 1 else f"{base_name} - {sheet}"
                frames.append((name, df))
            return frames

        return [(base_name, data_importer.read_dataframe(self.file_path, options))]

    def _import_data_task(self, progress_callback: Callable[[float], None], **kwargs) -> dict:
        """
        Import task function to be run in a background thread.
        Returns a dictionary with success status and any error message.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            dict: {'success': bool, 'error': str or None, 'datasets': List[Dataset], 'file_path': str or None}
        """
        self.logger.debug("Starting data import task")
        try:
            if progress_callback:
                progress_callback(0.1)  # Starting import

            if not self.file_path or not os.path.exists(self.file_path):
                return {"success": False, "error": f"File not found: {self.file_path}", "datasets": []}

            if progress_callback:
                progress_callback(0.2)  # File validation complete

            # Read the data file into one or more (name, dataframe) pairs
            try:
                frames = self._read_frames()
            except Exception as e:
                return {"success": False, "error": f"Failed to read file: {str(e)}", "datasets": []}

            if progress_callback:
                progress_callback(0.6)  # File read successfully

            # Drop empty sheets rather than failing the whole import over one blank tab
            non_empty = [(name, df) for name, df in frames if not df.empty]
            if not non_empty:
                error_msg = "The selected file is empty." if len(frames) == 1 else "The selected sheet(s) contain no data."
                return {"success": False, "error": error_msg, "datasets": []}

            datasets = []
            for name, df in non_empty:
                dataset = Dataset(id=str(uuid.uuid4()), name=name, data=df, source_file=self.file_path)
                datasets.append(dataset)

            if progress_callback:
                progress_callback(0.9)  # Dataset objects created

            self.logger.info(
                "Successfully imported %d dataset(s) from '%s' (%s)",
                len(datasets),
                self.file_path,
                ", ".join(f"{d.name} (rows={d.data.shape[0]}, cols={d.data.shape[1]})" for d in datasets),
            )

            if progress_callback:
                progress_callback(1.0)  # Finished

            return {
                "success": True,
                "error": None,
                "datasets": datasets,
                "file_path": self.file_path,
            }

        except Exception as e:
            error_msg = f"Error during data import: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg, "datasets": []}

    def _on_import_result(self, result: dict):
        """Handle successful completion of import task."""
        try:
            self.is_importing = False

            if result.get("success", False):
                datasets: List[Dataset] = result.get("datasets") or []
                file_path = result.get("file_path")

                # Assign on main thread to avoid thread safety issues
                self.imported_datasets = datasets

                if datasets and self.project:
                    # Verify that we still have a project and it's the same as when we started the import
                    if not self.app_state.has_project:
                        # Project was closed during import - abort with user message
                        self.logger.warning("Project was closed during import - aborting import operation")
                        self.ui_controller.show_warning_message(
                            "Import Cancelled",
                            "The project was closed during import. The import has been cancelled."
                        )
                        return

                    current_project = self.app_state.current_project
                    if current_project != self.project:
                        # Project changed during import - abort with user message
                        self.logger.warning("Project changed during import - aborting import operation")
                        self.ui_controller.show_warning_message(
                            "Import Cancelled",
                            "The project was changed during import. The import has been cancelled to prevent data inconsistency."
                        )
                        return

                    # Add the dataset(s) to the project via a separate,
                    # undo-tracked command -- this is the command that
                    # actually lands on the undo stack for this import (see
                    # occupies_undo_slot()).
                    added = self.app_context.get_command_executor().execute_command(
                        AddImportedDatasetsCommand(
                            self.app_context, datasets, folder_id=self.folder_id, file_path=file_path
                        )
                    )
                    if not added:
                        error_msg = "Failed to add imported dataset(s) to project"
                        self.ui_controller.show_error_message("Import Failed", error_msg)
                        self.logger.error(error_msg)
                        return

                    self.logger.info("%d dataset(s) successfully added to project", len(datasets))

                    # Show success message to user
                    if len(datasets) == 1:
                        d = datasets[0]
                        self.ui_controller.show_info_message(
                            "Import Data", f"Successfully imported '{d.name}'\nRows: {d.data.shape[0]}, Columns: {d.data.shape[1]}"
                        )
                    else:
                        names = "\n".join(f"- {d.name} ({d.data.shape[0]} rows, {d.data.shape[1]} cols)" for d in datasets)
                        self.ui_controller.show_info_message(
                            "Import Data", f"Successfully imported {len(datasets)} sheets as datasets:\n{names}"
                        )
                else:
                    error_msg = "Missing datasets or project in import result"
                    self.ui_controller.show_error_message("Import Failed", error_msg)
                    self.logger.error(error_msg)
            else:
                error_msg = result.get("error", "Unknown import error")
                self.ui_controller.show_error_message("Import Failed", error_msg)
                self.logger.error(f"Import failed: {error_msg}")

        except Exception as e:
            self.logger.error(f"Error handling import result: {e}", exc_info=True)
            self.ui_controller.show_error_message("Import Error", f"Error processing import result: {str(e)}")

    def _on_import_error(self, error_info: Tuple[Any, Any, str]):
        """Handle error during import task."""
        try:
            self.is_importing = False
            error_type, error_value, error_traceback = error_info
            error_msg = f"Import failed with {error_type.__name__}: {str(error_value)}"

            self.logger.error(f"Import task error: {error_msg}")
            self.logger.error(f"Traceback: {error_traceback}")

            self.ui_controller.show_error_message("Import Data Error", error_msg)

        except Exception as e:
            self.logger.error(f"Error handling import error: {e}", exc_info=True)

    def _on_import_finished(self):
        """Handle completion of import task (success or failure)."""
        try:
            self.is_importing = False
            self.logger.info("Import task finished")

        except Exception as e:
            self.logger.error(f"Error in import finished handler: {e}", exc_info=True)

    def _on_import_progress(self, progress: float):
        """Handle progress updates from import task."""
        try:
            # Log the progress for now - could update a progress bar if UI supports it
            if progress <= 1.0:
                percentage = int(progress * 100)
                self.logger.debug(f"Import progress: {percentage}%")

        except Exception as e:
            self.logger.error(f"Error handling import progress: {e}", exc_info=True)

    @override
    def undo(self) -> CommandResult:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False, so
        this command is never pushed onto undo_stack/redo_stack, and the
        executor's undo()/redo() only ever act on stack contents. Undoing
        the added dataset(s) is AddImportedDatasetsCommand's job. Kept as a
        no-op only to satisfy the abstract Command interface; SUCCESS is
        reported since "nothing to undo here" is the expected, correct
        outcome."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        """See undo() -- unreachable via CommandExecutor for the same reason."""
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False, so
        this command is never pushed onto a stack for cleanup() to apply to.
        Kept as a documented no-op only to complete the Command interface."""
        return
