"""Tests for DataTab's series reordering (move-up/move-down) controls (#189).

Follows the pattern in test_data_tab_selection_persistence.py: a real
DataTab against a real build_app_context()/Project/Chart, since the move
handlers touch the real ReorderSeriesCommand/CommandExecutor undo stack.
"""
import sys

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_with_three_series():
    project = Project(name="Reorder Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, "x", "y", label="A")
    chart.add_data_series(dataset.id, "x", "y", label="B")
    chart.add_data_series(dataset.id, "x", "y", label="C")
    project.add_item(chart)
    return project, chart


def _labels(chart):
    return [s.label for s in chart.data_series]


@pytest.fixture
def data_tab_with_chart():
    _qapp()
    app_context = build_app_context()
    app_context.get_app_state().load_project(_project_with_three_series()[0])
    project = app_context.get_app_state().current_project
    chart = next(i for i in project.get_all_items() if isinstance(i, Chart))

    data_tab = DataTab(app_context=app_context)
    data_tab.set_project(project)
    data_tab.load(chart)
    return data_tab, chart, app_context


def test_move_series_reorders_the_data_series_list(data_tab_with_chart):
    data_tab, chart, _ = data_tab_with_chart

    data_tab._move_series(0, 2)

    assert _labels(chart) == ["B", "C", "A"]


def test_move_series_is_undoable_via_the_command_executor(data_tab_with_chart):
    data_tab, chart, app_context = data_tab_with_chart

    data_tab._move_series(0, 2)
    assert _labels(chart) == ["B", "C", "A"]

    app_context.get_command_executor().undo()

    assert _labels(chart) == ["A", "B", "C"]


def test_move_series_out_of_range_is_a_noop(data_tab_with_chart):
    data_tab, chart, _ = data_tab_with_chart

    data_tab._move_series(0, -1)
    data_tab._move_series(0, 3)

    assert _labels(chart) == ["A", "B", "C"]


def test_moving_the_selected_series_follows_it_to_the_new_index(data_tab_with_chart):
    """Regression: after a reorder, the previously-selected/expanded card
    must stay pinned to the *same series*, not the same numeric index --
    otherwise moving series A out from under an open, live-edited card
    would silently start editing whatever series slid into A's old slot."""
    data_tab, chart, _ = data_tab_with_chart
    data_tab._expand_series(0)
    assert data_tab.selected_index == 0

    data_tab._move_series(0, 2)

    assert data_tab.selected_index == 2
    assert chart.data_series[data_tab.selected_index].label == "A"


def test_move_up_button_disabled_for_first_series(data_tab_with_chart):
    data_tab, _chart, _ = data_tab_with_chart

    up_buttons = [b for b in data_tab.findChildren(QPushButton) if b.text() == "▲"]
    # One "up" button per series row (collapsed cards, since nothing is expanded beyond index 0).
    assert len(up_buttons) >= 3
    assert up_buttons[0].isEnabled() is False
    assert all(b.isEnabled() for b in up_buttons[1:])


def test_move_down_button_disabled_for_last_series(data_tab_with_chart):
    data_tab, _chart, _ = data_tab_with_chart

    down_buttons = [b for b in data_tab.findChildren(QPushButton) if b.text() == "▼"]
    assert len(down_buttons) >= 3
    assert down_buttons[-1].isEnabled() is False
    assert all(b.isEnabled() for b in down_buttons[:-1])


def test_clicking_move_down_button_reorders_series(data_tab_with_chart):
    data_tab, chart, _ = data_tab_with_chart

    down_button = next(b for b in data_tab.findChildren(QPushButton) if b.text() == "▼" and b.isEnabled())
    QTest.mouseClick(down_button, Qt.MouseButton.LeftButton)

    assert _labels(chart) == ["B", "A", "C"]


def _current_generation_move_buttons(data_tab):
    """Move buttons in the *currently laid-out* cards only.

    `data_tab.findChildren(QPushButton)` would also return buttons from
    already-replaced cards: `_rebuild_series_cards` removes a stale card
    from `_series_cards_layout` via `takeAt` and schedules it for deletion
    (`deleteLater()`), but that deletion is deferred by Qt and isn't
    reliably flushed inside a headless test (no running event loop) -- the
    stale widget stays a QObject child, and therefore a findChildren hit,
    until then. Scoping to what's actually still in the layout sidesteps
    that entirely.
    """
    buttons = []
    for i in range(data_tab._series_cards_layout.count()):
        widget = data_tab._series_cards_layout.itemAt(i).widget()
        if widget is not None:
            buttons.extend(b for b in widget.findChildren(QPushButton) if b.text() in ("▲", "▼"))
    return buttons


def test_fit_data_rows_have_no_move_buttons(data_tab_with_chart):
    """Fits always draw after every series regardless of list position
    (chart_editor.py's separate, always-later fit-plotting loop), so
    reordering them wouldn't change anything -- no move controls offered.
    Every one of the 3 row-rendering modes (collapsed/detail/expanded) is
    shared between series and fits, so this only holds if all three
    correctly gate the move buttons on "is this a series, not a fit"."""
    data_tab, chart, _ = data_tab_with_chart
    chart.add_fit_data(
        source_dataset_id=chart.data_series[0].dataset_id, fit_type="linear",
        x_data=np.array([1, 2, 3]), y_data=np.array([1, 2, 3]), label="Fit 1",
    )
    data_tab.load(chart)
    total_series = len(chart.data_series)

    # Collapsed/detail rows only (nothing expanded past the default index 0).
    assert len(_current_generation_move_buttons(data_tab)) == 2 * total_series

    # Expand the fit row (combined index 3, appended after the 3 series) --
    # if _build_expanded_series_card built move buttons for it too, this
    # count would grow past 2 * total_series.
    data_tab._expand_series(total_series)
    assert data_tab.selected_index == total_series
    assert len(_current_generation_move_buttons(data_tab)) == 2 * total_series
