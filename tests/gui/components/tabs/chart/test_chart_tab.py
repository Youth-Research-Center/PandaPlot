from unittest.mock import Mock

from PySide6.QtCore import QTimer

from pandaplot.gui.components.tabs.chart.chart_tab import ChartTab


def test_get_tab_data_returns_chart_type_and_id():
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1")

    assert tab.get_tab_data() == {"type": "chart", "id": "ch-1"}


def test_on_chart_renamed_refreshes_title_for_matching_chart():
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1")
    tab.refresh_tab_title = Mock()

    tab.on_chart_renamed({"item_id": "ch-1", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_called_once()


def test_on_chart_renamed_ignores_other_items():
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1")
    tab.refresh_tab_title = Mock()

    tab.on_chart_renamed({"item_id": "other-id", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_not_called()


def test_on_dataset_changed_debounces_refresh_instead_of_calling_immediately(qapp):
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1", get_all_datasets=Mock(return_value=["ds-1"]))
    tab._chart_refresh_timer = QTimer()
    tab._chart_refresh_timer.setSingleShot(True)
    tab._chart_refresh_timer.timeout.connect(lambda: tab._refresh_chart_editor())
    tab._refresh_chart_editor = Mock()

    tab.on_dataset_changed({"dataset_id": "ds-1"})

    tab._refresh_chart_editor.assert_not_called()
    assert tab._chart_refresh_timer.isActive()


def test_on_chart_updated_debounces_refresh_instead_of_calling_immediately(qapp):
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1")
    tab._chart_refresh_timer = QTimer()
    tab._chart_refresh_timer.setSingleShot(True)
    tab._chart_refresh_timer.timeout.connect(lambda: tab._refresh_chart_editor())
    tab._refresh_chart_editor = Mock()

    tab.on_chart_updated({"chart_id": "ch-1"})

    tab._refresh_chart_editor.assert_not_called()
    assert tab._chart_refresh_timer.isActive()


def test_rapid_dataset_changes_coalesce_into_one_refresh(qapp, qtbot):
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1", get_all_datasets=Mock(return_value=["ds-1"]))
    tab._chart_refresh_timer = QTimer()
    tab._chart_refresh_timer.setSingleShot(True)
    tab._chart_refresh_timer.timeout.connect(lambda: tab._refresh_chart_editor())
    tab._refresh_chart_editor = Mock()

    for _ in range(5):
        tab.on_dataset_changed({"dataset_id": "ds-1"})
    tab._refresh_chart_editor.assert_not_called()
    qtbot.wait(600)
    tab._refresh_chart_editor.assert_called_once()


def test_on_dataset_changed_ignores_unrelated_dataset(qapp):
    tab = ChartTab.__new__(ChartTab)
    tab.chart = Mock(id="ch-1", get_all_datasets=Mock(return_value=["ds-1"]))
    tab._chart_refresh_timer = QTimer()
    tab._chart_refresh_timer.setSingleShot(True)
    tab._chart_refresh_timer.timeout.connect(lambda: tab._refresh_chart_editor())
    tab._refresh_chart_editor = Mock()

    tab.on_dataset_changed({"dataset_id": "other-ds"})

    assert not tab._chart_refresh_timer.isActive()
