"""Rebuilt parameter and input fields stay in visual top-to-bottom Tab order (#757)."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget
from pytestqt.qtbot import QtBot

from pandaplot.analysis import AnalysisType, SignalAnalysisType, StatTestType
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart_analysis.chart_analysis_panel import ChartAnalysisPanel
from pandaplot.gui.components.sidebar.chart_signal.chart_signal_analysis_panel import ChartSignalAnalysisPanel
from pandaplot.gui.components.sidebar.signal.signal_panel import SignalPanel
from pandaplot.gui.components.sidebar.statistics.statistics_panel import StatisticsPanel
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.events import DatasetOperationEvents
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset
from tests.gui.panel_inventory import panel_inventory
from tests.gui.theme_testing import design_tokens, surface_palette


def _tab_chain(panel: QWidget) -> list[QWidget]:
    """Walk `nextInFocusChain()` and return every Tab-focusable leaf widget in `panel`."""
    widgets: list[QWidget] = []
    seen: set[int] = set()
    widget = panel.nextInFocusChain()
    while widget is not None and widget is not panel and id(widget) not in seen:
        seen.add(id(widget))
        if (
            panel.isAncestorOf(widget)
            and not isinstance(widget, QScrollArea)
            and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
            and widget.focusProxy() is None
        ):
            widgets.append(widget)
        widget = widget.nextInFocusChain()
    return widgets


def _focus_target(widget: QWidget | None) -> QWidget:
    """Return the widget (or its `focusProxy()`) that actually receives Tab focus."""
    assert widget is not None
    return widget.focusProxy() or widget


@pytest.fixture
def context() -> SimpleNamespace:
    project = Project(name="Tab order")
    time = np.linspace(0.0, 9.9, 100)
    dataset = Dataset(
        id="ds-tab-order",
        name="Measurements",
        data=pd.DataFrame({"time": time, "signal": np.sin(time), "reference": np.cos(time)}),
    )
    project.add_item(dataset)

    chart = Chart(id="chart-tab-order", name="Signal over time", chart_type=ChartType.LINE)
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("signal")
    assert x_id is not None and y_id is not None
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id, label="Signal")
    project.add_item(chart)

    bus = EventBus()
    app_state = SimpleNamespace(has_project=True, current_project=project, event_bus=bus)
    ctx = Mock()
    ctx.event_bus = bus
    ctx.app_state = app_state
    ctx.get_app_state.return_value = app_state
    ctx.get_manager.return_value.get_surface_palette.return_value = surface_palette()
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens()
    return SimpleNamespace(ctx=ctx, bus=bus, project=project, dataset=dataset, chart=chart)


def test_statistics_panel_keeps_rebuilt_inputs_and_parameters_in_tab_order(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = StatisticsPanel(context.ctx)
    qtbot.addWidget(panel)
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": context.dataset.id})

    # Switch test twice: One-sample t -> One-way ANOVA (group list + hint) -> Independent t (2 combos + checkbox).
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(StatTestType.ONE_WAY_ANOVA))
    assert panel.group_list is not None
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.test_type_combo,
        panel.info_btn,
        panel.group_list,
        _focus_target(panel.alpha_spin),
        panel.run_btn,
        panel.results_text,
        panel.add_btn,
        panel.clear_btn,
    ]
    inventory = panel_inventory(panel)
    assert inventory.index('group | "Data Selection" |') < inventory.index(
        'list | "Groups:" | items=["time", "signal", "reference"] selected=["time", "signal"]'
    )
    assert inventory.index(
        'label | "Select 2+ numeric group columns (Ctrl/Shift-click)." |'
    ) < inventory.index('group | "Parameters" |')

    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(StatTestType.INDEPENDENT_T))
    assert len(panel.column_combos) == 2
    assert panel.alternative_combo is not None
    assert panel.equal_var_check is not None
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.test_type_combo,
        panel.info_btn,
        *panel.column_combos,
        _focus_target(panel.alpha_spin),
        panel.alternative_combo,
        panel.equal_var_check,
        panel.run_btn,
        panel.results_text,
        panel.add_btn,
        panel.clear_btn,
    ]

    # Rebuilding only the column pickers on a dataset column change must also preserve their position.
    context.dataset.data["extra"] = 1.0
    context.bus.emit(
        DatasetOperationEvents.DATASET_COLUMN_ADDED,
        {"dataset_id": context.dataset.id, "column_name": "extra"},
    )
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.test_type_combo,
        panel.info_btn,
        *panel.column_combos,
        _focus_target(panel.alpha_spin),
        panel.alternative_combo,
        panel.equal_var_check,
        panel.run_btn,
        panel.results_text,
        panel.add_btn,
        panel.clear_btn,
    ]


def test_signal_panel_keeps_rebuilt_parameters_in_tab_order(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = SignalPanel(context.ctx)
    qtbot.addWidget(panel)
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": context.dataset.id})

    # Switch method twice: FFT -> Autocorrelation (0 parameters) -> Peak Detection (4 parameters).
    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.AUTOCORRELATION))
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.analysis_combo,
        panel.column_combo,
        panel.run_btn,
        panel.results_text,
        panel.add_btn,
        panel.clear_btn,
    ]

    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.PEAKS))
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.analysis_combo,
        panel.column_combo,
        _focus_target(panel.height_spin),
        _focus_target(panel.distance_spin),
        _focus_target(panel.prominence_spin),
        _focus_target(panel.threshold_spin),
        panel.run_btn,
        panel.results_text,
        panel.add_btn,
        panel.clear_btn,
    ]


def test_chart_signal_panel_keeps_rebuilt_parameters_in_tab_order(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = ChartSignalAnalysisPanel(context.ctx)
    qtbot.addWidget(panel)
    panel._on_tab_changed({"tab_type": "chart", "tab_id": context.chart.id})

    # Switch method twice: FFT -> Autocorrelation (0 parameters) -> PSD Welch (4 parameters).
    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.AUTOCORRELATION))
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.source_combo,
        panel.analysis_combo,
        _focus_target(panel.start_index),
        _focus_target(panel.end_index),
        panel.run_btn,
        panel.results_text,
        panel.plot_result_cb,
        panel.plot_target_combo,
        panel.add_btn,
        panel.clear_btn,
    ]

    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.PSD))
    assert panel.window_combo is not None
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.source_combo,
        panel.analysis_combo,
        _focus_target(panel.sampling_rate),
        panel.window_combo,
        _focus_target(panel.nperseg_spin),
        _focus_target(panel.overlap_spin),
        _focus_target(panel.start_index),
        _focus_target(panel.end_index),
        panel.run_btn,
        panel.results_text,
        panel.plot_result_cb,
        panel.plot_target_combo,
        panel.add_btn,
        panel.clear_btn,
    ]


def test_chart_analysis_panel_keeps_rebuilt_parameters_in_tab_order(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = ChartAnalysisPanel(context.ctx)
    qtbot.addWidget(panel)
    panel._on_tab_changed({"tab_type": "chart", "tab_id": context.chart.id})

    # Switch operation twice: Derivative -> Integral (label only) -> Smoothing (combo + sub-params),
    # then switch smoothing sub-method twice (Savitzky-Golay -> LOWESS -> Rolling mean).
    panel.operation_combo.setCurrentIndex(panel.operation_combo.findData(AnalysisType.INTEGRAL))
    inventory = panel_inventory(panel)
    assert inventory.index('group | "Parameters" |') < inventory.index('label | "Method: Trapezoidal rule" |')
    assert inventory.index('label | "Method: Trapezoidal rule" |') < inventory.index('group | "Segment (index range)" |')

    panel.operation_combo.setCurrentIndex(panel.operation_combo.findData(AnalysisType.SMOOTHING))
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.source_combo,
        panel.operation_combo,
        panel.smooth_method_combo,
        _focus_target(panel.window_length_spin),
        _focus_target(panel.poly_order_spin),
        _focus_target(panel.start_index),
        _focus_target(panel.end_index),
        panel.result_name,
        panel.plot_result_cb,
        panel.plot_target_combo,
        panel.preview_btn,
        panel.preview_text,
        panel.apply_btn,
        panel.clear_btn,
    ]

    panel.smooth_method_combo.setCurrentIndex(panel.smooth_method_combo.findData("lowess"))
    panel.smooth_method_combo.setCurrentIndex(panel.smooth_method_combo.findData("rolling_mean"))
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.source_combo,
        panel.operation_combo,
        panel.smooth_method_combo,
        _focus_target(panel.window_spin),
        _focus_target(panel.start_index),
        _focus_target(panel.end_index),
        panel.result_name,
        panel.plot_result_cb,
        panel.plot_target_combo,
        panel.preview_btn,
        panel.preview_text,
        panel.apply_btn,
        panel.clear_btn,
    ]


def test_analysis_panel_keeps_rebuilt_parameters_in_tab_order(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = AnalysisPanel(context.ctx)
    qtbot.addWidget(panel)
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": context.dataset.id})

    # Switch type twice: Derivative -> Integral -> Smoothing, then sub-method twice.
    panel.analysis_type_combo.setCurrentText("Integral")
    inventory = panel_inventory(panel)
    assert inventory.index('group | "Parameters" |') < inventory.index('label | "Method: Trapezoidal Rule" |')
    assert inventory.index('label | "Method: Trapezoidal Rule" |') < inventory.index('group | "Data Range" |')

    panel.analysis_type_combo.setCurrentText("Smoothing")
    panel.smooth_method_combo.setCurrentText("LOWESS")
    panel.smooth_method_combo.setCurrentText("Rolling Mean")
    assert _tab_chain(panel) == [
        _focus_target(panel.help_button),
        panel.analysis_type_combo,
        panel.x_column_combo,
        panel.y_column_combo,
        panel.smooth_method_combo,
        _focus_target(panel.window_spin),
        _focus_target(panel.start_index),
        _focus_target(panel.end_index),
        panel.result_column_name,
        panel.replace_existing,
        panel.preview_btn,
        panel.preview_text,
        panel.apply_btn,
        panel.clear_btn,
    ]


def test_real_tab_navigation_moves_through_rebuilt_parameters_before_action_buttons(
    qtbot: QtBot, context: SimpleNamespace
) -> None:
    panel = SignalPanel(context.ctx)
    qtbot.addWidget(panel)
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": context.dataset.id})
    panel.resize(360, 700)
    panel.show()
    QApplication.processEvents()

    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.PEAKS))
    panel.analysis_combo.setCurrentIndex(panel.analysis_combo.findData(SignalAnalysisType.FFT))

    panel.column_combo.setFocus()
    QApplication.processEvents()
    assert QApplication.focusWidget() is panel.column_combo

    visited: list[QWidget | None] = []
    for _ in range(4):
        assert panel.focusNextPrevChild(True)  # noqa: FBT003 -- Qt bound method, positional-only
        visited.append(QApplication.focusWidget())

    assert visited == [
        _focus_target(panel.sampling_rate),
        _focus_target(panel.nfft_spin),
        panel.window_combo,
        panel.run_btn,
    ]
