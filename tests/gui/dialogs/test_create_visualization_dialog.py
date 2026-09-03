"""Tests for CreateVisualizationDialog: which branch it builds (chart list
present or not) and what each interaction does. "Create Chart" is always
offered regardless of branch, unlike ExploreDataDialog's either/or.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from pandaplot.gui.dialogs.create_visualization_dialog import CreateVisualizationDialog
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart
from pandaplot.models.project.items.folder import Folder


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_dialog(app_context, on_create_chart=None):
    return CreateVisualizationDialog(
        app_context, on_create_chart=on_create_chart or Mock(), parent=None
    )


def _chart(name="Sales Trend", chart_type="line", series=0):
    chart = Chart(name=name, chart_type=chart_type)
    chart.data_series = [Mock() for _ in range(series)]
    return chart


def test_get_charts_empty_when_no_project_open():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False

    dialog = _make_dialog(app_context)

    assert dialog._get_charts() == []


def test_get_charts_empty_when_project_has_no_charts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = []
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert dialog._get_charts() == []


def test_get_charts_filters_to_chart_items_only():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    c1, c2 = _chart("A"), _chart("B")
    non_chart_item = Mock()
    project = Mock()
    project.get_all_items.return_value = [c1, non_chart_item, c2]
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert dialog._get_charts() == [c1, c2]


def test_create_chart_button_always_present_with_no_charts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False

    dialog = _make_dialog(app_context)

    assert hasattr(dialog, "create_btn")


def test_create_chart_button_always_present_with_charts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = [_chart("A")]
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert hasattr(dialog, "create_btn")


def test_dialog_shows_an_intro_explanation_regardless_of_branch():
    empty_context = Mock()
    empty_context.get_app_state.return_value.has_project = False
    empty_dialog = _make_dialog(empty_context)
    assert empty_dialog.intro_label.text().strip()

    populated_context = Mock()
    populated_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = [_chart("A")]
    populated_context.get_app_state.return_value.current_project = project
    populated_dialog = _make_dialog(populated_context)
    assert populated_dialog.intro_label.text().strip()


def test_open_chart_emits_tab_open_requested_and_accepts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    dialog = _make_dialog(app_context)
    chart = _chart("Sales Trend")
    chart.id = "chart-1"

    dialog._open_chart(chart)

    from pandaplot.models.events.event_types import UIEvents
    event_bus = app_context.get_app_state.return_value.event_bus
    event_bus.emit.assert_called_once_with(
        UIEvents.TAB_OPEN_REQUESTED, {"item_id": "chart-1", "item_name": "Sales Trend"}
    )
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_chart_list_disambiguates_duplicate_chart_names():
    # Uses a real Project (not a Mock) so chart_display_options' folder-path
    # lookup (project.get_folder_path) has something real to resolve --
    # this is what a project full of wizard-created "New Chart"s looks like.
    project = Project(name="Test Project")
    runs = Folder(name="Runs")
    project.add_item(runs)

    root_chart = Chart(name="New Chart")
    nested_chart = Chart(name="New Chart")
    project.add_item(root_chart)
    project.add_item(nested_chart, runs.id)

    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    buttons = dialog.findChildren(QPushButton, "ChartItemButton")
    names = {button.accessibleName() for button in buttons}
    assert names == {"New Chart  (project root)", "New Chart  (Runs)"}
    assert len(buttons) == 2


def test_chart_item_uses_canonical_chart_type_display_names():
    # chart_type.value.capitalize() would mangle these: "hist" -> "Hist"
    # (not "Histogram"), "colormap" -> "Colormap" (not "Color Map").
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = [
        _chart("Histogram Chart", chart_type="hist"),
        _chart("Colormap Chart", chart_type="colormap"),
    ]
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    buttons = dialog.findChildren(QPushButton, "ChartItemButton")
    descriptions = {button.accessibleDescription() for button in buttons}
    assert descriptions == {"Histogram chart · 0 series", "Color Map chart · 0 series"}


def test_handle_create_chart_invokes_callback_and_accepts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    on_create_chart = Mock()
    dialog = _make_dialog(app_context, on_create_chart=on_create_chart)

    dialog._handle_create_chart()

    on_create_chart.assert_called_once()
    assert dialog.result() == QDialog.DialogCode.Accepted
