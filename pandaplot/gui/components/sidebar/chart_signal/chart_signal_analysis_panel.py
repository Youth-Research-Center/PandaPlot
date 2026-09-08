"""
Chart Signal Analysis panel.

Runs a signal analysis (FFT/STFT/PSD/Autocorrelation/Peak detection) on any
series of the active chart -- a plotted data series or a fitted curve --
optionally restricted to a segment, and stores the result as a new dataset.

Modeled on two sibling panels:
- ChartAnalysisPanel (pandaplot/gui/components/sidebar/chart_analysis/
  chart_analysis_panel.py) for the chart-context plumbing: the series/fit
  source picker and the segment (index range) section.
- SignalPanel (pandaplot/gui/components/sidebar/signal/signal_panel.py) for
  the async run/apply interaction pattern: a busy spinner, mutually
  exclusive Run/Add-to-Project dispatch, and reusing a cached preview result
  when nothing has changed since the last successful Run.
"""

from typing import Optional, override

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pandaplot.analysis import SIGNAL_ANALYSES, SignalAnalysisResult, SignalAnalysisType
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart.chart_signal_analysis_command import (
    ChartSignalAnalysisCommand,
)
from pandaplot.commands.project.chart.create_chart_with_analysis_series_command import (
    build_quick_plot_command,
)
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.gui.components.common.busy_spinner import BusySpinner
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.chart.series_source_picker import (
    find_series_fit_combo_index,
    populate_chart_target_combo,
    populate_series_fit_sources,
    series_source_hint,
)
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.gui.components.sidebar.signal.signal_panel import SignalPanel
from pandaplot.gui.components.sidebar.signal.signal_parameter_widgets import (
    build_signal_parameter_widgets,
)
from pandaplot.models.events import ChartEvents, DatasetEvents, UIEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartSignalAnalysisPanel(SidebarPanel):
    """Side panel for signal analysis operations on chart data/fit series."""

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)

        self.current_chart: Optional[Chart] = None
        self.current_chart_id: Optional[str] = None

        self.last_result: Optional[SignalAnalysisResult] = None
        self._last_run_params = None
        self._pending_command = None

        # Set while an in-flight add_results_to_project() dispatch has
        # quick-plot enabled, so _on_chart_updated() can recognize the
        # CHART_UPDATED("series_added") that dispatch's own composite
        # command (apply + AddAnalysisSeriesCommand) fires as it completes,
        # and not mistake its own result for an external, invalidating
        # chart edit. See _on_chart_updated()'s docstring.
        self._pending_quick_plot = False

        # The actual destination chart id of the in-flight
        # add_results_to_project() dispatch tracked by _pending_quick_plot
        # above (mirrors command.plot_target_chart_id), or None for the
        # "new chart" destination. Lets _on_chart_updated() only treat a
        # series_added on the *current* chart as this dispatch's own
        # expected event when the current chart is actually that dispatch's
        # target -- an unrelated series_added landing on the current chart
        # while a dispatch targeting some other existing chart is in flight
        # must still invalidate normally.
        self._pending_plot_target_chart_id: Optional[str] = None

        # Cache for _range_command(): a fresh ChartSignalAnalysisCommand
        # per call would re-run NaN-drop/to_numeric series resolution on
        # every call even though the underlying series hasn't changed --
        # reusing one instance per (chart, source) lets its own
        # _resolved_xy_cache actually pay off across the segment-label and
        # sampling-rate-default refreshes that both run on every spinbox tick.
        self._range_command_key = None
        self._range_command_cache: Optional[ChartSignalAnalysisCommand] = None

        # Bumped by _populate_sources() (tab change, chart update, or a
        # backing-dataset edit) -- an in-flight preview/commit captures the
        # generation at dispatch time and discards its result if this has
        # moved on by the time it completes, since the underlying data may
        # have changed even when the dispatch parameters (chart/source/
        # method/segment/...) themselves did not.
        self._generation = 0

        self._initialize()

    @override
    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("📡 Chart Signal Analysis")

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self._create_source_section(layout)
        self._create_method_section(layout)
        self._create_parameters_section(layout)
        self._create_range_section(layout)
        self._create_results_section(layout)
        self._create_action_buttons(layout)
        layout.addStretch()

        self._set_content(content_widget, scrollable=True)

        self._connect_signals()
        self._on_analysis_changed()

    # -- sections -----------------------------------------------------------

    def _create_source_section(self, layout):
        group = QGroupBox("Series")
        form = QFormLayout(group)
        self.source_combo = QComboBox()
        form.addRow("Analyze:", self.source_combo)
        self.source_hint = QLabel("Data series and fitted curves of this chart.")
        self.source_hint.setWordWrap(True)
        form.addRow(self.source_hint)
        layout.addWidget(group)

    def _create_method_section(self, layout):
        group = QGroupBox("Method")
        form = QFormLayout(group)

        self.analysis_combo = QComboBox()
        for analysis_type, info in SIGNAL_ANALYSES.items():
            self.analysis_combo.addItem(info.label, analysis_type)
        form.addRow("Method:", self.analysis_combo)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        form.addRow("", self.description_label)

        layout.addWidget(group)

    def _create_parameters_section(self, layout):
        self.parameters_group = QGroupBox("Parameters")
        self.parameters_layout = QFormLayout(self.parameters_group)
        layout.addWidget(self.parameters_group)

    def _create_range_section(self, layout):
        group = QGroupBox("Segment (index range)")
        form = QFormLayout(group)

        self.start_index = QSpinBox()
        self.start_index.setMinimum(0)
        self.start_index.setMaximum(0)
        self.start_value_label = QLabel("–")
        start_row = QHBoxLayout()
        start_row.addWidget(self.start_index)
        start_row.addWidget(self.start_value_label)
        form.addRow("Start index:", start_row)

        self.end_index = QSpinBox()
        self.end_index.setMinimum(0)
        self.end_index.setMaximum(0)
        self.end_value_label = QLabel("–")
        end_row = QHBoxLayout()
        end_row.addWidget(self.end_index)
        end_row.addWidget(self.end_value_label)
        form.addRow("End index:", end_row)

        layout.addWidget(group)

    def _create_results_section(self, layout):
        group = QGroupBox("Results")
        vbox = QVBoxLayout(group)

        self.run_btn = PButton("Run", role="secondary", on_click=self.run_analysis)
        vbox.addWidget(self.run_btn)

        self.busy_spinner = BusySpinner()
        vbox.addWidget(self.busy_spinner)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Run analysis to see results...")
        vbox.addWidget(self.results_text)

        layout.addWidget(group)

    def _create_action_buttons(self, layout):
        self.plot_result_cb = QCheckBox("Plot result")
        self.plot_result_cb.setChecked(True)
        layout.addWidget(self.plot_result_cb)

        self.plot_target_row = QWidget()
        target_row_layout = QHBoxLayout(self.plot_target_row)
        target_row_layout.setContentsMargins(0, 0, 0, 0)
        target_row_layout.addWidget(QLabel("Plot on:"))
        self.plot_target_combo = QComboBox()
        target_row_layout.addWidget(self.plot_target_combo)
        layout.addWidget(self.plot_target_row)

        row = QHBoxLayout()
        self.add_btn = PButton(
            "Add to Project", role="primary", on_click=self.add_results_to_project, enabled=False
        )
        self.clear_btn = PButton("Clear", role="secondary", on_click=self.clear)
        row.addWidget(self.add_btn)
        row.addWidget(self.clear_btn)
        layout.addLayout(row)

    def _connect_signals(self):
        self.analysis_combo.currentIndexChanged.connect(self._on_analysis_changed)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.start_index.valueChanged.connect(self._on_segment_changed)
        self.end_index.valueChanged.connect(self._on_segment_changed)
        self.plot_result_cb.toggled.connect(self._update_plot_target_visibility)

    # -- dynamic parameters ---------------------------------------------------

    def _on_analysis_changed(self):
        analysis_type = self.analysis_combo.currentData()
        if analysis_type is None:
            return

        info = SIGNAL_ANALYSES[analysis_type]
        self.description_label.setText(info.description)

        self._build_parameter_widgets(info)
        self._refresh_sampling_rate_default()
        self._update_quick_plot_compatibility(has_sources=self.source_combo.count() > 0)
        self.clear()

    def _build_parameter_widgets(self, info):
        while self.parameters_layout.count():
            item = self.parameters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # reset references
        self.sampling_rate = None
        self.nfft_spin = None
        self.window_combo = None
        self.nperseg_spin = None
        self.overlap_spin = None

        self.height_spin = None
        self.distance_spin = None
        self.prominence_spin = None
        self.threshold_spin = None

        widgets = build_signal_parameter_widgets(self.parameters_layout, info)

        self.sampling_rate = widgets.get("sampling_rate")
        self.nfft_spin = widgets.get("nfft")
        self.window_combo = widgets.get("window")
        self.nperseg_spin = widgets.get("nperseg")
        self.overlap_spin = widgets.get("overlap")

        self.height_spin = widgets.get("height")
        self.distance_spin = widgets.get("distance")
        self.prominence_spin = widgets.get("prominence")
        self.threshold_spin = widgets.get("threshold")

    # -- sampling-rate pre-fill ----------------------------------------------

    def _refresh_sampling_rate_default(self):
        """Recompute the sampling-rate spinbox's default value as
        ``1 / median(diff(x))`` over the currently selected segment's x
        values, whenever the source or segment range changes. The field
        stays user-editable in between -- this is only called from source/
        segment change handlers, never from the sampling-rate spinbox's own
        valueChanged, so a value the user is actively editing is never
        clobbered outside of those triggers."""
        if getattr(self, "sampling_rate", None) is None:
            return

        source = self._selected_source()
        if source is None:
            return
        command = self._range_command(*source)
        if command is None:
            return

        start = self.start_index.value()
        end = self.end_index.value() + 1  # inclusive UI end -> exclusive boundary
        x_segment = command.resolve_segment_x(start, end)
        if x_segment is None or len(x_segment) < 2:
            return

        # Sampling interval is a magnitude -- np.abs() so a descending (or
        # mixed-direction) x axis still yields a usable estimate instead of
        # every diff coming back negative and getting filtered out entirely.
        # resolve_series_xy() coerces non-numeric x values to NaN rather than
        # dropping them, so a single such value produces a NaN diff -- filter
        # non-finite diffs out too, or np.median (and the sampling-rate
        # spinbox) would silently end up NaN instead of using the remaining
        # valid spacings.
        diffs = np.abs(np.diff(x_segment.to_numpy()))
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if len(diffs) == 0:
            return

        median_diff = float(np.median(diffs))
        if median_diff <= 0:
            return

        self.sampling_rate.setValue(1.0 / median_diff)

    # -- config ---------------------------------------------------------------

    def _selected_source(self):
        """Return (kind, index) for the selected series, or None."""
        return self.source_combo.currentData()

    def _current_analysis_type(self) -> Optional[SignalAnalysisType]:
        return self.analysis_combo.currentData()

    def _build_parameters(self) -> dict:
        params: dict = {
            "start_index": self.start_index.value(),
            # end_index shown in the UI is the last included point; the
            # engine takes an exclusive slice boundary.
            "end_index": self.end_index.value() + 1,
        }

        if self.nfft_spin:
            params["nfft"] = self.nfft_spin.value()
        if self.window_combo:
            params["window"] = self.window_combo.currentText()
        if self.nperseg_spin:
            params["nperseg"] = self.nperseg_spin.value()
        if self.overlap_spin:
            params["overlap"] = self.overlap_spin.value()
        if self.height_spin:
            params["height"] = self.height_spin.value()
        if self.distance_spin:
            params["distance"] = self.distance_spin.value()
        if self.prominence_spin:
            params["prominence"] = self.prominence_spin.value()
        if self.threshold_spin:
            params["threshold"] = self.threshold_spin.value()

        return params

    def _get_dispatch_params(self):
        source = self._selected_source()
        if source is None or self.current_chart_id is None:
            return None
        kind, index = source

        return (
            self.current_chart_id,
            kind,
            index,
            self._current_analysis_type(),
            self.sampling_rate.value() if self.sampling_rate else None,
            self._build_parameters(),
        )

    def _build_command(self) -> Optional[ChartSignalAnalysisCommand]:
        params = self._get_dispatch_params()
        if params is None:
            return None

        chart_id, kind, index, analysis_type, sampling_rate, parameters = params
        folder_id = self.current_chart.parent_id if self.current_chart else None
        plot_result = self.plot_result_cb.isChecked() and self.plot_result_cb.isEnabled()
        return ChartSignalAnalysisCommand(
            self.app_context,
            chart_id=chart_id,
            source_kind=kind,
            source_index=index,
            analysis_type=analysis_type,
            sampling_rate=sampling_rate,
            parameters=parameters,
            folder_id=folder_id,
            plot_result=plot_result,
            plot_target_chart_id=self.plot_target_combo.currentData() if plot_result else None,
        )

    # -- async run/apply dispatch (mirrors SignalPanel) ------------------------

    def run_analysis(self):
        # Run and "Add to Project" share one busy spinner and one
        # _pending_command slot -- letting both run at once would have
        # whichever finishes first stop the spinner and clear the other's
        # still-active reference out from under it, so treat them as mutually
        # exclusive rather than tracking two independent in-flight jobs.
        if self._pending_command is not None:
            return

        command = self._build_command()
        if command is None:
            return

        # Tab/source/method/segment navigation stays enabled while a preview
        # computes in the background -- capture what was actually requested
        # so a stale completion (any of those changed mid-flight, or the
        # chart/its backing dataset changed underneath without changing the
        # dispatch parameters themselves) can be discarded instead of
        # overwriting whatever the panel now shows.
        dispatch_params = self._get_dispatch_params()
        dispatch_generation = self._generation

        self.run_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.busy_spinner.start()
        self._pending_command = command  # keep alive until on_complete fires

        def _on_complete(result, error):
            self.busy_spinner.stop()
            # Restore Run from the current source context rather than
            # unconditionally re-enabling it -- the user may have navigated
            # to a chart/tab with no eligible source while this was running.
            self.run_btn.setEnabled(self.source_combo.count() > 0)
            self._pending_command = None

            if self._generation != dispatch_generation or self._get_dispatch_params() != dispatch_params:
                self.logger.info(
                    "Discarding stale chart signal analysis preview: dispatch parameters changed."
                )
                return

            if error is not None:
                self.last_result = None
                self._last_run_params = None
                self.add_btn.setEnabled(False)
                self.results_text.setText(f"❌ Analysis failed:\n{error}")
                return

            self.last_result = result
            self._last_run_params = dispatch_params
            try:
                self.results_text.setText(SignalPanel._format_result(result))
                self.add_btn.setEnabled(True)
            except Exception as e:
                self.last_result = None
                self._last_run_params = None
                self.add_btn.setEnabled(False)
                self.results_text.setText(f"❌ Analysis failed:\n{e}")

        command.run_analysis_async(_on_complete)

    def add_results_to_project(self):
        # See the matching guard/comment in run_analysis(): Run and Add
        # share one spinner and one _pending_command slot, so they must not
        # both be in flight at once.
        if self._pending_command is not None:
            return

        current_params = self._get_dispatch_params()
        if current_params is None:
            return

        # If parameters are unchanged since the last successful Run preview,
        # commit self.last_result directly without re-computing on a
        # background thread.
        if self.last_result is not None and self._last_run_params == current_params:
            folder_id = self.current_chart.parent_id if self.current_chart else None
            apply_command = ApplySignalAnalysisResultCommand(
                app_context=self.app_context,
                result_name=None,
                folder_id=folder_id,
                result=self.last_result,
            )
            executor = self.app_context.get_command_executor()
            if self.plot_result_cb.isChecked() and self.plot_result_cb.isEnabled():
                plot_command = build_quick_plot_command(
                    self.app_context,
                    apply_command,
                    target_chart_id=self.plot_target_combo.currentData(),
                    folder_id=folder_id,
                )
                success = executor.execute_command(CompositeCommand([apply_command, plot_command]))
            else:
                success = executor.execute_command(apply_command)

            if success:
                self.results_text.append("\n\n✅ Results added to project")
                self.add_btn.setEnabled(False)
            else:
                self.add_btn.setEnabled(True)
            return

        command = self._build_command()
        if command is None:
            return

        # See the matching capture/comment in run_analysis(): the commit
        # itself already happened for real (the dataset was created in the
        # project regardless of what the panel shows by the time it
        # completes), but the *display* of that outcome belongs to whatever
        # dispatch parameters are current now -- skip it if any changed.
        dispatch_generation = self._generation

        self.run_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.busy_spinner.start()
        self._pending_command = command
        self._pending_quick_plot = command.plot_result
        self._pending_plot_target_chart_id = command.plot_target_chart_id

        def _on_complete(result):
            self.busy_spinner.stop()
            # Restore Run from the current source context rather than
            # unconditionally re-enabling it -- see the matching comment in
            # run_analysis().
            self.run_btn.setEnabled(self.source_combo.count() > 0)
            self._pending_command = None
            # The one benign self-caused CHART_UPDATED this dispatch could
            # produce (see _on_chart_updated()) has either already arrived
            # and been consumed, or -- on failure -- was never going to
            # arrive at all; either way, don't let a stale True suppress
            # invalidation for some later, unrelated series_added.
            self._pending_quick_plot = False
            self._pending_plot_target_chart_id = None

            if self._generation != dispatch_generation or self._get_dispatch_params() != current_params:
                self.logger.info(
                    "Not displaying chart signal analysis commit result: dispatch parameters changed."
                )
                return

            if result is CommandResult.SUCCESS:
                self.last_result = command.result
                self._last_run_params = current_params
                self.results_text.append("\n\n✅ Results added to project")
            else:
                self.add_btn.setEnabled(True)  # let the user retry

        command.on_complete = _on_complete
        executor = self.app_context.get_command_executor()
        if not executor.execute_command(command):
            # Synchronous validation failure -- on_complete never fires, so
            # it never gets a chance to clear _pending_quick_plot either;
            # do it here or a later, genuinely unrelated series_added would
            # be mistaken for this (failed, never-dispatched) commit's own
            # event and wrongly skip invalidation.
            self.busy_spinner.stop()
            self.run_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self._pending_command = None
            self._pending_quick_plot = False
            self._pending_plot_target_chart_id = None

    def clear(self):
        if hasattr(self, "results_text"):
            self.results_text.clear()

        self.last_result = None
        self._last_run_params = None
        if hasattr(self, "add_btn"):
            self.add_btn.setEnabled(False)
        # Don't stop the busy spinner while a Run/Add computation is still
        # in flight (this is called from the Clear button and from every
        # analysis-method change) -- it must keep reflecting that until the
        # completion callback clears _pending_command; stopping it here
        # would make the panel look idle while Run/Add still silently
        # no-op via the _pending_command guard.
        if self._pending_command is None and hasattr(self, "busy_spinner"):
            self.busy_spinner.stop()

    # -- chart context --------------------------------------------------------

    def _range_command(self, kind: str, index: int) -> Optional[ChartSignalAnalysisCommand]:
        """Return a command to resolve the selected series, reused across
        calls for the same (chart, source) so its _resolved_xy_cache
        actually amortizes the NaN-drop/to_numeric resolution work.

        Used for the segment bounds, index -> (x, y) previews, and the
        sampling-rate default, so all three stay in sync with what will
        actually be analyzed -- a data series' raw row count can be larger
        once rows with missing x/y are dropped. Any analysis_type works
        here since it's only used for source_length()/resolve_point()/
        resolve_segment_x().
        """
        if self.current_chart is None or self.current_chart_id is None:
            return None
        key = (self.current_chart_id, kind, index)
        if self._range_command_key != key:
            self._range_command_cache = ChartSignalAnalysisCommand(
                self.app_context,
                chart_id=self.current_chart_id,
                source_kind=kind,
                source_index=index,
                analysis_type=SignalAnalysisType.FFT,
            )
            self._range_command_key = key
        return self._range_command_cache

    def _series_length(self, kind: str, index: int) -> int:
        """Best-effort length of a source series, for the segment bounds."""
        command = self._range_command(kind, index)
        return command.source_length() if command else 0

    def _on_source_changed(self):
        source = self._selected_source()
        if source is None:
            last = 0
        else:
            last = max(self._series_length(*source) - 1, 0)
        self.start_index.setMaximum(last)
        self.end_index.setMaximum(last)
        # Default to the whole series -- start at the first point, end at
        # the last -- whenever the source changes, since a previous value
        # may no longer make sense against the new series' length.
        # setMaximum() alone only clamps an out-of-range start down to
        # `last` (not up to 0), which left a nonzero start from a longer
        # previous source retained -- or, if it exceeded the new shorter
        # source's last index, clamped to a degenerate one-point segment
        # (start == end == last) rather than actually selecting the whole
        # new series.
        self.start_index.setValue(0)
        self.end_index.setValue(last)
        self._update_range_labels()
        self._refresh_sampling_rate_default()

    def _on_segment_changed(self):
        self._update_range_labels()
        self._refresh_sampling_rate_default()

    def _format_point(self, point: Optional[tuple[float, float]]) -> str:
        if point is None:
            return "–"
        x, y = point
        return f"x={x:.4g}, y={y:.4g}"

    def _update_range_labels(self):
        source = self._selected_source()
        command = self._range_command(*source) if source else None
        if command is None:
            self.start_value_label.setText("–")
            self.end_value_label.setText("–")
            return

        self.start_value_label.setText(self._format_point(command.resolve_point(self.start_index.value())))
        self.end_value_label.setText(self._format_point(command.resolve_point(self.end_index.value())))

    def _update_plot_target_visibility(self):
        self.plot_target_row.setVisible(self.plot_result_cb.isChecked() and self.plot_result_cb.isEnabled())

    def _update_quick_plot_compatibility(self, *, has_sources: bool):
        if not has_sources:
            self.plot_result_cb.setEnabled(False)
        else:
            # STFT results are 3-column (time, frequency, magnitude) -- not
            # a single (x, y) curve, so there's nothing sensible to overlay,
            # regardless of destination.
            self.plot_result_cb.setEnabled(self._current_analysis_type() != SignalAnalysisType.STFT)
        self._update_plot_target_visibility()

    def _populate_sources(self, *, invalidate: bool = True):
        # Force _range_command() to build a fresh command even if the
        # (chart, source) key is unchanged: this runs on every
        # UIEvents.TAB_CHANGED/ChartEvents.CHART_UPDATED/dataset change, and
        # those fire on chart/series-backing-dataset mutations that the
        # cached command's _resolved_xy_cache would otherwise keep serving
        # stale data for. Clearing the cached command itself (not just its
        # key) also matters when there's no longer an eligible source at all
        # (chart closed, or repopulated with nothing to analyze) --
        # _range_command() returns None without rebuilding in that case, so
        # leaving the old command object behind would otherwise keep its
        # resolved x/y series (potentially large) referenced for the rest of
        # the panel's lifetime.
        self._range_command_key = None
        self._range_command_cache = None
        if invalidate:
            # A previously computed last_result may have been resolved from
            # data that just changed underneath it (same chart/source/
            # method/segment, different underlying values) -- discard it
            # rather than let Add to Project's cached-result fast path
            # commit a stale analysis. Also bump _generation so an
            # in-flight preview/commit dispatched before this update
            # discards its result on arrival even when its own dispatch
            # parameters still compare equal. Skipped when this refresh is
            # itself the plotted result of an in-flight commit -- see
            # _on_chart_updated().
            self.last_result = None
            self._last_run_params = None
            self._generation += 1
            if hasattr(self, "add_btn"):
                self.add_btn.setEnabled(False)
        has_sources, any_series_excluded = populate_series_fit_sources(self.source_combo, self.current_chart)
        # A tab switch while a Run/Add-to-Project computation is still in
        # flight (for whatever chart/source was previously selected) must
        # not re-enable the Run button -- _pending_command's own guard would
        # silently no-op the click until that computation's on_complete
        # fires and re-enables it for real.
        self.run_btn.setEnabled(has_sources and self._pending_command is None)
        self.source_hint.setText(
            series_source_hint(has_sources=has_sources, any_series_excluded=any_series_excluded)
        )
        project = self.app_context.get_app_state().current_project
        populate_chart_target_combo(self.plot_target_combo, project)
        self._update_quick_plot_compatibility(has_sources=has_sources)
        self._on_source_changed()

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(UIEvents.TAB_CHANGED, self._on_tab_changed)
        self.subscribe_to_event(ChartEvents.CHART_UPDATED, self._on_chart_updated)
        # Chart series/fits read their values live from source datasets, so
        # an edit to one of those datasets (cell edits, added/removed rows
        # or columns, ...) can change the resolved x/y without emitting
        # CHART_UPDATED -- mirrors ChartTab's own subscription for the same
        # reason (see chart_tab.py). DATASET_CHANGED is the generic parent
        # of all those specific dataset events.
        self.subscribe_to_event(DatasetEvents.DATASET_CHANGED, self._on_dataset_changed)
        self.subscribe_to_event(ChartEvents.SERIES_SELECTED, self._on_series_selected_event)

    def _on_series_selected_event(self, event_data):
        """Clicking a series/fit on the chart canvas or its legend also
        selects it here, so switching from "look at it" to "run signal
        analysis on it" doesn't require re-finding the same entry in this
        combo."""
        chart_id = event_data.get("chart_id")
        if self.current_chart_id is None or chart_id != self.current_chart_id:
            return
        kind = event_data.get("kind")
        index = event_data.get("index")
        if kind is None or index is None:
            return
        combo_index = find_series_fit_combo_index(self.source_combo, kind, index)
        if combo_index >= 0:
            self.source_combo.setCurrentIndex(combo_index)

    def _on_tab_changed(self, event_data):
        if self._pending_quick_plot:
            # An in-flight add_results_to_project() dispatch with quick-plot
            # enabled can itself trigger this (see the "New chart" case: its
            # CreateChartCommand emits CHART_CREATED, which TabContainer
            # reacts to by auto-opening and activating the new chart's tab --
            # synchronously, before this dispatch's own on_complete runs).
            # Reassigning current_chart_id here (to the just-created chart)
            # or bumping _generation via _populate_sources() would make
            # on_complete's own staleness check discard its own successful
            # result. Skip entirely for the duration of the pending dispatch --
            # any genuine concurrent tab switch by the user is deferred until
            # the next tab change or _populate_sources() trigger once the
            # dispatch completes and clears this flag.
            return
        if event_data.get("tab_type") == "chart":
            chart_id = event_data.get("tab_id")
            self.current_chart_id = chart_id
            project = self.app_context.get_app_state().current_project
            chart = project.find_item(chart_id) if project and chart_id else None
            self.current_chart = chart if isinstance(chart, Chart) else None
        else:
            self.current_chart = None
            self.current_chart_id = None
        self._populate_sources()

    def _on_chart_updated(self, event_data):
        chart = event_data.get("chart")
        if not chart or (self.current_chart_id and chart.id != self.current_chart_id):
            return
        if isinstance(chart, Chart):
            self.current_chart = chart
            self.current_chart_id = chart.id
            if (
                self._pending_quick_plot
                and self._pending_plot_target_chart_id == self.current_chart_id
                and event_data.get("update_type") == "series_added"
            ):
                # The composite command an in-flight add_results_to_project()
                # dispatched (with quick-plot enabled) fires this very event
                # -- via AddAnalysisSeriesCommand's AddSeriesCommand -- as
                # part of successfully completing *this* dispatch, strictly
                # before its on_complete callback runs (see
                # ChartSignalAnalysisCommand._on_commit_computed()). Treat it
                # as expected progress, not an external edit that
                # invalidates the very analysis it's the result of --
                # otherwise on_complete's generation check below would
                # always see a moved-on generation and silently discard its
                # own successful result. Only the one event a given dispatch
                # can produce is consumed this way (the flag is cleared
                # here, and again unconditionally once on_complete runs) --
                # any other series_added still invalidates normally.
                self._pending_quick_plot = False
                self._populate_sources(invalidate=False)
            else:
                self._populate_sources()

    def _on_dataset_changed(self, event_data):
        changed_dataset_id = event_data.get("dataset_id")
        if changed_dataset_id is None or self.current_chart is None:
            return
        # Only invalidate if this chart actually plots the changed dataset --
        # mirrors ChartTab.on_dataset_changed's own filter.
        if changed_dataset_id in self.current_chart.get_all_datasets():
            self._populate_sources()

    @override
    def showEvent(self, event):
        """Force a refresh whenever this panel becomes the visible sidebar
        panel (PanelArea is a QStackedWidget, and Qt fires this on
        setCurrentWidget()).

        A Chart Properties > Data tab edit to a series' dataset/X/Y/type
        binding mutates the chart live but deliberately emits only a
        `dirtyOnly` signal, not ChartEvents.CHART_UPDATED (see data_tab.py's
        _on_series_config_changed -- routing every keystroke-driven combo
        change through CHART_UPDATED would redraw the chart on every one),
        and switching the active sidebar panel emits nothing at all. Without
        this, a user could edit a series' source in the Data tab, switch to
        this panel, and have Add to Project's cached-result fast path commit
        a preview computed from the pre-edit source. _populate_sources()
        already does exactly the invalidation this scenario needs -- it's
        just never otherwise triggered by either of those two events.
        """
        super().showEvent(event)
        if self.current_chart is not None:
            self._populate_sources()

    # -- theme ------------------------------------------------------------------

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#ffffff")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")

        self.setStyleSheet(f"""
            ChartSignalAnalysisPanel {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 9pt;
                color: {base_fg};
                margin-top: 5px;
                padding-top: 10px;
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: {card_bg};
            }}
        """)

        self._apply_title_theme(base_fg, card_border)

        self.source_hint.setStyleSheet(
            f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        )
        value_label_style = f"QLabel {{ color: {secondary_fg}; background-color: transparent; }}"
        self.start_value_label.setStyleSheet(value_label_style)
        self.end_value_label.setStyleSheet(value_label_style)
        self.plot_result_cb.setStyleSheet(f"QCheckBox {{ color: {base_fg}; background-color: transparent; }}")

        self.results_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {card_bg};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
            }}
        """)
