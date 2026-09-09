"""Tests for ChartSignalAnalysisPanel: source picker filtering, segment
index -> (x, y) preview labels, method/parameter widget wiring, the
sampling-rate pre-fill, and the async run/apply dispatch (mirroring
test_chart_analysis_panel.py and test_signal_panel.py respectively).
"""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.analysis import SIGNAL_ANALYSES, SignalAnalysisType
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart import AddAnalysisSeriesCommand, CreateChartWithAnalysisSeriesCommand
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.gui.components.sidebar.chart_signal.chart_signal_analysis_panel import (
    ChartSignalAnalysisPanel,
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
    # A known-frequency signal: 100 samples/second over 1 second, 5 Hz sine.
    t = np.linspace(0.0, 1.0, 101)
    y = np.sin(2 * np.pi * 5 * t)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "signal": y}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("signal")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="signal", label="Signal")
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
    panel = ChartSignalAnalysisPanel(app_context)
    panel.current_chart = project.find_item("chart-1")
    panel.current_chart_id = "chart-1"
    panel._populate_sources()
    return panel


class TestSourcePickerFiltering:
    """Same filtering rules as ChartAnalysisPanel (#202): series types with
    no meaningful ordered (x, y) curve are excluded from the source picker."""

    def _combo_labels(self, panel):
        return [panel.source_combo.itemText(i) for i in range(panel.source_combo.count())]

    def test_bar_series_is_excluded_from_the_source_picker(self, panel):
        panel.current_chart.data_series[0].series_type = SeriesType.BAR
        panel._populate_sources()

        assert self._combo_labels(panel) == []
        assert panel.run_btn.isEnabled() is False

    def test_line_and_scatter_series_are_offered(self, panel):
        assert any("Signal" in label for label in self._combo_labels(panel))


class TestSegmentRangeLabels:
    def test_labels_show_no_selection_placeholder_without_source(self, app_context):
        panel = ChartSignalAnalysisPanel(app_context)

        assert panel.start_value_label.text() == "–"
        assert panel.end_value_label.text() == "–"

    def test_start_label_updates_on_index_change(self, panel):
        panel.start_index.setValue(10)

        # sin(2*pi*5*0.1) == sin(pi) ~ 0 (numerically ~1e-16, formatted as such).
        assert panel.start_value_label.text().startswith("x=0.1, y=")

    def test_end_index_defaults_to_the_last_point(self, panel):
        assert panel.end_index.minimum() == 0
        assert panel.end_index.value() == 100
        assert panel.end_value_label.text() != "–"

    def test_end_label_updates_on_explicit_index(self, panel):
        panel.end_index.setValue(50)

        assert panel.end_value_label.text() != "–"

    def test_build_parameters_sends_inclusive_end_as_exclusive_boundary(self, panel):
        panel.start_index.setValue(0)
        panel.end_index.setValue(50)

        assert panel._build_parameters()["end_index"] == 51


class TestSourceChangeResetsSegment:
    """Regression: _on_source_changed only reset end_index (via
    setMaximum()/setValue()) -- a nonzero start carried over from the
    previous source either stayed as-is (if still in range) or got clamped
    down to the new source's last index rather than reset to 0, leaving a
    shrunk or degenerate one-point segment instead of actually selecting
    the whole new series."""

    def test_start_index_resets_to_zero_when_switching_to_a_shorter_source(self, app_context, project):
        short_t = np.linspace(0.0, 0.05, 6)
        short_dataset = Dataset(
            id="ds-2", name="Short",
            data=pd.DataFrame({"t": short_t, "signal": np.sin(2 * np.pi * 5 * short_t)}),
        )
        project.add_item(short_dataset)

        chart = project.find_item("chart-1")
        chart.add_data_series(
            dataset_id="ds-2",
            x_column_id=short_dataset.column_id("t"), y_column_id=short_dataset.column_id("signal"),
            x_column="t", y_column="signal", label="Short",
        )

        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = chart
        panel.current_chart_id = "chart-1"
        panel._populate_sources()

        panel.source_combo.setCurrentIndex(0)  # the 101-point "Signal" series
        panel.start_index.setValue(30)
        assert panel.start_index.value() == 30

        panel.source_combo.setCurrentIndex(1)  # the 6-point "Short" series

        assert panel.start_index.value() == 0
        assert panel.end_index.value() == panel.end_index.maximum()


class TestMethodDropdownAndParameterWidgets:
    def test_method_dropdown_lists_exactly_the_signal_analyses(self, panel):
        assert panel.analysis_combo.count() == len(SIGNAL_ANALYSES)
        types = {panel.analysis_combo.itemData(i) for i in range(panel.analysis_combo.count())}
        assert types == set(SIGNAL_ANALYSES.keys())

    def _select(self, panel, analysis_type: SignalAnalysisType):
        index = panel.analysis_combo.findData(analysis_type)
        assert index != -1
        panel.analysis_combo.setCurrentIndex(index)

    def test_fft_shows_sampling_rate_nfft_and_window(self, panel):
        self._select(panel, SignalAnalysisType.FFT)

        assert panel.sampling_rate is not None
        assert panel.nfft_spin is not None
        assert panel.window_combo is not None
        assert panel.nperseg_spin is None
        assert panel.height_spin is None

    def test_peaks_shows_peak_params_and_no_sampling_rate(self, panel):
        self._select(panel, SignalAnalysisType.PEAKS)

        assert panel.sampling_rate is None
        assert panel.height_spin is not None
        assert panel.distance_spin is not None
        assert panel.prominence_spin is not None
        assert panel.threshold_spin is not None

    def test_autocorrelation_has_no_sampling_rate_widget(self, panel):
        self._select(panel, SignalAnalysisType.AUTOCORRELATION)

        assert panel.sampling_rate is None


class TestSamplingRatePrefill:
    def test_prefill_reflects_median_sample_spacing_over_the_segment(self, panel):
        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        # t = linspace(0, 1, 101) -> spacing 0.01 -> sampling rate ~100 Hz.
        assert panel.sampling_rate.value() == pytest.approx(100.0, rel=1e-2)

    def test_prefill_changes_when_the_segment_changes(self, panel):
        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        panel.start_index.setValue(0)
        panel.end_index.setValue(10)  # spacing still 0.01 -> same rate, but recomputed
        first = panel.sampling_rate.value()

        # Manually overwrite, then force a recompute via a segment change --
        # this asserts the panel actively recomputes on segment change
        # (not just leaves whatever the user set).
        panel.sampling_rate.setValue(1.0)
        panel.end_index.setValue(20)

        assert panel.sampling_rate.value() == pytest.approx(first, rel=1e-2)
        assert panel.sampling_rate.value() != 1.0

    def test_prefill_handles_a_descending_x_axis(self, app_context, project):
        """Regression: filtering diffs to > 0 assumed ascending x -- a
        descending (or mixed-direction) axis produced no positive diffs at
        all, silently falling back to the unrelated 1000 Hz default instead
        of a usable estimate. Sampling interval is a magnitude, so the fix
        takes abs(diff(x)) before filtering."""
        dataset = project.find_item("ds-1")
        dataset.data = dataset.data.iloc[::-1].reset_index(drop=True)  # descending t

        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"
        panel._populate_sources()

        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        assert panel.sampling_rate.value() == pytest.approx(100.0, rel=1e-2)

    def test_prefill_ignores_non_finite_diffs_from_a_non_numeric_x_value(self, app_context, project):
        """Regression: resolve_series_xy()'s missing-value mask runs before
        its numeric coercion, so a non-numeric (but non-NaN) x cell survives
        the mask and only turns into NaN afterward -- the resulting NaN diff
        used to propagate through np.median into a NaN sampling rate instead
        of being filtered alongside the zero diffs."""
        dataset = project.find_item("ds-1")
        dataset.data["t"] = dataset.data["t"].astype(object)
        dataset.data.loc[10, "t"] = "not-a-number"

        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"
        panel._populate_sources()

        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        assert not np.isnan(panel.sampling_rate.value())
        assert panel.sampling_rate.value() == pytest.approx(100.0, rel=1e-2)


class TestRunAnalysisAsyncDispatch:
    def _fake_result(self):
        result = Mock()
        result.analysis_name = "FFT"
        result.data = pd.DataFrame({"frequency": [1.0, 2.0], "magnitude": [0.1, 0.2]})
        result.metadata = {}
        return result

    def test_success_path_populates_results_and_enables_add(self, panel):
        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()

        assert panel.busy_spinner.is_running is True
        assert panel.run_btn.isEnabled() is False
        assert panel.add_btn.isEnabled() is False

        captured["on_complete"](self._fake_result(), None)

        assert panel.busy_spinner.is_running is False
        assert panel.run_btn.isEnabled() is True
        assert panel.add_btn.isEnabled() is True
        assert "FFT" in panel.results_text.toPlainText()

    def test_failure_path_shows_error(self, panel):
        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command

        panel.run_analysis()
        captured["on_complete"](None, "boom")

        assert panel.busy_spinner.is_running is False
        assert panel.add_btn.isEnabled() is False
        assert "boom" in panel.results_text.toPlainText()


class TestResultFolderMatchesChart:
    """Regression (#347): the result dataset should land in the chart's own
    folder instead of always at the project root."""

    def test_build_command_uses_the_chart_parent_folder(self, app_context, project):
        from pandaplot.models.project.items.folder import Folder

        folder = Folder(id="folder-1", name="F")
        project.add_item(folder)
        chart = project.find_item("chart-1")
        project.root.remove_item(chart)
        project.add_item(chart, parent_id="folder-1")

        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = chart
        panel.current_chart_id = "chart-1"
        panel._populate_sources()

        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        command = panel._build_command()

        assert command.folder_id == "folder-1"

    def test_cached_add_to_project_uses_the_chart_parent_folder(self, app_context, project, monkeypatch):
        from pandaplot.models.project.items.folder import Folder

        folder = Folder(id="folder-1", name="F")
        project.add_item(folder)
        chart = project.find_item("chart-1")
        project.root.remove_item(chart)
        project.add_item(chart, parent_id="folder-1")

        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = chart
        panel.current_chart_id = "chart-1"
        panel._populate_sources()

        current_params = panel._get_dispatch_params()
        panel.last_result = Mock()
        panel._last_run_params = current_params

        captured = {}

        class _FakeApplyCommand:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr(
            "pandaplot.gui.components.sidebar.chart_signal.chart_signal_analysis_panel.ApplySignalAnalysisResultCommand",
            _FakeApplyCommand,
        )
        panel.app_context.get_command_executor.return_value.execute_command = lambda command: True

        panel.add_results_to_project()

        assert captured["folder_id"] == "folder-1"


class TestRunAndAddMutualExclusion:
    """Regression coverage (mirrors SignalPanel's): Run and Add to Project
    share one busy spinner and one _pending_command slot."""

    def test_add_is_a_no_op_while_run_is_in_flight(self, panel):
        run_captured = {}
        run_command = Mock()
        run_command.run_analysis_async = lambda on_complete: run_captured.update(on_complete=on_complete)
        panel._build_command = lambda: run_command
        panel.run_analysis()
        assert panel._pending_command is run_command

        add_attempted = {}

        def _build_add_command():
            add_attempted["built"] = True
            return Mock()

        panel._build_command = _build_add_command
        panel.add_results_to_project()

        assert "built" not in add_attempted
        assert panel._pending_command is run_command

    def test_run_is_a_no_op_while_add_is_in_flight(self, panel):
        add_command = Mock()
        add_command.result = Mock()
        panel.app_context.get_command_executor.return_value.execute_command = lambda command: True
        panel._build_command = lambda: add_command
        panel.add_results_to_project()
        assert panel._pending_command is add_command

        run_attempted = {}

        def _build_run_command():
            run_attempted["built"] = True
            return Mock()

        panel._build_command = _build_run_command
        panel.run_analysis()

        assert "built" not in run_attempted
        assert panel._pending_command is add_command


class TestPopulateSourcesRespectsPendingCommand:
    """Regression: switching the active chart tab while a Run/Add-to-Project
    computation is still in flight for the previous chart used to
    re-enable the Run button via _populate_sources() (has_sources alone),
    even though _pending_command was still set -- the button looked live
    but silently no-op'd until the in-flight computation completed."""

    def test_run_button_stays_disabled_while_a_command_is_pending(self, panel):
        run_captured = {}
        run_command = Mock()
        run_command.run_analysis_async = lambda on_complete: run_captured.update(on_complete=on_complete)
        panel._build_command = lambda: run_command
        panel.run_analysis()
        assert panel._pending_command is run_command
        assert panel.run_btn.isEnabled() is False

        # Simulate switching to another (still valid) chart tab while the
        # run is still in flight.
        panel._populate_sources()

        assert panel.run_btn.isEnabled() is False

    def test_run_button_re_enables_once_pending_command_clears(self, panel):
        run_captured = {}
        run_command = Mock()
        run_command.run_analysis_async = lambda on_complete: run_captured.update(on_complete=on_complete)
        panel._build_command = lambda: run_command
        panel.run_analysis()

        run_captured["on_complete"](
            Mock(analysis_name="FFT", data=pd.DataFrame({"a": [1.0]}), metadata={}), None,
        )
        panel._populate_sources()

        assert panel.run_btn.isEnabled() is True


class TestRangeCommandCaching:
    """Regression: _range_command() used to build a brand-new
    ChartSignalAnalysisCommand on every call, defeating its own
    _resolved_xy_cache and forcing the sampling-rate pre-fill to loop
    resolve_point() once per index in the segment. It now reuses one
    instance per (chart, source) -- invalidated whenever sources are
    repopulated, since a chart update may have changed the underlying data
    -- and computes the sampling-rate default via one vectorized
    resolve_segment_x() call instead."""

    def test_range_command_is_reused_for_the_same_source(self, panel):
        first = panel._range_command("series", 0)
        second = panel._range_command("series", 0)
        assert first is second

    def test_range_command_cache_is_invalidated_on_repopulate(self, panel):
        first = panel._range_command("series", 0)
        panel._populate_sources()
        second = panel._range_command("series", 0)
        assert first is not second

    def test_sampling_rate_prefill_uses_resolve_segment_x_not_a_per_index_loop(self, panel):
        index = panel.analysis_combo.findData(SignalAnalysisType.FFT)
        panel.analysis_combo.setCurrentIndex(index)

        command = panel._range_command("series", 0)
        command.resolve_point = Mock(
            side_effect=AssertionError("resolve_point should not be used for the sampling-rate prefill")
        )

        panel._refresh_sampling_rate_default()

        command.resolve_point.assert_not_called()

    def test_repopulate_with_no_eligible_source_releases_the_cached_command(self, panel):
        """Regression: clearing only _range_command_key (not
        _range_command_cache) meant that once there was no eligible source
        at all (chart closed, or repopulated with nothing to analyze),
        _range_command() returned None without ever rebuilding -- leaving
        the old command (and its resolved, potentially large x/y series)
        referenced for the rest of the panel's lifetime."""
        panel._range_command("series", 0)
        assert panel._range_command_cache is not None

        panel.current_chart = None
        panel.current_chart_id = None
        panel._populate_sources()

        assert panel._range_command_cache is None


class TestStaleCompletionDiscard:
    """Regression: the staleness check used to compare only
    (chart_id, source) -- if the method, sampling rate, segment, or a
    parameter widget changed while a preview/commit was in flight, the old
    result still got displayed/committed under the new UI state. It must
    now compare the full dispatch parameters (and a generation counter, for
    changes to the underlying data that don't move any of those)."""

    def test_run_discards_a_stale_result_when_the_method_changes_mid_flight(self, panel):
        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command
        panel.run_analysis()

        # Switch method while the (fake) background computation is still
        # running.
        peaks_index = panel.analysis_combo.findData(SignalAnalysisType.PEAKS)
        panel.analysis_combo.setCurrentIndex(peaks_index)

        result = Mock(analysis_name="FFT", data=pd.DataFrame({"a": [1.0]}), metadata={})
        captured["on_complete"](result, None)

        assert panel.last_result is None
        assert panel.add_btn.isEnabled() is False
        assert "FFT" not in panel.results_text.toPlainText()

    def test_add_discards_a_stale_commit_when_the_method_changes_mid_flight(self, panel):
        command = Mock()
        command.result = Mock()
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()
        assert panel._pending_command is command

        peaks_index = panel.analysis_combo.findData(SignalAnalysisType.PEAKS)
        panel.analysis_combo.setCurrentIndex(peaks_index)

        command.on_complete(CommandResult.SUCCESS)

        assert panel.last_result is None
        assert "added to project" not in panel.results_text.toPlainText()

    def test_run_discards_a_stale_result_after_a_chart_update_bumps_generation(self, panel):
        """Same-params case: the underlying data changed (e.g. a dataset
        edit re-emitted CHART_UPDATED for this chart) without moving any of
        the dispatch parameters themselves -- only the generation counter
        catches this one."""
        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command
        panel.run_analysis()

        panel._on_chart_updated({"chart": panel.current_chart})

        result = Mock(analysis_name="FFT", data=pd.DataFrame({"a": [1.0]}), metadata={})
        captured["on_complete"](result, None)

        assert panel.last_result is None
        assert "FFT" not in panel.results_text.toPlainText()


class TestRunButtonRestoredFromCurrentContext:
    """Regression: the on_complete callbacks used to unconditionally
    re-enable Run, even if the user had since switched to a chart/tab with
    no eligible source -- leaving an active-looking button that would
    silently no-op via the _pending_command guard."""

    def test_run_completion_leaves_run_disabled_with_no_eligible_source(self, panel):
        captured = {}
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: captured.update(on_complete=on_complete)
        panel._build_command = lambda: fake_command
        panel.run_analysis()

        panel.source_combo.clear()  # simulate navigating to a chart with no sources

        captured["on_complete"](None, "boom")

        assert panel.run_btn.isEnabled() is False

    def test_add_completion_leaves_run_disabled_with_no_eligible_source(self, panel):
        command = Mock()
        command.result = Mock()
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()

        panel.source_combo.clear()

        command.on_complete(CommandResult.SUCCESS)

        assert panel.run_btn.isEnabled() is False


class TestClearWhilePending:
    """Regression: clear() (from the Clear button and every analysis-method
    change) used to unconditionally stop the busy spinner, even while a
    Run/Add computation was still in flight -- the panel then looked idle
    while Run/Add still silently no-op'd via the _pending_command guard."""

    def test_clear_does_not_stop_the_spinner_while_a_command_is_pending(self, panel):
        fake_command = Mock()
        fake_command.run_analysis_async = lambda on_complete: None
        panel._build_command = lambda: fake_command
        panel.run_analysis()
        assert panel.busy_spinner.is_running is True

        panel.clear()

        assert panel.busy_spinner.is_running is True

    def test_clear_stops_the_spinner_once_nothing_is_pending(self, panel):
        panel.busy_spinner.start()
        panel.clear()
        assert panel.busy_spinner.is_running is False


class TestDatasetChangedInvalidatesCache:
    """Regression: chart series read their values live from backing
    datasets, but the panel only listened for ChartEvents.CHART_UPDATED --
    an ordinary cell/row edit to the dataset (without that event) left the
    cached range command and any successful last_result looking valid,
    letting Add's fast path commit a preview computed from pre-edit data."""

    def test_dataset_changed_for_a_plotted_dataset_invalidates_range_command_and_last_result(self, panel):
        stale_range_command = panel._range_command("series", 0)
        panel.last_result = Mock()
        panel._last_run_params = panel._get_dispatch_params()

        panel._on_dataset_changed({"dataset_id": "ds-1"})

        assert panel._range_command("series", 0) is not stale_range_command
        assert panel.last_result is None
        assert panel._last_run_params is None

    def test_dataset_changed_for_an_unrelated_dataset_is_ignored(self, panel):
        stale_range_command = panel._range_command("series", 0)
        panel.last_result = Mock()

        panel._on_dataset_changed({"dataset_id": "some-other-dataset"})

        assert panel._range_command("series", 0) is stale_range_command
        assert panel.last_result is not None


class TestShowEventRefresh:
    """Regression: a Chart Properties > Data tab edit to a series'
    dataset/X/Y binding mutates the chart live but deliberately emits only
    `dirtyOnly`, not ChartEvents.CHART_UPDATED, and switching the active
    sidebar panel emits nothing at all -- so neither of this panel's two
    existing invalidation hooks ever fired for that edit. Qt's showEvent
    (fired when PanelArea, a QStackedWidget, makes this panel current)
    closes that gap."""

    def test_show_event_refreshes_sources_and_invalidates_cache(self, panel):
        stale_range_command = panel._range_command("series", 0)
        panel.last_result = Mock()
        panel._last_run_params = panel._get_dispatch_params()
        generation_before = panel._generation

        panel.show()

        assert panel._generation != generation_before
        assert panel.last_result is None
        assert panel._range_command("series", 0) is not stale_range_command

    def test_show_event_is_a_no_op_without_a_current_chart(self, app_context):
        panel = ChartSignalAnalysisPanel(app_context)
        panel.current_chart = None
        generation_before = panel._generation

        panel.show()

        assert panel._generation == generation_before


class TestChartSignalAnalysisPanelSeriesSelectedEvent:
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
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "series", "index": 5}
        )

        assert panel.source_combo.currentIndex() == 0


class TestChartSignalAnalysisPanelQuickPlot:
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

    def test_quick_plot_disabled_for_stft(self, panel):
        index = panel.analysis_combo.findData(SignalAnalysisType.STFT)
        panel.analysis_combo.setCurrentIndex(index)

        assert panel.plot_result_cb.isEnabled() is False

    def test_quick_plot_stays_enabled_for_3d_charts(self, panel):
        """See the matching ChartAnalysisPanel test/comment: "New chart" is
        always a valid destination, so the checkbox no longer disables
        based on the current chart's type."""
        panel.current_chart.chart_type = ChartType.SCATTER3D
        panel._populate_sources()

        assert panel.plot_result_cb.isEnabled() is True

    def test_3d_current_chart_is_excluded_from_the_destination_combo(self, panel):
        panel.current_chart.chart_type = ChartType.SCATTER3D
        panel._populate_sources()

        labels = [panel.plot_target_combo.itemText(i) for i in range(panel.plot_target_combo.count())]
        assert labels == ["➕ New chart"]

    def test_cached_add_results_creates_a_new_chart_by_default(self, panel, app_context):
        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.last_result = Mock()
        panel._last_run_params = panel._get_dispatch_params()

        panel.add_results_to_project()

        assert executor.execute_command.called
        cmd = executor.execute_command.call_args[0][0]
        assert isinstance(cmd, CompositeCommand)
        assert len(cmd.commands) == 2
        assert isinstance(cmd.commands[0], ApplySignalAnalysisResultCommand)
        assert isinstance(cmd.commands[1], CreateChartWithAnalysisSeriesCommand)

    def test_cached_add_results_plots_on_the_selected_existing_chart(self, panel, app_context, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.last_result = Mock()
        panel._last_run_params = panel._get_dispatch_params()

        panel.add_results_to_project()

        cmd = executor.execute_command.call_args[0][0]
        add_series_cmd = cmd.commands[1]
        assert isinstance(add_series_cmd, AddAnalysisSeriesCommand)
        assert add_series_cmd.chart_id == "chart-2"

    def test_cached_add_results_executes_single_command_when_quick_plot_unchecked(self, panel, app_context):
        executor = Mock()
        app_context.get_command_executor.return_value = executor
        executor.execute_command.return_value = True

        panel.last_result = Mock()
        panel._last_run_params = panel._get_dispatch_params()
        panel.plot_result_cb.setChecked(False)

        panel.add_results_to_project()

        assert executor.execute_command.called
        cmd = executor.execute_command.call_args[0][0]
        assert isinstance(cmd, ApplySignalAnalysisResultCommand)

    def test_async_add_completes_when_its_own_quick_plot_fires_chart_updated(self, panel):
        """Regression: the composite command an in-flight (non-cached)
        add_results_to_project() dispatch executes -- when quick-plot is
        enabled -- fires CHART_UPDATED("series_added") synchronously via
        AddAnalysisSeriesCommand's AddSeriesCommand, strictly before
        on_complete runs (see ChartSignalAnalysisCommand._on_commit_computed()).
        That used to bump _generation like any other chart update, so the
        completion's own staleness check always saw a moved-on generation
        and silently discarded its own successful result."""
        command = Mock()
        command.result = Mock()
        command.plot_result = True
        command.plot_target_chart_id = panel.current_chart_id  # plotting on the current chart
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()
        assert panel._pending_quick_plot is True

        panel._on_chart_updated({"chart": panel.current_chart, "update_type": "series_added"})
        assert panel._pending_quick_plot is True  # deferred, not consumed yet
        assert len(panel._deferred_chart_updates) == 1

        command.on_complete(CommandResult.SUCCESS)

        # on_complete's own success branch runs first and displays the
        # result, but the queued event is then replayed for real (the new
        # mechanism can no longer special-case "this was our own event" --
        # see _on_chart_updated()) -- so the replay's own _populate_sources()
        # call invalidates last_result again immediately afterwards. The
        # success message it left behind is unaffected, and nothing is left
        # dangling in the queue.
        assert panel.last_result is None
        assert "added to project" in panel.results_text.toPlainText()
        assert panel._deferred_chart_updates == []

    def test_async_add_still_discards_an_unrelated_series_added_mid_flight(self, panel):
        """The suppression above must not swallow a genuinely unrelated
        series_added (e.g. another panel adding a series, or an undo of an
        earlier removal) that happens to arrive while a plot_result=False
        dispatch is in flight -- only a dispatch that actually enabled
        quick-plot gets this leniency."""
        command = Mock()
        command.result = Mock()
        command.plot_result = False
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()
        assert panel._pending_quick_plot is False

        panel._on_chart_updated({"chart": panel.current_chart, "update_type": "series_added"})

        command.on_complete(CommandResult.SUCCESS)

        assert panel.last_result is None
        assert "added to project" not in panel.results_text.toPlainText()

    def test_pending_quick_plot_cleared_on_synchronous_dispatch_failure(self, panel):
        """Regression: on_complete never runs for a dispatch that fails
        synchronous validation (execute_command() returns False before any
        computation starts), so it never got a chance to clear
        _pending_quick_plot either -- leaving a stale True that would make
        the next, genuinely unrelated series_added event skip invalidation
        as if it belonged to this (failed, never-actually-dispatched)
        commit."""
        command = Mock()
        command.plot_result = True
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: False
        panel._build_command = lambda: command

        panel.add_results_to_project()

        assert panel._pending_quick_plot is False

    def test_build_command_forwards_selected_destination(self, panel):
        index = panel.plot_target_combo.findData(None)  # "New chart" (already selected, but explicit)
        panel.plot_target_combo.setCurrentIndex(index)

        command = panel._build_command()

        assert command.plot_result is True
        assert command.plot_target_chart_id is None

    def test_build_command_forwards_an_existing_chart_destination(self, panel, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        command = panel._build_command()

        assert command.plot_result is True
        assert command.plot_target_chart_id == "chart-2"

    def test_tab_changed_is_deferred_during_an_in_flight_new_chart_quick_plot(self, panel):
        """Regression: CreateChartCommand (run when the "New chart"
        destination is used) emits CHART_CREATED synchronously, and
        TabContainer reacts to that by auto-opening and activating the new
        chart's tab -- synchronously, before this dispatch's own
        on_complete runs. _on_tab_changed() used to unconditionally
        reassign current_chart_id to that just-created chart and bump
        _generation via _populate_sources(), which made on_complete's own
        staleness check discard its own successful result.

        The fix defers the tab change instead of dropping it: on_complete
        must still see its own untouched dispatch-time context (so the
        success message displays), but once it has made its display
        decision, the deferred tab change should be replayed so the panel
        ends up bound to the chart the app's active tab actually switched
        to, rather than staying stuck on the old context indefinitely."""
        command = Mock()
        command.result = Mock()
        command.plot_result = True
        command.plot_target_chart_id = None  # "New chart"
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()
        assert panel._pending_quick_plot is True

        # Simulate TabContainer auto-opening the newly created chart's tab,
        # reentrantly, before on_complete runs. With the fix this is
        # deferred rather than dropped or applied immediately -- it doesn't
        # even need "new-chart-id" to exist in the project fixture.
        panel._on_tab_changed({"tab_type": "chart", "tab_id": "new-chart-id"})
        assert panel.current_chart_id == "chart-1"  # not yet applied

        command.on_complete(CommandResult.SUCCESS)

        assert "added to project" in panel.results_text.toPlainText()
        assert panel.current_chart_id == "new-chart-id"  # replayed after on_complete settled
        assert panel._deferred_tab_change is None  # consumed

    def test_deferred_tab_change_replays_after_a_stale_discarded_completion(self, panel):
        """The deferred-replay mechanism must fire even when on_complete
        discards its own result as stale -- not only on the success path."""
        command = Mock()
        command.plot_result = True
        command.plot_target_chart_id = None
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()

        panel._on_tab_changed({"tab_type": "chart", "tab_id": "new-chart-id"})
        assert panel._deferred_tab_change is not None

        # Make the dispatch parameters change mid-flight so on_complete
        # takes the "stale, discard" branch instead of the success branch.
        peaks_index = panel.analysis_combo.findData(SignalAnalysisType.PEAKS)
        panel.analysis_combo.setCurrentIndex(peaks_index)

        command.on_complete(CommandResult.SUCCESS)

        assert panel._deferred_tab_change is None
        assert panel.current_chart_id == "new-chart-id"

    def test_deferred_tab_change_replays_after_synchronous_dispatch_failure(self, panel):
        """A tab change arriving reentrantly during execute_command() itself
        (mirroring the CreateChartCommand/CHART_CREATED reentrancy the
        success-path test above exercises) -- before execute_command()
        returns False -- must still be replayed once the failure branch
        clears _pending_quick_plot, not dropped."""
        command = Mock()
        command.plot_result = True
        command.plot_target_chart_id = None

        def _fail(cmd):
            panel._on_tab_changed({"tab_type": "chart", "tab_id": "new-chart-id"})
            return False

        panel.app_context.get_command_executor.return_value.execute_command = _fail
        panel._build_command = lambda: command

        panel.add_results_to_project()

        assert panel._deferred_tab_change is None
        assert panel.current_chart_id == "new-chart-id"

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

    def test_destination_combo_refreshes_when_a_different_chart_is_moved(self, panel, project):
        from pandaplot.models.project.items.folder import Folder
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        dest_folder = Folder(id="f-dest", name="Dest")
        project.add_item(dest_folder)
        project.remove_item(other_chart)
        project.add_item(other_chart, parent_id="f-dest")
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.plot_target_combo.currentData() == "chart-2"

    def test_destination_combo_falls_back_to_new_chart_when_selected_destination_is_removed(self, panel, project):
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)
        panel._populate_sources()
        index = panel.plot_target_combo.findData("chart-2")
        panel.plot_target_combo.setCurrentIndex(index)

        project.remove_item_by_id("chart-2")
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.plot_target_combo.currentData() is None

    def test_chart_updated_on_current_chart_is_deferred_and_still_invalidates_when_destination_is_a_different_chart(
        self, panel, project
    ):
        """The dispatch's real destination is a different existing chart
        (chart-2), but an unrelated CHART_UPDATED lands on the current
        chart (chart-1) while the dispatch is in flight. The new mechanism
        can't distinguish "this dispatch's own event" from a genuinely
        unrelated one once more than one such event for the same chart can
        arrive in the same window, so it defers ALL of them -- nothing is
        lost, and normal invalidation still runs, just after on_complete
        has made its own display decision instead of immediately."""
        other_chart = Chart(id="chart-2", name="Other", chart_type=ChartType.LINE)
        project.add_item(other_chart)

        command = Mock()
        command.result = Mock()
        command.plot_result = True
        command.plot_target_chart_id = "chart-2"  # NOT the current chart ("chart-1")
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()
        assert panel._pending_quick_plot is True

        generation_before = panel._generation
        # An unrelated series_added lands on the CURRENT chart, not chart-2.
        panel._on_chart_updated({"chart": panel.current_chart, "update_type": "series_added"})

        assert panel._generation == generation_before  # deferred, not yet applied
        assert len(panel._deferred_chart_updates) == 1

        command.on_complete(CommandResult.SUCCESS)

        assert panel._generation > generation_before  # replayed -- invalidation still ran
        assert panel._deferred_chart_updates == []

    def test_deferred_chart_update_replays_after_a_stale_discarded_completion(self, panel):
        """The deferred-chart-update replay must fire even when on_complete
        discards its own result as stale -- not only when it displays it."""
        command = Mock()
        command.plot_result = True
        command.plot_target_chart_id = panel.current_chart_id
        panel.app_context.get_command_executor.return_value.execute_command = lambda cmd: True
        panel._build_command = lambda: command
        panel.add_results_to_project()

        panel._on_chart_updated({"chart": panel.current_chart, "update_type": "series_added"})
        assert len(panel._deferred_chart_updates) == 1

        # Make the dispatch parameters change mid-flight so on_complete
        # takes the "stale, discard" branch instead of the success branch.
        peaks_index = panel.analysis_combo.findData(SignalAnalysisType.PEAKS)
        panel.analysis_combo.setCurrentIndex(peaks_index)

        generation_before = panel._generation
        command.on_complete(CommandResult.SUCCESS)

        assert panel._deferred_chart_updates == []
        assert panel._generation > generation_before

    def test_deferred_chart_update_replays_after_synchronous_dispatch_failure(self, panel):
        command = Mock()
        command.plot_result = True
        command.plot_target_chart_id = panel.current_chart_id

        def _fail(cmd):
            panel._on_chart_updated({"chart": panel.current_chart, "update_type": "series_added"})
            return False

        panel.app_context.get_command_executor.return_value.execute_command = _fail
        panel._build_command = lambda: command

        generation_before = panel._generation
        panel.add_results_to_project()

        assert panel._deferred_chart_updates == []
        assert panel._generation > generation_before
