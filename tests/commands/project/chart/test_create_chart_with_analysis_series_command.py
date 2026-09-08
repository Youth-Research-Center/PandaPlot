"""Tests for CreateChartWithAnalysisSeriesCommand and build_quick_plot_command."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import AnalysisType
from pandaplot.commands import CommandExecutor, CompositeCommand
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart import AddAnalysisSeriesCommand, CreateChartWithAnalysisSeriesCommand
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.commands.project.chart.create_chart_with_analysis_series_command import (
    build_quick_plot_command,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")

    folder = Folder(id="f-1", name="F")
    project.add_item(folder)

    t = np.linspace(0.0, 10.0, 101)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "y": t ** 2}))
    project.add_item(dataset, parent_id="f-1")

    chart = Chart(id="chart-1", name="C")
    chart.parent_id = "f-1"
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("y")
    chart.add_data_series(
        dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id, x_column="t", y_column="y", label="y"
    )
    project.add_item(chart, parent_id="f-1")

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.event_bus = app_state.event_bus
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    return app_context, project, chart


def _analyze_cmd(app_context, chart):
    return AnalyzeChartSeriesCommand(
        app_context,
        chart_id="chart-1",
        source_kind="series",
        source_index=0,
        analysis_type=AnalysisType.DERIVATIVE,
        folder_id=chart.parent_id,
    )


class TestCreateChartWithAnalysisSeriesCommand:
    def test_creates_a_new_line_chart_and_plots_the_result(self, ctx):
        app_context, project, chart = ctx
        executor = CommandExecutor(app_context)

        analyze_cmd = _analyze_cmd(app_context, chart)
        create_cmd = CreateChartWithAnalysisSeriesCommand(
            app_context, folder_id=chart.parent_id, dataset_command=analyze_cmd,
        )
        composite = CompositeCommand([analyze_cmd, create_cmd])

        assert executor.execute_command(composite) is True

        dataset = project.find_item(analyze_cmd.result_dataset_id)
        assert dataset is not None

        new_chart = project.find_item(create_cmd.created_chart_id)
        assert new_chart is not None
        assert new_chart.id != "chart-1"
        assert new_chart.parent_id == "f-1"
        assert new_chart.chart_type == ChartType.LINE
        # unique_sibling_name sees the just-created dataset as an existing
        # sibling with the same base name, so the chart is deduped to "(2)".
        assert new_chart.name == f"{dataset.name} (2)"
        assert len(new_chart.data_series) == 1
        assert new_chart.data_series[0].dataset_id == dataset.id

        # The original chart is untouched.
        assert len(chart.data_series) == 1

    def test_undo_redo_removes_and_restores_dataset_chart_and_series(self, ctx):
        app_context, project, chart = ctx
        executor = CommandExecutor(app_context)

        analyze_cmd = _analyze_cmd(app_context, chart)
        create_cmd = CreateChartWithAnalysisSeriesCommand(
            app_context, folder_id=chart.parent_id, dataset_command=analyze_cmd,
        )
        composite = CompositeCommand([analyze_cmd, create_cmd])
        executor.execute_command(composite)

        dataset_id = analyze_cmd.result_dataset_id
        new_chart_id = create_cmd.created_chart_id

        assert executor.undo() is True
        assert project.find_item(dataset_id) is None
        assert project.find_item(new_chart_id) is None

        assert executor.redo() is True
        assert project.find_item(dataset_id) is not None
        restored_chart = project.find_item(new_chart_id)
        assert restored_chart is not None
        assert len(restored_chart.data_series) == 1

    def test_fails_when_dataset_command_never_produced_a_dataset(self, ctx):
        app_context, project, chart = ctx
        dataset_command = Mock()
        dataset_command.result_dataset_id = None

        command = CreateChartWithAnalysisSeriesCommand(
            app_context, folder_id=chart.parent_id, dataset_command=dataset_command,
        )

        assert command.execute() is CommandResult.FAILURE
        assert command.created_chart_id is None


class TestBuildQuickPlotCommand:
    def test_none_target_builds_create_chart_command(self, ctx):
        app_context, _project, chart = ctx
        analyze_cmd = _analyze_cmd(app_context, chart)

        command = build_quick_plot_command(
            app_context, analyze_cmd, target_chart_id=None, folder_id=chart.parent_id,
        )

        assert isinstance(command, CreateChartWithAnalysisSeriesCommand)
        assert command.folder_id == chart.parent_id
        assert command.dataset_command is analyze_cmd

    def test_existing_chart_id_builds_add_analysis_series_command(self, ctx):
        app_context, _project, chart = ctx
        analyze_cmd = _analyze_cmd(app_context, chart)

        command = build_quick_plot_command(
            app_context, analyze_cmd, target_chart_id="chart-1", folder_id=chart.parent_id,
        )

        assert isinstance(command, AddAnalysisSeriesCommand)
        assert command.chart_id == "chart-1"
        assert command.dataset_command is analyze_cmd
