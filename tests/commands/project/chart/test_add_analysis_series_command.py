"""Tests for AddAnalysisSeriesCommand and quick-plot composition."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import AnalysisType, SignalAnalysisResult, SignalAnalysisType
from pandaplot.commands import CommandExecutor, CompositeCommand
from pandaplot.commands.project.chart import AddAnalysisSeriesCommand
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")

    # Folder
    folder = Folder(id="f-1", name="F")
    project.add_item(folder)

    # Source dataset in folder
    t = np.linspace(0.0, 10.0, 101)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "y": t ** 2}))
    project.add_item(dataset, parent_id="f-1")

    # Chart in folder
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


class TestAddAnalysisSeriesCommand:
    def test_add_analysis_series_with_analyze_command(self, ctx):
        app_context, project, chart = ctx
        executor = CommandExecutor(app_context)

        analyze_cmd = AnalyzeChartSeriesCommand(
            app_context,
            chart_id="chart-1",
            source_kind="series",
            source_index=0,
            analysis_type=AnalysisType.DERIVATIVE,
            folder_id=chart.parent_id,
        )
        add_series_cmd = AddAnalysisSeriesCommand(
            app_context,
            chart_id="chart-1",
            dataset_command=analyze_cmd,
        )
        composite = CompositeCommand([analyze_cmd, add_series_cmd])

        assert executor.execute_command(composite) is True

        # Dataset created in chart's folder
        dataset = project.find_item(analyze_cmd.result_dataset_id)
        assert dataset is not None
        assert dataset.parent_id == "f-1"

        # Series added to chart
        assert len(chart.data_series) == 2
        new_series = chart.data_series[1]
        assert new_series.dataset_id == dataset.id
        assert new_series.x_column == dataset.data.columns[0]
        assert new_series.y_column == dataset.data.columns[1]

        # Test Undo
        assert executor.undo() is True
        assert len(chart.data_series) == 1
        assert project.find_item(dataset.id) is None

        # Test Redo
        assert executor.redo() is True
        assert len(chart.data_series) == 2
        assert project.find_item(dataset.id) is not None

    def test_series_type_falls_back_to_scatter_when_line_not_allowed(self, ctx):
        """A Bar chart allows SCATTER but not LINE -- the plotted series
        must actually be a SCATTER, not silently fall through to the
        chart's default_series_type (BAR), which would render each
        analysis result point as its own bar."""
        app_context, project, chart = ctx
        chart.chart_type = ChartType.BAR
        executor = CommandExecutor(app_context)

        analyze_cmd = AnalyzeChartSeriesCommand(
            app_context,
            chart_id="chart-1",
            source_kind="series",
            source_index=0,
            analysis_type=AnalysisType.DERIVATIVE,
            folder_id=chart.parent_id,
        )
        add_series_cmd = AddAnalysisSeriesCommand(
            app_context,
            chart_id="chart-1",
            dataset_command=analyze_cmd,
        )
        composite = CompositeCommand([analyze_cmd, add_series_cmd])

        assert executor.execute_command(composite) is True

        assert chart.data_series[1].series_type == SeriesType.SCATTER

    def test_add_analysis_series_with_signal_apply_command(self, ctx):
        app_context, project, chart = ctx
        executor = CommandExecutor(app_context)

        result_df = pd.DataFrame({"Index": [10, 20], "Value": [1.5, 2.5]})
        signal_result = SignalAnalysisResult(
            analysis_type=SignalAnalysisType.PEAKS,
            analysis_name="Peak Detection",
            source_columns=["y"],
            data=result_df,
        )

        apply_cmd = ApplySignalAnalysisResultCommand(
            app_context,
            result_name="Peaks Result",
            folder_id=chart.parent_id,
            result=signal_result,
        )
        add_series_cmd = AddAnalysisSeriesCommand(
            app_context,
            chart_id="chart-1",
            dataset_command=apply_cmd,
        )
        composite = CompositeCommand([apply_cmd, add_series_cmd])

        assert executor.execute_command(composite) is True

        dataset = project.find_item(apply_cmd.result_dataset_id)
        assert dataset is not None
        assert dataset.parent_id == "f-1"

        assert len(chart.data_series) == 2
        new_series = chart.data_series[1]
        assert new_series.dataset_id == dataset.id
        assert new_series.x_column == "Index"
        assert new_series.y_column == "Value"

        # Undo/Redo round trip
        assert executor.undo() is True
        assert len(chart.data_series) == 1
        assert project.find_item(dataset.id) is None

        assert executor.redo() is True
        assert len(chart.data_series) == 2
        assert project.find_item(dataset.id) is not None
