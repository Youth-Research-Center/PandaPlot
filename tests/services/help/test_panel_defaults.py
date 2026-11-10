"""The numbers the help text states must equal the defaults and ranges of the real panel widgets."""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QFormLayout

from pandaplot.analysis.analysis_types import AnalysisType
from pandaplot.analysis.signal.signal_types import SIGNAL_ANALYSES, SignalAnalysisType
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart.tabs.chart_tab import ChartTab
from pandaplot.gui.components.sidebar.chart_analysis.chart_analysis_panel import ChartAnalysisPanel
from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.sidebar.signal.signal_parameter_widgets import build_signal_parameter_widgets
from pandaplot.gui.components.sidebar.statistics.descriptive_panel import DescriptiveStatsPanel
from pandaplot.gui.components.sidebar.statistics.statistics_panel import StatisticsPanel
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.content import panel_defaults as defaults
from pandaplot.services.help.content.panel_defaults import SpinRange
from pandaplot.services.help.help_catalog import get_help_catalog
from pandaplot.services.help.help_types import PANEL_TOPIC_FIT
from tests.gui.icon_testing import ICON_TOKENS


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **ICON_TOKENS}
    return ctx


def _assert_spin(widget, expected: SpinRange) -> None:
    assert widget.value() == expected.default
    assert widget.minimum() == expected.minimum
    assert widget.maximum() == expected.maximum


class TestDatasetAnalysisPanel:
    def test_interpolation_points(self, app_context):
        panel = AnalysisPanel(app_context)
        panel.analysis_type_combo.setCurrentText("Interpolation")

        _assert_spin(panel.num_points_spin, defaults.INTERPOLATION_POINTS_DATASET)

    def test_savgol_window_and_order(self, app_context):
        panel = AnalysisPanel(app_context)
        panel.analysis_type_combo.setCurrentText("Smoothing")
        panel.smooth_method_combo.setCurrentText("Savitzky-Golay")

        _assert_spin(panel.window_length_spin, defaults.SAVGOL_WINDOW_LENGTH)
        _assert_spin(panel.poly_order_spin, defaults.SAVGOL_POLYNOMIAL_ORDER)

    def test_rolling_mean_window(self, app_context):
        panel = AnalysisPanel(app_context)
        panel.analysis_type_combo.setCurrentText("Smoothing")
        panel.smooth_method_combo.setCurrentText("Rolling Mean")

        _assert_spin(panel.window_spin, defaults.ROLLING_WINDOW_DATASET)


class TestChartAnalysisPanel:
    def _select(self, panel: ChartAnalysisPanel, operation: AnalysisType) -> None:
        panel.operation_combo.setCurrentIndex(panel.operation_combo.findData(operation))

    def test_interpolation_points(self, app_context):
        panel = ChartAnalysisPanel(app_context)
        self._select(panel, AnalysisType.INTERPOLATION)

        _assert_spin(panel.num_points_spin, defaults.INTERPOLATION_POINTS_CHART)

    def test_savgol_window_and_order(self, app_context):
        panel = ChartAnalysisPanel(app_context)
        self._select(panel, AnalysisType.SMOOTHING)
        panel.smooth_method_combo.setCurrentIndex(panel.smooth_method_combo.findData("savgol"))

        _assert_spin(panel.window_length_spin, defaults.SAVGOL_WINDOW_LENGTH)
        _assert_spin(panel.poly_order_spin, defaults.SAVGOL_POLYNOMIAL_ORDER)

    def test_rolling_mean_window(self, app_context):
        panel = ChartAnalysisPanel(app_context)
        self._select(panel, AnalysisType.SMOOTHING)
        panel.smooth_method_combo.setCurrentIndex(panel.smooth_method_combo.findData("rolling_mean"))

        _assert_spin(panel.window_spin, defaults.ROLLING_WINDOW_CHART)


def test_fit_points(app_context):
    _assert_spin(FitPanel(app_context).fit_points_spin, defaults.FIT_POINTS)


def test_descriptive_significant_digits(app_context):
    _assert_spin(DescriptiveStatsPanel(app_context).digits_spin, defaults.DESCRIPTIVE_SIGNIFICANT_DIGITS)


def test_statistics_significance_and_expected_mean(app_context):
    panel = StatisticsPanel(app_context)

    _assert_spin(panel.alpha_spin, defaults.SIGNIFICANCE_ALPHA)
    assert panel.popmean_spin is not None
    assert panel.popmean_spin.value() == defaults.EXPECTED_MEAN.default


class TestSignalParameterWidgets:
    @pytest.fixture
    def widgets(self):
        """Widgets per analysis type, with their layouts kept alive so the widgets are not deleted."""
        layouts = {analysis_type: QFormLayout() for analysis_type in SIGNAL_ANALYSES}
        self._layouts = layouts
        return {analysis_type: build_signal_parameter_widgets(layouts[analysis_type], info) for analysis_type, info in SIGNAL_ANALYSES.items()}

    def test_sampling_rate_default(self, widgets):
        by_type = widgets

        assert by_type[SignalAnalysisType.FFT]["sampling_rate"].value() == defaults.SAMPLING_RATE_DATASET.default

    def test_overlap_range_and_default(self, widgets):
        by_type = widgets
        overlap = by_type[SignalAnalysisType.STFT]["overlap"]

        assert overlap.value() == SIGNAL_ANALYSES[SignalAnalysisType.STFT].default_overlap == defaults.SIGNAL_OVERLAP.default
        assert overlap.minimum() == defaults.SIGNAL_OVERLAP.minimum
        assert overlap.maximum() == defaults.SIGNAL_OVERLAP.maximum

    def test_peak_defaults(self, widgets):
        by_type = widgets
        peaks = by_type[SignalAnalysisType.PEAKS]

        assert peaks["height"].value() == defaults.PEAK_MINIMUM_HEIGHT_DEFAULT
        assert peaks["distance"].value() == defaults.PEAK_MINIMUM_DISTANCE.default
        assert peaks["distance"].minimum() == defaults.PEAK_MINIMUM_DISTANCE.minimum
        assert peaks["prominence"].value() == defaults.PEAK_PROMINENCE_DEFAULT
        assert peaks["threshold"].value() == defaults.PEAK_THRESHOLD_DEFAULT


class TestChartTab:
    def test_histogram_bins(self):
        _assert_spin(ChartTab().hist_bins_spin, defaults.HIST_BINS)


class TestHelpTextUsesTheConstants:
    def test_fit_panel_topic_states_the_fit_points_default(self):
        topic = get_help_catalog().get(PANEL_TOPIC_FIT)

        assert topic is not None
        assert f"({defaults.FIT_POINTS.default} by default)" in "\n".join(topic.steps)

    def test_fit_panel_topic_lists_exactly_the_chart_types_without_fits(self):
        topic = get_help_catalog().get(PANEL_TOPIC_FIT)
        assert topic is not None
        without_fit = [spec.display_name for spec in CHART_TYPE_SPECS.values() if not spec.allows_fit]

        assert without_fit
        assert all(name in topic.explanation for name in without_fit)
