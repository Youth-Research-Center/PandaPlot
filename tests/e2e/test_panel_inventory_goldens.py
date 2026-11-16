"""Every side panel and Chart Properties tab still contains what its committed golden records (spec §8, DS-02).

The panels are built by the real window with a dataset tab or a chart tab active, so conditional panels show their
populated form. See `tests/e2e/panel_inventory/README.md` for how a migration PR regenerates a golden.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset
from tests.gui.panel_inventory import assert_matches_golden, panel_inventory

GOLDENS = Path(__file__).parent / "panel_inventory"
DATASET_TAB_PANELS = ("explorer", "search", "transform", "preprocessing", "analysis", "descriptive", "statistics", "signal")
CHART_TAB_PANELS = ("chart_properties", "fit", "chart_analysis", "chart_signal", "chart_transform")
CHART_PROPERTIES_TABS = ("chart", "data", "style", "axes", "legend")


def _column_id(dataset: Dataset, name: str) -> str:
    column_id = dataset.column_id(name)
    assert column_id is not None
    return column_id


def _pages(properties: ChartPropertiesPanel) -> list[QWidget]:
    pages = [properties.tab_widget.widget(i) for i in range(properties.tab_widget.count())]
    return [page for page in pages if page is not None]


def _project() -> tuple[Project, Dataset, Chart]:
    """A small project with fixed ids and values, so the goldens do not depend on random data."""
    project = Project(name="Inventory")
    time = np.linspace(0.0, 9.9, 100)
    dataset = Dataset(
        id="dataset-inventory",
        name="Measurements",
        data=pd.DataFrame({"time": time, "signal": np.sin(time), "reference": np.cos(time)}),
    )
    project.add_item(dataset)
    chart = Chart(id="chart-inventory", name="Signal over time", chart_type=ChartType.LINE)
    chart.add_data_series(
        dataset_id=dataset.id,
        x_column_id=_column_id(dataset, "time"),
        y_column_id=_column_id(dataset, "signal"),
        label="Signal",
    )
    project.add_item(chart)
    return project, dataset, chart


def _flush_deferred_deletes() -> None:
    """Delete widgets a panel replaced; until their deferred delete runs they are still in the focus chain."""
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _panels(window: PandaMainWindow) -> dict[str, QWidget]:
    return {info["name"]: info["panel"] for info in window.sidebar_panel_coordinator.panel_setup_manager.panels}


def _open_tab(window: PandaMainWindow, qtbot: QtBot, item_id: str, panel_names: tuple[str, ...]) -> None:
    window.tab_container.open_tab(item_id)
    qtbot.waitUntil(lambda: window.tab_container.get_tab_widget(item_id) is not None)
    sidebar = window.sidebar
    qtbot.waitUntil(lambda: all(sidebar.icon_bar.panels[name].isVisible() for name in panel_names))


def _show(window: PandaMainWindow, qtbot: QtBot, name: str) -> None:
    sidebar = window.sidebar
    if sidebar.active_panel != name:
        sidebar.show_panel(name)
    qtbot.waitUntil(lambda: sidebar.active_panel == name)
    _flush_deferred_deletes()


def _chart_properties_excluded(properties: ChartPropertiesPanel) -> list[QWidget]:
    """The tab pages have their own goldens. The tab selector combo replaces the tab bar only when the tabs do not
    fit, which depends on font metrics, so it is left out (spec §6 replaces it with tab scroll buttons)."""
    return [*_pages(properties), properties.tab_selector_combo]


def _check(targets: dict[str, list[str]]) -> None:
    """Compare every target before failing, so one run shows all diffs."""
    failures = []
    for name, lines in targets.items():
        try:
            assert_matches_golden(lines, GOLDENS / f"{name}.txt")
        except AssertionError as error:
            failures.append(str(error))
    assert not failures, "\n\n".join(failures)


def test_dataset_tab_panels_match_their_goldens(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    project, dataset, _chart = _project()
    app_window.app_context.app_state.load_project(project)
    _open_tab(app_window, qtbot, dataset.id, DATASET_TAB_PANELS)
    panels = _panels(app_window)

    targets = {}
    for name in DATASET_TAB_PANELS:
        _show(app_window, qtbot, name)
        targets[name] = panel_inventory(panels[name])

    _check(targets)


def test_chart_tab_panels_and_chart_properties_tabs_match_their_goldens(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    project, _dataset, chart = _project()
    app_window.app_context.app_state.load_project(project)
    _open_tab(app_window, qtbot, chart.id, CHART_TAB_PANELS)
    panels = _panels(app_window)
    properties = panels["chart_properties"]
    assert isinstance(properties, ChartPropertiesPanel)

    targets = {}
    for name in CHART_TAB_PANELS:
        _show(app_window, qtbot, name)
        targets[name] = panel_inventory(panels[name], exclude=_chart_properties_excluded(properties) if name == "chart_properties" else ())
    _show(app_window, qtbot, "chart_properties")
    for tab_name in CHART_PROPERTIES_TABS:
        tab = getattr(properties, f"{tab_name}_tab")
        properties.tab_widget.setCurrentWidget(next(page for page in _pages(properties) if page.isAncestorOf(tab)))
        _flush_deferred_deletes()
        targets[f"chart_properties-{tab_name}"] = panel_inventory(tab)

    _check(targets)
