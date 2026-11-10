"""Tests for the shared series/fit combo-box populator."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QComboBox

from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    find_series_fit_combo_index,
    populate_chart_target_combo,
    populate_series_fit_sources,
    retint_combo_icons,
    series_source_hint,
)
from pandaplot.gui.resources.item_icons import item_icon
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


ICON_SIZE = QSize(16, 16)


@pytest.fixture
def app_context():
    context = Mock()
    context.get_manager.return_value.get_design_tokens.return_value = dict(ICON_TOKENS)
    return context


def _same_pixels(first, second) -> bool:
    return first.pixmap(ICON_SIZE).toImage() == second.pixmap(ICON_SIZE).toImage()


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
    def test_no_chart_yields_no_sources(self, app_context):
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, None, app_context=app_context)
        assert has_sources is False
        assert any_excluded is False
        assert combo.count() == 0

    def test_eligible_series_is_listed(self, chart, app_context):
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, chart, app_context=app_context)
        assert has_sources is True
        assert any_excluded is False
        assert combo.itemData(0) == 0
        assert combo.itemText(0) == "Squared"
        assert _same_pixels(combo.itemIcon(0), item_icon(app_context, "chart"))

    def test_bar_series_is_excluded(self, chart, app_context):
        chart.data_series[0].series_type = SeriesType.BAR
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, chart, app_context=app_context)
        assert has_sources is False
        assert any_excluded is True

    def test_fits_are_offered_alongside_series(self, chart, app_context):
        chart.add_fit_series(
            "ds-1", x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
            label="Fit 1", style=FitStyle(fit_type="linear"),
        )
        combo = QComboBox()
        populate_series_fit_sources(combo, chart, app_context=app_context)
        assert combo.itemData(1) == 1
        assert combo.itemText(1) == "Fit 1  (fit)"
        assert _same_pixels(combo.itemIcon(1), themed_icon(app_context, "waveform"))

    def test_a_chart_with_only_a_fit_does_not_report_any_series_excluded(self, chart, app_context):
        """Regression test for final-review Minor finding #6: a FIT-type
        entry in chart.data_series hits the loop's supports_curve_analysis
        check and used to set any_series_excluded=True even though the fit
        IS listed, just via the separate fit-listing loop below. A chart
        whose only non-plain-series entry is a fit must not report any
        exclusion at all."""
        only_fit_chart = Chart(id="fit-only", name="Fit Only")
        only_fit_chart.add_fit_series(
            "ds-1", x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
            label="Fit 1", style=FitStyle(fit_type="linear"),
        )
        combo = QComboBox()
        has_sources, any_excluded = populate_series_fit_sources(combo, only_fit_chart, app_context=app_context)
        assert has_sources is True
        assert any_excluded is False
        assert combo.itemData(0) == 0

    def test_item_data_is_the_data_series_index_not_the_combo_row(self, app_context):
        """Regression test for final-review Important #1: with a chart whose
        data_series is [FIT, excluded BAR, LINE], the combo lists the fit
        and the line in that order (fits-after-series in the loop, but
        series-then-fits in the combo), so combo row != real data_series
        index for either entry. itemData must carry the real index anyway."""
        project = Project(name="P")
        dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]}))
        project.add_item(dataset)
        chart = Chart(id="c", name="C")
        chart.add_fit_series(
            "ds-1", x_data=np.array([1.0, 2.0]), y_data=np.array([1.0, 2.0]),
            label="Fit A", style=FitStyle(fit_type="linear"),
        )  # data_series[0]
        chart.add_data_series(dataset_id="ds-1", label="Bars", series_type=SeriesType.BAR)  # data_series[1], excluded
        chart.add_data_series(dataset_id="ds-1", label="Line", series_type=SeriesType.LINE)  # data_series[2]
        project.add_item(chart)

        combo = QComboBox()
        populate_series_fit_sources(combo, chart, app_context=app_context)

        assert [combo.itemData(i) for i in range(combo.count())] == [2, 0]
        assert find_series_fit_combo_index(combo, 0) == 1
        assert find_series_fit_combo_index(combo, 1) == -1


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
    def test_new_chart_is_always_first_and_selected_by_default(self, project_with_charts, app_context):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts, app_context=app_context)
        assert combo.itemText(0) == "New chart"
        assert combo.itemData(0) is None
        assert combo.currentIndex() == 0

    def test_new_chart_has_the_plus_icon(self, project_with_charts, app_context):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts, app_context=app_context)
        assert _same_pixels(combo.itemIcon(0), themed_icon(app_context, "plus"))

    def test_compatible_charts_are_listed(self, project_with_charts, app_context):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts, app_context=app_context)
        assert combo.itemText(1) == "Line Chart"
        assert combo.itemData(1) == "line-1"

    def test_incompatible_charts_are_excluded(self, project_with_charts, app_context):
        combo = QComboBox()
        populate_chart_target_combo(combo, project_with_charts, app_context=app_context)
        labels = [combo.itemText(i) for i in range(combo.count())]
        assert "Hist Chart" not in labels

    def test_no_project_yields_only_new_chart(self, app_context):
        combo = QComboBox()
        populate_chart_target_combo(combo, None, app_context=app_context)
        assert combo.count() == 1
        assert combo.itemData(0) is None

    def test_same_named_charts_get_disambiguated_labels(self, app_context):
        project = Project(name="P")
        folder_a = Folder(id="fa", name="A")
        project.add_item(folder_a)
        folder_b = Folder(id="fb", name="B")
        project.add_item(folder_b)
        project.add_item(Chart(id="c1", name="Signal", chart_type=ChartType.LINE), parent_id="fa")
        project.add_item(Chart(id="c2", name="Signal", chart_type=ChartType.LINE), parent_id="fb")

        combo = QComboBox()
        populate_chart_target_combo(combo, project, app_context=app_context)

        labels = [combo.itemText(i) for i in range(combo.count())]
        assert labels[0] == "New chart"
        assert "A" in labels[1] and "Signal" in labels[1]
        assert "B" in labels[2] and "Signal" in labels[2]
        assert labels[1] != labels[2]


class TestRetintComboIcons:
    def test_icons_follow_the_current_theme_tokens(self, chart, project_with_charts, app_context):
        series_combo = QComboBox()
        populate_series_fit_sources(series_combo, chart, app_context=app_context)
        target_combo = QComboBox()
        populate_chart_target_combo(target_combo, project_with_charts, app_context=app_context)
        app_context.get_manager.return_value.get_design_tokens.return_value = {**ICON_TOKENS, "text_primary": "#00AA00"}

        retint_combo_icons(series_combo, app_context)
        retint_combo_icons(target_combo, app_context)

        assert_tinted(strongest_pixel(series_combo.itemIcon(0)), "#00AA00")
        assert_tinted(strongest_pixel(target_combo.itemIcon(0)), "#00AA00")
        assert target_combo.itemText(0) == "New chart"
        assert target_combo.itemIcon(1).isNull()

    def test_a_combo_without_icons_is_left_alone(self, app_context):
        combo = QComboBox()
        combo.addItem("Plain", 1)

        retint_combo_icons(combo, app_context)

        assert combo.itemIcon(0).isNull()
