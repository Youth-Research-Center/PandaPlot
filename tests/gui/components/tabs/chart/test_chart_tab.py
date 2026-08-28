from unittest.mock import Mock

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
