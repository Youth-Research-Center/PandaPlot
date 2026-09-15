"""Tests for PanelSetupManager.register_default_panels().

Every panel class register_default_panels() constructs is patched out with a
plain Mock -- constructing the real widgets needs a live AppContext/QWidget
tree that is irrelevant to verifying which (name, icon, visibility_condition)
tuples get registered, and is already covered by each panel's own tests.
"""
from unittest.mock import Mock, patch

from pandaplot.gui.components.sidebar.panels.panel_conditions import (
    is_chart_tab_active,
    is_dataset_tab_active,
)
from pandaplot.gui.components.sidebar.panels.panel_setup_manager import PanelSetupManager

_PATCHED_PANEL_CLASSES = [
    "ProjectViewPanel",
    "SearchPanel",
    "TransformPanel",
    "PreprocessingPanel",
    "AnalysisPanel",
    "DescriptiveStatsPanel",
    "StatisticsPanel",
    "SignalPanel",
    "ChartPropertiesPanel",
    "FitPanel",
    "ChartAnalysisPanel",
    "ChartSignalAnalysisPanel",
    "ChartTransformPanel",
]


def _register_with_patched_panels():
    patchers = [
        patch(f"pandaplot.gui.components.sidebar.panels.panel_setup_manager.{name}", return_value=Mock())
        for name in _PATCHED_PANEL_CLASSES
    ]
    for patcher in patchers:
        patcher.start()
    try:
        manager = PanelSetupManager(app_context=Mock())
        manager.register_default_panels()
        return manager
    finally:
        for patcher in patchers:
            patcher.stop()


def test_register_default_panels_registers_chart_signal_panel_for_chart_tabs():
    manager = _register_with_patched_panels()

    by_name = {info["name"]: info for info in manager.panels}
    assert "chart_signal" in by_name
    assert by_name["chart_signal"]["icon"] == "📡"
    assert by_name["chart_signal"]["visibility_condition"] is is_chart_tab_active


def test_register_default_panels_registers_all_expected_panel_names():
    manager = _register_with_patched_panels()

    names = [info["name"] for info in manager.panels]
    assert names == [
        "explorer",
        "search",
        "transform",
        "preprocessing",
        "analysis",
        "descriptive",
        "statistics",
        "signal",
        "chart_properties",
        "fit",
        "chart_analysis",
        "chart_signal",
        "chart_transform",
    ]
    # Sanity check on a couple of the pre-existing entries, to make sure the
    # patched-class trick above is exercising the real registration order/
    # conditions rather than silently short-circuiting it.
    by_name = {info["name"]: info for info in manager.panels}
    assert by_name["signal"]["visibility_condition"] is is_dataset_tab_active
    assert by_name["chart_analysis"]["visibility_condition"] is is_chart_tab_active
