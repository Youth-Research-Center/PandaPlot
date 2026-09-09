"""Tests for ChartAnalysisPanel segment index -> (x, y) preview labels."""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart import AddAnalysisSeriesCommand, CreateChartWithAnalysisSeriesCommand
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.gui.components.sidebar.chart_analysis.chart_analysis_panel import (
    ChartAnalysisPanel,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def project():
    project = Project(name="P")
    t = np.linspace(0.0, 10.0, 101)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("sq")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="sq", label="Squared")
    project.add_item(chart)
    return project


@pytest.fixture
def app_context(project):
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    ctx.get_app_state.return_value = app_state
    return ctx


@pytest.fixture
def panel(app_context, project):
    panel = ChartAnalysisPanel(app_context)
    panel.current_chart = project.find_item("chart-1")
    panel.current_chart_id = "chart-1"
    panel._populate_sources()
    return panel


class TestChartAnalysisPanelRangeLabels:
    def test_labels_show_no_selection_placeholder_without_source(self, app_context):
        panel = ChartAnalysisPanel(app_context)

        assert panel.start_value_label.text() == "–"
        assert panel.end_value_label.text() == "–"

    def test_start_label_updates_on_index_change(self, panel):
        panel.start_index.setValue(10)

        assert panel.start_value_label.text() == "x=1, y=1"

    def test_end_index_defaults_to_the_last_point(self, panel):
        assert panel.end_index.minimum() == 0
        assert panel.end_index.value() == 100
        assert panel.end_value_label.text() == "x=10, y=100"

    def test_end_label_updates_on_explicit_index(self, panel):
        panel.end_index.setValue(50)

        assert panel.end_value_label.text() == "x=5, y=25"

    def test_end_index_shrinks_the_segment_when_decreased(self, panel):
        panel.end_index.setValue(panel.end_index.value() - 1)

        assert panel.end_value_label.text() == "x=9.9, y=98.01"

    def test_build_parameters_sends_inclusive_end_as_exclusive_boundary(self, panel):
        panel.start_index.setValue(0)
        panel.end_index.setValue(50)

        assert panel._build_parameters()["end_index"] == 51


class TestChartAnalysisPanelSeriesFiltering:
    """Regression (#202): derivative/integral/arc-length/smoothing/
    interpolation assume a single ordered (x, y) curve -- meaningless for
    bar/hist/vector/colormap/heatmap/3-D series, so the source picker must
    leave them off entirely rather than letting them produce nonsense."""

    def _combo_labels(self, panel):
        return [panel.source_combo.itemText(i) for i in range(panel.source_combo.count())]

    def test_bar_series_is_excluded_from_the_source_picker(self, panel):
        panel.current_chart.data_series[0].series_type = SeriesType.BAR
        panel._populate_sources()

        assert self._combo_labels(panel) == []
        assert panel.apply_btn.isEnabled() is False

    def test_line_and_scatter_series_are_offered(self, panel):
        assert any("Squared" in label for label in self._combo_labels(panel))

    def test_fit_curves_are_offered_even_when_every_series_is_excluded(self, panel):
        panel.current_chart.data_series[0].series_type = SeriesType.HEATMAP
        panel.current_chart.add_fit_data(
            source_dataset_id="ds-1", fit_type="linear",
            x_data=[1.0, 2.0, 3.0], y_data=[1.0, 2.0, 3.0], label="Fit 1",
        )

        panel._populate_sources()

        labels = self._combo_labels(panel)
        assert any("Fit 1" in label for label in labels)
        assert len(labels) == 1

    def test_hint_flags_excluded_series_when_other_sources_remain(self, panel):
        panel.current_chart.add_data_series(
            dataset_id="ds-1", label="Counts", series_type=SeriesType.HIST,
        )

        panel._populate_sources()

        assert "aren't shown" in panel.source_hint.text()
        assert any("Squared" in label for label in self._combo_labels(panel))

    def test_hint_explains_when_every_series_is_excluded(self, panel):
        panel.current_chart.data_series[0].series_type = SeriesType.VECTOR

        panel._populate_sources()

        assert self._combo_labels(panel) == []
        assert "aren't supported here" in panel.source_hint.text()


class TestChartAnalysisPanelSeriesSelectedEvent:
    """Clicking a series/fit on the chart canvas or its legend (#341, #107)
    should also select it here, so switching to "analyze it" doesn't
    require re-finding the same entry in this combo."""

    def test_series_click_selects_matching_combo_row(self, panel):
        panel.current_chart.add_data_series(
            dataset_id="ds-1", label="Second", series_type=SeriesType.LINE,
        )
        panel._populate_sources()
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "series", "index": 1}
        )

        assert panel.source_combo.currentData() == ("series", 1)

    def test_fit_click_selects_matching_combo_row(self, panel):
        panel.current_chart.add_fit_data(
            source_dataset_id="ds-1", fit_type="linear",
            x_data=[1.0, 2.0, 3.0], y_data=[1.0, 2.0, 3.0], label="Fit 1",
        )
        panel._populate_sources()
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "fit", "index": 0}
        )

        assert panel.source_combo.currentData() == ("fit", 0)

    def test_ignores_event_for_a_different_chart(self, panel):
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "some-other-chart", "kind": "series", "index": 0}
        )

        assert panel.source_combo.currentIndex() == 0

    def test_ignores_selection_of_a_series_excluded_from_this_combo(self, panel):
        """A click on a bar/hist/vector/... series has no matching combo
        row (see TestChartAnalysisPanelSeriesFiltering) -- must not raise
        or change the current selection."""
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "series", "index": 5}
        )

        assert panel.source_combo.currentIndex() == 0


class TestChartAnalysisPanelQuickPlot:
    def test_quick_plot_checkbox_is_present_and_checked_by_default(self, panel):
        assert hasattr(panel, "plot_result_cb")
        assert panel.plot_result_cb.text() == "Plot result"
        assert panel.plot_result_cb.isChecked() is True
        assert panel.plot_result_cb.isEnabled() is True

    def test_destination_combo_defaults_to_new_chart(self, panel):
        assert panel.plot_target_combo.itemText(0) == "➕ New chart"
        assert panel.plot_target_combo.currentData() is None

    def test_plot_target_row_hides_when_checkbox_unchecked(self, panel):
        assert panel.plot_target_row.isVisibleTo(panel) is True
        panel.plot_result_cb.setChecked(False)
        assert panel.plot_target_row.isVisibleTo(panel) is False

    def test_quick_plot_stays_enabled_for_3d_charts(self, panel):
        """A 3-D current chart has no valid LINE/SCATTER series type of its
        own, but "New chart" is always a valid destination -- the checkbox
        no longer needs to disable itself based on the current chart's
        type at all (see the design spec's "enablement no longer depends
        on the current chart" section)."""
        panel.current_chart.chart_type = ChartType.SCATTER3D
        panel._populate_sources()

        assert panel.plot_result_cb.isEnabled() is True

    def test_3d_current_chart_is_excluded_from_the_destination_combo(self, panel):
        panel.current_chart.chart_type = ChartType.SCATTER3D
        panel._populate_sources()

        labels = [panel.plot_target_combo.itemText(i) for i in range(panel.plot_target_combo.count())]
        assert labels == ["➕ New chart"]

    def test_compatible_other_chart_is_offered_in_the_destination_combo(self, panel, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()

        labels = [panel.plot_target_combo.itemText(i) for i in range(panel.plot_target_combo.count())]
        assert "Other" in labels

    def test_apply_creates_a_new_chart_when_new_chart_is_selected(self, panel, app_context):
        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.apply()

        assert executor.execute_command.called
        cmd = executor.execute_command.call_args[0][0]
        assert isinstance(cmd, CompositeCommand)
        assert len(cmd.commands) == 2
        assert isinstance(cmd.commands[0], AnalyzeChartSeriesCommand)
        assert isinstance(cmd.commands[1], CreateChartWithAnalysisSeriesCommand)

    def test_apply_plots_on_the_selected_existing_chart(self, panel, app_context, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.apply()

        cmd = executor.execute_command.call_args[0][0]
        assert isinstance(cmd, CompositeCommand)
        add_series_cmd = cmd.commands[1]
        assert isinstance(add_series_cmd, AddAnalysisSeriesCommand)
        assert add_series_cmd.chart_id == "chart-2"

    def test_destination_combo_refreshes_when_a_different_chart_is_renamed(self, panel, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        other_chart.name = "Renamed"
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.plot_target_combo.currentData() == "chart-2"
        assert panel.plot_target_combo.currentText() == "Renamed"

    def test_chart_updated_with_only_chart_id_refreshes_destination_combo_for_a_different_chart(
        self, panel, project
    ):
        """ChartPropertiesPanel's live-edit publish (e.g. retyping a chart
        via the Properties panel) sends only chart_id, not the Chart object
        itself -- must still resolve it from the project so a different
        chart's retype is reflected in the destination combo."""
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        other_chart.chart_type = ChartType.HIST  # retyped to an incompatible type
        panel._on_chart_updated({"chart_id": "chart-2", "update_type": "config_updated"})

        assert panel.plot_target_combo.currentData() is None

    def test_chart_updated_with_only_chart_id_still_refreshes_the_current_chart(self, panel):
        """Same chart_id-only payload shape, but for the panel's own
        current chart -- must still trigger the normal refresh path."""
        calls = []
        original = panel._populate_sources

        def _spy():
            calls.append(1)
            original()

        panel._populate_sources = _spy

        panel._on_chart_updated({"chart_id": "chart-1", "update_type": "config_updated"})

        assert calls == [1]

    def test_destination_combo_refreshes_when_a_different_chart_is_moved(self, panel, project):
        from pandaplot.models.project.items.folder import Folder
        source_folder = Folder(id="f-src", name="Src")
        project.add_item(source_folder)
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart, parent_id="f-src")
        # A same-named sibling elsewhere forces disambiguated_display_options
        # to suffix both charts' labels with their folder path -- without a
        # collision, neither label would ever include a path that could go
        # stale, and this test wouldn't actually exercise the bug.
        colliding_chart = Chart(id="chart-3", name="Other", chart_type=ChartType.LINE)
        project.add_item(colliding_chart)

        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)
        assert "Src" in panel.plot_target_combo.currentText()

        dest_folder = Folder(id="f-dest", name="Dest")
        project.add_item(dest_folder)
        project.remove_item(other_chart)
        project.add_item(other_chart, parent_id="f-dest")
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.plot_target_combo.currentData() == "chart-2"
        assert "Dest" in panel.plot_target_combo.currentText()
        assert "Src" not in panel.plot_target_combo.currentText()

    def test_destination_combo_falls_back_to_new_chart_when_selected_destination_is_removed(self, panel, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        project.remove_item_by_id("chart-2")
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.plot_target_combo.currentData() is None

    def test_apply_executes_single_command_when_quick_plot_unchecked(self, panel, app_context):
        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.plot_result_cb.setChecked(False)
        panel.apply()

        assert executor.execute_command.called
        cmd = executor.execute_command.call_args[0][0]
        assert isinstance(cmd, AnalyzeChartSeriesCommand)
