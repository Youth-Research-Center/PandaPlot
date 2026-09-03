"""Command-dispatch collaborator for TabContainer.

Translates UI-level requests from the welcome tab and dataset tabs into
project/chart commands, keeping TabContainer itself focused on pane/tab-widget
lifecycle management rather than also knowing how to build and execute
commands. Mirrors the existing ProjectPanelCommandManager pattern
(pandaplot/gui/components/sidebar/project/project_command_manager.py).
"""
import logging
from typing import Optional

from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.commands.project.project import LoadProjectCommand, NewProjectCommand, OpenProjectCommand
from pandaplot.models.state.app_context import AppContext


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
        """Handle example project selection from welcome tab."""
        command = LoadProjectCommand(self.app_context, project_path)
        self.app_context.get_command_executor().execute_command(command)

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

    def create_chart_from_dataset(self, dataset_id: str, preselected_column_ids: Optional[list[str]] = None):
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
