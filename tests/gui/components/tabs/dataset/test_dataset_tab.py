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
