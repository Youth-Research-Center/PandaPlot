"""Command-dispatch collaborator for TabContainer.

Translates UI-level requests from the welcome tab and dataset tabs into
project/chart commands, keeping TabContainer itself focused on pane/tab-widget
lifecycle management rather than also knowing how to build and execute
commands. Mirrors the existing ProjectPanelCommandManager pattern
(pandaplot/gui/components/sidebar/project/project_command_manager.py).
"""
import logging

from PySide6.QtWidgets import QWidget

from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.commands.project.dataset import AnalyzeMeasurementsCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.commands.project.project import LoadProjectCommand, NewProjectCommand, OpenProjectCommand
from pandaplot.models.events.event_data import TabOpenRequestedData
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.examples import example_start_item


class TabContainerCommandManager:
    def __init__(self, app_context: AppContext):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context

    def handle_new_project(self):
        """Handle new project request from welcome tab."""
        command = NewProjectCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def handle_open_project(self):
        """Handle open project request from welcome tab."""
        command = OpenProjectCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def handle_recent_project(self, project_path: str):
        """Handle recent project selection from welcome tab."""
        command = LoadProjectCommand(self.app_context, project_path)
        self.app_context.get_command_executor().execute_command(command)

    def handle_example_project(self, project_path: str):
        """Handle example project selection from welcome tab (opens an untitled copy)."""
        # on_loaded runs after a successful load. Redo of a kept load swaps the project back without calling it, so it does
        # not re-open UI; only a redo that has to load the file again (the loaded project was dropped) opens the start item again.
        command = LoadProjectCommand(self.app_context, project_path, as_untitled_copy=True, on_loaded=self._open_example_start_item)
        self.app_context.get_command_executor().execute_command(command)

    def _open_example_start_item(self, project: Project) -> None:
        """Open the freshly loaded example's start note (or first featured chart) in a tab.

        Args:
            project: The example project that was just loaded.
        """
        item = example_start_item(project)
        if item is None:
            return
        self.app_context.get_event_bus().emit(
            UIEvents.TAB_OPEN_REQUESTED, TabOpenRequestedData(item_id=item.id, item_name=item.name).to_dict()
        )

    def handle_import_data(self):
        """Handle import data request from welcome tab."""
        # Import data requires a project to be loaded first
        if not self.app_context.get_app_state().has_project:
            # Create a new project first
            self.handle_new_project()

        # Show file dialog for data import (CSV or single-sheet Excel)
        from pandaplot.commands.project.dataset.import_data_command import (
            ImportDataCommand,
        )
        command = ImportDataCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def handle_create_dataset(self):
        """Handle create-dataset request from the welcome tab's Explore Data dialog."""
        # Creating a dataset requires a project to be loaded first
        if not self.app_context.get_app_state().has_project:
            self.handle_new_project()

        command = CreateEmptyDatasetCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def handle_create_chart(self):
        """Handle create-chart request from the welcome tab's Create
        Visualizations dialog.

        Unlike handle_import_data/handle_create_dataset, this doesn't create
        a project first: CreateChartFromWizardCommand already offers to
        create one itself (ensure_project_or_offer_create) if none is open,
        matching MainMenu's "Chart > Create New" entry point.
        """
        command = CreateChartFromWizardCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def create_chart_from_dataset(self, dataset_id: str, preselected_column_ids: list[str] | None = None):
        """Open the chart creation wizard for a dataset.

        The wizard is non-blocking, so no chart exists when this returns. The
        resulting chart's tab is opened by TabContainer's
        `ChartEvents.CHART_CREATED` subscription once the user finishes.
        """
        app_state = self.app_context.get_app_state()
        if app_state.has_project and app_state.current_project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return

        project = app_state.current_project
        if project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return
        dataset_item = project.find_item(dataset_id)
        if not dataset_item:
            self.logger.warning("Cannot create chart: Dataset %s not found", dataset_id)
            return

        command = CreateChartFromWizardCommand(
            self.app_context,
            dataset_id=dataset_id,
            preselected_column_ids=preselected_column_ids or [],
        )
        self.app_context.get_command_executor().execute_command(command)

    def analyze_measurements_for_dataset(
        self,
        dataset_id: str,
        *,
        parent_widget: QWidget | None = None,
    ) -> None:
        """Open measurement analysis and execute it if the wizard is accepted."""
        app_state = self.app_context.get_app_state()
        project = app_state.current_project
        dataset = project.find_item(dataset_id) if project is not None else None
        if not isinstance(dataset, Dataset):
            self.logger.warning("Cannot analyze measurements: Dataset %s not found", dataset_id)
            return

        from PySide6.QtWidgets import QDialog

        from pandaplot.gui.dialogs.measurement_analysis_wizard import MeasurementAnalysisWizard

        self.app_context.get_ui_controller().set_parent_widget(parent_widget)
        wizard = MeasurementAnalysisWizard(self.app_context, dataset, parent=parent_widget)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return

        command = AnalyzeMeasurementsCommand(
            self.app_context,
            dataset.id,
            wizard.selected_roles(),
            measurement_groups=wizard.selected_measurement_groups(),
            result_name=wizard.result_name(),
        )
        executor = self.app_context.get_command_executor()
        executor.execute_command(command)
        if wizard.plot_requested() and command.result_dataset_id is not None:
            self.create_chart_from_dataset(command.result_dataset_id)
