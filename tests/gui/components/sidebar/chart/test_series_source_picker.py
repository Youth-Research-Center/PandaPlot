"""Tests for the shared series/fit combo-box populator."""

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    populate_series_fit_sources,
    series_source_hint,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
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
