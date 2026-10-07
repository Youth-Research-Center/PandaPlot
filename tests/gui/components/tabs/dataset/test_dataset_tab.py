from unittest.mock import Mock

from pandaplot.gui.components.tabs.dataset.dataset_tab import DatasetTab


def test_get_tab_data_returns_dataset_type_and_id():
    tab = DatasetTab.__new__(DatasetTab)
    tab.dataset = Mock(id="ds-1")

    assert tab.get_tab_data() == {"type": "dataset", "id": "ds-1"}


def test_on_dataset_renamed_refreshes_title_for_matching_dataset():
    tab = DatasetTab.__new__(DatasetTab)
    tab.dataset = Mock(id="ds-1")
    tab.refresh_tab_title = Mock()

    tab.on_dataset_renamed({"item_id": "ds-1", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_called_once()


def test_on_dataset_renamed_ignores_other_items():
    tab = DatasetTab.__new__(DatasetTab)
    tab.dataset = Mock(id="ds-1")
    tab.refresh_tab_title = Mock()

    tab.on_dataset_renamed({"item_id": "other-id", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_not_called()


def test_analyze_measurements_routes_dataset_id_and_tab_as_parent():
    tab = DatasetTab.__new__(DatasetTab)
    tab.dataset = Mock(id="ds-1")
    tab.logger = Mock()
    tab.parent = Mock(return_value=None)
    container = Mock()
    tab.parent.side_effect = [container]

    tab.analyze_measurements()

    container.analyze_measurements_for_dataset.assert_called_once_with(
        "ds-1",
        parent_widget=tab,
    )
