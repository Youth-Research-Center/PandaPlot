"""Tests for TabContainer.create_chart_from_dataset delegating to TabContainerCommandManager.

The command-construction logic itself moved to TabContainerCommandManager (see
tests/gui/components/tabs/test_tab_container_command_manager.py) as part of
issue #251's "TabContainer also carries command-dispatch logic" cleanup. This
thin pass-through stays on TabContainer only because DatasetTab.create_chart_from_data
looks up `create_chart_from_dataset` by walking its Qt parent-widget chain.
"""
from unittest.mock import create_autospec

from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.components.tabs.tab_container_command_manager import TabContainerCommandManager


def test_create_chart_from_dataset_delegates_to_the_command_manager():
    container = TabContainer.__new__(TabContainer)
    container.command_manager = create_autospec(TabContainerCommandManager)

    container.create_chart_from_dataset("ds-1", preselected_column_ids=["col-rev"])

    container.command_manager.create_chart_from_dataset.assert_called_once_with(
        "ds-1", ["col-rev"]
    )
