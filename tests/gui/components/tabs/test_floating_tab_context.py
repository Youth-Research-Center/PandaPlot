from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.models.events import UIEvents
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.project import Project


class _ChartContextTab(QWidget):
    def __init__(self, chart: Chart) -> None:
        super().__init__()
        self.chart = chart
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def get_tab_data(self) -> dict[str, str]:
        return {"type": "chart", "id": self.chart.id}

    def get_tab_title(self) -> str:
        return self.chart.name


def test_floating_activation_and_same_pane_focus_restore_fit_context(qtbot: QtBot) -> None:
    project = Project(name="Floating context")
    dataset = Dataset(name="Data", data=pd.DataFrame({"x": [1, 2, 3], "y": [2, 4, 6]}))
    project.add_item(dataset)
    x_column_id = dataset.column_id("x")
    y_column_id = dataset.column_id("y")
    assert x_column_id is not None
    assert y_column_id is not None
    charts = [Chart(name="Chart A"), Chart(name="Chart B")]
    for chart in charts:
        chart.add_data_series(dataset_id=dataset.id, x_column_id=x_column_id, y_column_id=y_column_id)
        project.add_item(chart)
    context = Mock()
    context.app_state = SimpleNamespace(current_project=project, has_project=True)
    context.get_app_state.return_value = context.app_state
    context.event_bus = EventBus()
    context.get_manager.return_value.get_surface_palette.return_value = {"card_bg": "#17191e", "base_fg": "#ffffff"}
    context.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9}
    container = TabContainer(context, parent=None)
    panel = FitPanel(context)
    qtbot.addWidget(container)
    qtbot.addWidget(panel)
    container.show()
    panel.show()
    pane = container.panes[0]
    tabs = [_ChartContextTab(chart) for chart in charts]
    for chart, tab in zip(charts, tabs, strict=True):
        container.tabs[chart.id] = tab
        pane.addTab(tab, chart.name)
    published = []
    context.event_bus.subscribe(UIEvents.TAB_CHANGED, published.append)
    container._emit_tab_changed_for_active_pane()
    panel.fit_points_spin.setValue(811)
    pane.setCurrentIndex(1)
    panel.fit_points_spin.setValue(622)
    container.popout_tab(pane, 0)
    window = container.floating_windows[charts[0].id]

    try:
        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
        assert panel.current_chart is charts[0]
        assert panel.fit_points_spin.value() == 811
        assert published[-1]["tab_id"] == charts[0].id
        assert published[-1]["tab_type"] == "chart"
        event_count = len(published)
        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
        assert len(published) == event_count

        container.activateWindow()
        tabs[1].setFocus()
        qtbot.waitUntil(lambda: panel.current_chart is charts[1])
        assert panel.fit_points_spin.value() == 622
        assert published[-1]["tab_id"] == charts[1].id
    finally:
        container.close_tab_by_item_id(charts[0].id)
