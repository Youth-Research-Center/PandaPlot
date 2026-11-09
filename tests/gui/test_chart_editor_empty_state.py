"""ChartEditorWidget shows an empty-state page, with actions, until its chart has a series."""

import pandas as pd
import pytest

from pandaplot.app import build_app_context
from pandaplot.commands.project.chart import AddSeriesFromDialogCommand
from pandaplot.commands.project.chart.add_series_command import AddSeriesCommand
from pandaplot.commands.project.dataset.import_data_command import ImportDataCommand
from pandaplot.gui.components.tabs.chart.chart_tab import ChartTab
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.items.chart import DataSeries
from pandaplot.models.project.project import Project


@pytest.fixture
def env(qtbot):
    project = Project(name="Test Project")
    dataset = Dataset(name="ds", data=pd.DataFrame({"x": [1, 2, 3], "y": [3, 4, 5]}))
    project.add_item(dataset)
    chart = Chart(name="Chart", chart_type="line")
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    tab = ChartTab(app_context=app_context, chart=chart, parent=None)
    qtbot.addWidget(tab)
    return app_context, dataset, chart, tab, tab.chart_editor


def _series(dataset: Dataset) -> DataSeries:
    return DataSeries(dataset_id=dataset.id, x_column_id=dataset.column_id("x") or "", y_column_id=dataset.column_id("y") or "", label="s")


def test_empty_chart_shows_empty_page_and_disables_nav_toolbar(env):
    _, _, _, _, editor = env

    assert editor.preview_stack.currentWidget() is editor.empty_state_panel
    assert not editor.chart_canvas.navigation_toolbar.isEnabled()
    assert editor.empty_state_panel.heading_label.text() == "This chart has no data yet"


def test_adding_series_switches_to_canvas_and_undo_restores_empty_page(env):
    app_context, dataset, chart, _, editor = env
    executor = app_context.get_command_executor()

    assert executor.execute_command(AddSeriesCommand(app_context, chart.id, _series(dataset)))
    assert editor.preview_stack.currentWidget() is editor.canvas_scroll
    assert editor.chart_canvas.navigation_toolbar.isEnabled()
    assert editor.dataset_label.text() == "Datasets: ds"

    assert executor.undo()
    assert editor.preview_stack.currentWidget() is editor.empty_state_panel
    assert not editor.chart_canvas.navigation_toolbar.isEnabled()
    assert editor.dataset_label.text() == "No series"

    assert executor.redo()
    assert editor.preview_stack.currentWidget() is editor.canvas_scroll
    assert editor.dataset_label.text() == "Datasets: ds"


def test_panel_buttons_execute_the_matching_commands(env, monkeypatch):
    app_context, _, chart, _, editor = env
    executed = []
    monkeypatch.setattr(app_context.get_command_executor(), "execute_command", lambda command, **_: executed.append(command) or True)

    editor.empty_state_panel.action_buttons[0].click()
    editor.empty_state_panel.action_buttons[1].click()

    assert [type(command) for command in executed] == [AddSeriesFromDialogCommand, ImportDataCommand]
    assert executed[0].chart_id == chart.id


def test_first_series_on_chart_without_saved_size_fits_canvas_to_panel(env, qtbot):
    app_context, dataset, chart, tab, _editor = env
    tab.resize(900, 700)
    tab.show()
    qtbot.waitExposed(tab)
    assert chart.config.width_cm is None
    assert chart.config.height_cm is None

    app_context.get_command_executor().execute_command(AddSeriesCommand(app_context, chart.id, _series(dataset)))

    qtbot.waitUntil(lambda: chart.config.width_cm is not None, timeout=3000)
    assert chart.config.height_cm is not None


def test_initial_fit_does_nothing_while_empty_page_is_current(env, qtbot):
    _, _, chart, tab, editor = env
    tab.resize(900, 700)
    tab.show()
    qtbot.waitExposed(tab)

    editor._apply_initial_fit_size()

    assert chart.config.width_cm is None
    assert chart.config.height_cm is None


def test_status_line_follows_a_dataset_rename(env):
    from pandaplot.commands.project.item.rename_item_command import RenameItemCommand

    app_context, dataset, chart, _, editor = env
    executor = app_context.get_command_executor()
    assert executor.execute_command(AddSeriesCommand(app_context, chart.id, _series(dataset)))
    assert editor.dataset_label.text() == "Datasets: ds"

    assert executor.execute_command(RenameItemCommand(app_context, dataset.id, "Raw"))

    assert editor.dataset_label.text() == "Datasets: Raw"

