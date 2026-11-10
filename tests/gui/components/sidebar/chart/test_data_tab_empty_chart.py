"""Tests for DataTab's empty-chart behaviour: the + Add series dialog route and the hint label."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QLabel

from pandaplot.app import build_app_context
from pandaplot.commands.project.chart import AddSeriesFromDialogCommand
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _setup():
    app_context = build_app_context()
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"x": [0, 1], "y": [0, 1]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    return app_context, project, dataset


def _record_commands(monkeypatch, app_context):
    """Replace the executor's execute_command with a recorder so no dialog ever opens."""
    executed = []
    monkeypatch.setattr(app_context.command_executor, "execute_command", lambda command: executed.append(command) or True)
    return executed


def _hint_labels(tab):
    return [
        tab._series_cards_layout.itemAt(i).widget()
        for i in range(tab._series_cards_layout.count())
        if tab._series_cards_layout.itemAt(i).widget().objectName() == "emptySeriesHint"
    ]


def test_add_series_on_an_empty_chart_opens_the_add_series_dialog_command(monkeypatch):
    app_context, project, _dataset = _setup()
    chart = Chart(name="Empty", chart_type="line")
    project.add_item(chart)
    executed = _record_commands(monkeypatch, app_context)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._add_series()

    assert len(executed) == 1
    assert isinstance(executed[0], AddSeriesFromDialogCommand)
    assert executed[0].chart_id == chart.id
    assert chart.data_series == []


def test_add_series_on_a_non_empty_chart_still_copies_the_selected_series(monkeypatch):
    app_context, project, dataset = _setup()
    chart = Chart(name="Filled", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    executed = _record_commands(monkeypatch, app_context)
    tab._add_series()

    assert len(executed) == 1
    assert not isinstance(executed[0], AddSeriesFromDialogCommand)


def test_empty_chart_shows_hint_which_disappears_once_a_series_exists():
    app_context, project, dataset = _setup()
    chart = Chart(name="Chart", chart_type="line")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    hints = _hint_labels(tab)
    assert len(hints) == 1
    assert isinstance(hints[0], QLabel)
    assert hints[0].wordWrap() is True
    assert "No series yet" in hints[0].text()

    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    tab.load(chart)

    assert _hint_labels(tab) == []


def test_panel_selects_the_new_series_on_series_selected_event():
    app_context, project, dataset = _setup()
    chart = Chart(name="Chart", chart_type="line")
    for _ in range(2):
        chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)
    assert panel.data_tab.selected_index == 0

    app_context.event_bus.emit(ChartEvents.SERIES_SELECTED, {"chart_id": chart.id, "series_index": 1, "index": 1})

    assert panel.data_tab.selected_index == 1
