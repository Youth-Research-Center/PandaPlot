"""Tests for the shared series/fit combo-box populator."""

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    populate_chart_target_combo,
    populate_series_fit_sources,
    series_source_hint,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def chart():
    project = Project(name="P")
    t = np.linspace(0.0, 10.0, 11)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    chart.add_data_series(dataset_id="ds-1", x_column="t", y_column="sq", label="Squared")
    project.add_item(chart)
    return chart


class TestPopulateSeriesFitSources:
    def test_no_chart_yields_no_sources(self):
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, None)
        assert has_sources is False
        assert any_excluded is False
        assert combo.count() == 0

    def test_eligible_series_is_listed(self, chart):
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, chart)
        assert has_sources is True
        assert any_excluded is False
        assert combo.itemData(0) == ("series", 0)
        assert "Squared" in combo.itemText(0)

    def test_bar_series_is_excluded(self, chart):
        chart.data_series[0].series_type = SeriesType.BAR
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, chart)
        assert has_sources is False
        assert any_excluded is True

    def test_fits_are_offered_alongside_series(self, chart):
        chart.add_fit_data(
            source_dataset_id="ds-1", fit_type="linear",
            x_data=[1.0, 2.0], y_data=[1.0, 2.0], label="Fit 1",
        )
        combo = QComboBox()
        populate_series_fit_sources(combo, chart)
        assert combo.itemData(1) == ("fit", 0)


class TestSeriesSourceHint:
    def test_no_sources_no_exclusion(self):
        assert (
            series_source_hint(has_sources=False, any_series_excluded=False)
            == "This chart has no data series or fits yet."
        )

    def test_no_sources_with_exclusion(self):
        assert "aren't supported here" in series_source_hint(
            has_sources=False, any_series_excluded=True
        )

    def test_has_sources_no_exclusion(self):
        assert (
            series_source_hint(has_sources=True, any_series_excluded=False)
            == "Data series and fitted curves of this chart."
        )

    def test_has_sources_with_exclusion(self):
        assert "aren't shown" in series_source_hint(has_sources=True, any_series_excluded=True)


@pytest.fixture
def project_with_charts():
    project = Project(name="P")
    line_chart = Chart(id="line-1", name="Line Chart", chart_type=ChartType.LINE)
    project.add_item(line_chart)
    hist_chart = Chart(id="hist-1", name="Hist Chart", chart_type=ChartType.HIST)
    project.add_item(hist_chart)
    return project


class TestPopulateChartTargetCombo:
    def test_new_chart_is_always_first_and_selected_by_default(self, project_with_charts):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts)
        assert combo.itemText(0) == "➕ New chart"
        assert combo.itemData(0) is None
        assert combo.currentIndex() == 0

    def test_compatible_charts_are_listed(self, project_with_charts):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts)
        assert combo.itemText(1) == "Line Chart"
        assert combo.itemData(1) == "line-1"

    def test_incompatible_charts_are_excluded(self, project_with_charts):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts)
        labels = [combo.itemText(i) for i in range(combo.count())]
        assert "Hist Chart" not in labels

    def test_no_project_yields_only_new_chart(self):
        combo = QComboBox()
        populate_chart_target_combo(combo, None)
        assert combo.count() == 1
        assert combo.itemData(0) is None

    def test_same_named_charts_get_disambiguated_labels(self):
        project = Project(name="P")
        folder_a = Folder(id="fa", name="A")
        project.add_item(folder_a)
        folder_b = Folder(id="fb", name="B")
        project.add_item(folder_b)
        project.add_item(Chart(id="c1", name="Signal", chart_type=ChartType.LINE), parent_id="fa")
        project.add_item(Chart(id="c2", name="Signal", chart_type=ChartType.LINE), parent_id="fb")

        combo = QComboBox()
        populate_chart_target_combo(combo, project)

        labels = [combo.itemText(i) for i in range(combo.count())]
        assert labels[0] == "➕ New chart"
        assert "A" in labels[1] and "Signal" in labels[1]
        assert "B" in labels[2] and "Signal" in labels[2]
        assert labels[1] != labels[2]
