"""Tests for ChartTransformPanel."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.commands.base_command import CommandResult
from pandaplot.gui.components.sidebar.chart_transform.chart_transform_panel import (
    ChartTransformPanel,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
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
    t = np.linspace(0.0, 10.0, 11)
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
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    ctx.get_app_state.return_value = app_state
    executor = Mock()
    executor.execute_command.side_effect = lambda cmd: cmd.execute() is CommandResult.SUCCESS
    ctx.get_command_executor.return_value = executor
    return ctx


@pytest.fixture
def panel(app_context, project):
    panel = ChartTransformPanel(app_context)
    panel.current_chart = project.find_item("chart-1")
    panel.current_chart_id = "chart-1"
    panel._populate_sources()
    return panel


class TestChartTransformPanelSourcePicker:
    def _combo_labels(self, panel):
        return [panel.source_combo.itemText(i) for i in range(panel.source_combo.count())]

    def test_line_series_is_offered(self, panel):
        assert any("Squared" in label for label in self._combo_labels(panel))

    def test_bar_series_is_excluded(self, panel):
        panel.current_chart.data_series[0].series_type = SeriesType.BAR
        panel._populate_sources()
        assert self._combo_labels(panel) == []
        assert panel.apply_btn.isEnabled() is False


class TestChartTransformPanelTarget:
    def test_default_target_is_y(self, panel):
        assert panel.target_combo.currentData() == "y"

    def test_target_x_is_selectable(self, panel):
        panel.target_combo.setCurrentIndex(1)
        assert panel.target_combo.currentData() == "x"

    def test_target_hint_names_y_as_the_replaced_axis_by_default(self, panel):
        assert "new Y values" in panel.target_hint.text()
        assert "x stays as-is" in panel.target_hint.text()

    def test_target_hint_updates_when_target_changes_to_x(self, panel):
        panel.target_combo.setCurrentIndex(1)
        assert "new X values" in panel.target_hint.text()
        assert "y stays as-is" in panel.target_hint.text()


class TestChartTransformPanelInsertFunctionCode:
    """Inserted template code (shared with the dataset Transform panel,
    always written in terms of 'x') should be rewritten to whichever axis
    is the current Target -- inserting "x * 2" while replacing Y is not
    the expression the user asked for."""

    def test_inserts_unchanged_when_target_is_x(self, panel):
        panel.target_combo.setCurrentIndex(1)  # X
        panel._insert_function_code("x * 2")
        assert panel.expression_text.toPlainText() == "x * 2"

    def test_rewrites_x_to_y_when_target_is_y(self, panel):
        assert panel.target_combo.currentData() == "y"
        panel._insert_function_code("x * 2")
        assert panel.expression_text.toPlainText() == "y * 2"

    def test_does_not_corrupt_identifiers_that_merely_contain_an_x(self, panel):
        panel._insert_function_code("np.exp(x)")
        assert panel.expression_text.toPlainText() == "np.exp(y)"

    def test_inserts_into_existing_text_rather_than_overwriting_it(self, panel):
        panel.expression_text.setPlainText("1 + 1")
        panel._insert_function_code("x * 2")
        assert "y * 2" in panel.expression_text.toPlainText()
        assert "1 + 1" in panel.expression_text.toPlainText()


class TestChartTransformPanelApply:
    def test_apply_with_no_expression_shows_error(self, panel):
        panel.apply()
        assert "Select a series" in panel.preview_text.toPlainText()

    def test_preview_shows_the_result(self, panel):
        panel.expression_text.setPlainText("y * 2")
        panel.preview()
        assert "Result:" in panel.preview_text.toPlainText()

    def test_preview_shows_an_error_for_an_unsafe_expression(self, panel):
        panel.expression_text.setPlainText("__import__('os')")
        panel.preview()
        assert "Preview error" in panel.preview_text.toPlainText()

    def test_apply_creates_a_new_dataset_and_adds_it_as_a_series(self, panel, project):
        chart = project.find_item("chart-1")
        series_count_before = len(chart.data_series)
        panel.expression_text.setPlainText("y * 2")
        panel.apply()
        assert "Created a new dataset" in panel.preview_text.toPlainText()
        assert "added it to the chart as a series" in panel.preview_text.toPlainText()
        datasets = [item for item in project.get_all_items() if isinstance(item, Dataset)]
        assert len(datasets) == 2
        assert len(chart.data_series) == series_count_before + 1

    def test_apply_places_the_new_dataset_in_the_charts_folder(self, app_context, project):
        folder = Folder(id="folder-1", name="Charts")
        project.add_item(folder)
        chart = project.find_item("chart-1")
        project.remove_item(chart)
        chart.parent_id = None
        project.add_item(chart, parent_id="folder-1")

        panel = ChartTransformPanel(app_context)
        panel.current_chart = chart
        panel.current_chart_id = "chart-1"
        panel._populate_sources()
        panel.expression_text.setPlainText("y * 2")
        panel.apply()

        datasets = [item for item in project.get_all_items() if isinstance(item, Dataset) and item.id != "ds-1"]
        assert len(datasets) == 1
        assert datasets[0].parent_id == "folder-1"

    def test_clear_inputs_resets_the_form(self, panel):
        panel.expression_text.setPlainText("y * 2")
        panel.result_name.setText("Custom")
        panel.clear_inputs()
        assert panel.expression_text.toPlainText() == ""
        assert panel.result_name.text() == ""


class TestChartTransformPanelButtons:
    def test_apply_button_is_primary_and_simply_labeled(self, panel):
        assert panel.apply_btn.text() == "Apply"
        assert panel.apply_btn.property("primary") is True

    def test_clear_button_is_secondary_and_simply_labeled(self, panel):
        assert panel.clear_btn.text() == "Clear"
        assert panel.clear_btn.property("secondary") is True

    def test_preview_button_is_secondary_and_simply_labeled(self, panel):
        assert panel.preview_btn.text() == "Preview"
        assert panel.preview_btn.property("secondary") is True


class TestChartTransformPanelSeriesSelectedEvent:
    """Clicking a series/fit on the chart canvas or its legend (#341, #107)
    should also select it here, so switching to "transform it" doesn't
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

    def test_ignores_event_for_a_different_chart(self, panel):
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "some-other-chart", "kind": "series", "index": 0}
        )

        assert panel.source_combo.currentIndex() == 0
