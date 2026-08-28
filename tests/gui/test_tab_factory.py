"""Tests for TabFactory."""
from unittest.mock import Mock, sentinel

import pytest

from pandaplot.gui.components.tabs.tab_factory import TabFactory


class _FakeItem:
    """Stand-in for an Item subclass; TabFactory keys on exact type()."""


class _OtherFakeItem:
    pass


def test_create_tab_calls_the_registered_loader_with_the_right_args():
    factory = TabFactory()
    loader = Mock(return_value=sentinel.tab_widget)
    factory.register(_FakeItem, loader)

    item = _FakeItem()
    app_context = Mock()
    parent = Mock()

    result = factory.create_tab(app_context, item, parent)

    loader.assert_called_once_with(app_context, item, parent)
    assert result is sentinel.tab_widget


def test_create_tab_raises_on_none_item():
    factory = TabFactory()

    with pytest.raises(ValueError, match="Item cannot be None"):
        factory.create_tab(Mock(), None, Mock())


def test_create_tab_raises_on_unregistered_item_type():
    factory = TabFactory()
    factory.register(_FakeItem, Mock())

    with pytest.raises(ValueError, match="Unsupported item type, item class _OtherFakeItem"):
        factory.create_tab(Mock(), _OtherFakeItem(), Mock())
