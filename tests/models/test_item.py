"""
Unit tests for pandaplot.models.project.items.item module.

Tests cover the Item and ItemCollection classes, including:
- Basic item creation and properties
- Serialization and deserialization
- Collection operations (add, remove, find)
- Hierarchical operations
- Edge cases and error handling
"""

import pytest
import uuid
import time
from pandaplot.models.project.items import Item, ItemCollection


# Fixtures
@pytest.fixture
def test_item_data():
    """Fixture providing test data for items."""
    return {
        'id': "test-item-123",
        'name': "Test Item"
    }


@pytest.fixture
def sample_items():
    """Fixture providing sample items for collection tests."""
    return {
        'item1': Item(id="item-1", name="Item 1"),
        'item2': Item(id="item-2", name="Item 2"),
        'item3': Item(id="item-3", name="Item 3")
    }


@pytest.fixture
def collection_data():
    """Fixture providing test data for collections."""
    return {
        'id': "collection-123",
        'name': "Test Collection"
    }


# Item Tests
class TestItem:
    """Test cases for Item class."""

    def test_item_creation_with_all_params(self, test_item_data):
        """Test creating an item with all parameters specified."""
        item = Item(
            id=test_item_data['id'],
            name=test_item_data['name'],
        )

        assert item.id == test_item_data['id']
        assert item.name == test_item_data['name']
        assert item.parent_id is None
        assert isinstance(item.created_at, str)
        assert item.modified_at == item.created_at
        assert item.metadata == {}

    def test_item_creation_with_defaults(self):
        """Test creating an item with default parameters."""
        item = Item()

        # ID should be auto-generated UUID
        assert isinstance(item.id, str)
        assert item.id != ""
        # Verify it's a valid UUID
        uuid.UUID(item.id)  # This will raise ValueError if invalid

        assert item.name == ""
        assert item.parent_id is None
        assert isinstance(item.created_at, str)
        assert item.modified_at == item.created_at
        assert item.metadata == {}

    def test_item_creation_partial_params(self, test_item_data):
        """Test creating an item with some parameters."""
        item = Item(name=test_item_data['name'])

        assert isinstance(item.id, str)
        assert item.name == test_item_data['name']

    def test_update_modified_time(self, test_item_data):
        """Test that update_modified_time changes the timestamp."""
        item = Item(name=test_item_data['name'])
        original_time = item.modified_at

        # Sleep briefly to ensure time difference
        time.sleep(0.001)

        item.update_modified_time()
        assert item.modified_at != original_time
        assert item.modified_at > original_time

    def test_update_name(self, test_item_data):
        """Test updating item name also updates modified time."""
        item = Item(name=test_item_data['name'])
        original_time = item.modified_at
        new_name = "Updated Name"

        # Sleep briefly to ensure time difference
        time.sleep(0.001)

        item.update_name(new_name)
        assert item.name == new_name
        assert item.modified_at != original_time
        assert item.modified_at > original_time

    def test_to_dict(self, test_item_data):
        """Test serialization to dictionary."""
        item = Item(
            id=test_item_data['id'],
            name=test_item_data['name'],
        )
        item.parent_id = "parent-123"
        item.metadata = {"key": "value", "number": 42}

        result = item.to_dict()

        expected = {
            'id': test_item_data['id'],
            'name': test_item_data['name'],
            'parent_id': "parent-123",
            'created_at': item.created_at,
            'modified_at': item.modified_at,
            'metadata': {"key": "value", "number": 42}
        }

        assert result == expected

    def test_from_dict_complete_data(self, test_item_data):
        """Test deserialization from complete dictionary."""
        data = {
            'id': test_item_data['id'],
            'name': test_item_data['name'],
            'parent_id': "parent-123",
            'created_at': "2023-01-01T12:00:00",
            'modified_at': "2023-01-01T13:00:00",
            'metadata': {"key": "value"}
        }

        item = Item.from_dict(data)

        assert item.id == test_item_data['id']
        assert item.name == test_item_data['name']
        assert item.parent_id == "parent-123"
        assert item.created_at == "2023-01-01T12:00:00"
        assert item.modified_at == "2023-01-01T13:00:00"
        assert item.metadata == {"key": "value"}

    def test_from_dict_minimal_data(self):
        """Test deserialization from minimal dictionary."""
        data = {}

        item = Item.from_dict(data)

        # ID should be auto-generated when not provided
        assert isinstance(item.id, str)
        assert item.id != ""
        # Verify it's a valid UUID
        uuid.UUID(item.id)  # This will raise ValueError if invalid

        assert item.name == ""
        assert item.parent_id is None
        assert isinstance(item.created_at, str)
        assert item.modified_at == item.created_at
        assert item.metadata == {}

    def test_str_representation(self, test_item_data):
        """Test string representation of item."""
        item = Item(id=test_item_data['id'], name=test_item_data['name'])
        expected = f"Item(id='{test_item_data['id']}', name='{test_item_data['name']}')"
        assert str(item) == expected

    def test_repr_representation(self, test_item_data):
        """Test repr representation equals str representation."""
        item = Item(id=test_item_data['id'], name=test_item_data['name'])
        assert repr(item) == str(item)


# ItemCollection Tests
class TestItemCollection:
    """Test cases for ItemCollection class."""

    def test_collection_creation(self, collection_data):
        """Test creating an ItemCollection."""
        collection = ItemCollection(
            id=collection_data['id'], name=collection_data['name'])

        assert collection.id == collection_data['id']
        assert collection.name == collection_data['name']
        assert len(collection.items) == 0
        assert isinstance(collection.items, dict)

    def test_collection_creation_with_defaults(self):
        """Test creating an ItemCollection with default parameters."""
        collection = ItemCollection()

        assert isinstance(collection.id, str)
        assert collection.name == "Collection"
        assert len(collection.items) == 0

    def test_collection_iteration(self, sample_items):
        """Test iterating over collection items."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        items = list(collection)
        assert len(items) == 2
        assert sample_items['item1'] in items
        assert sample_items['item2'] in items

    def test_add_item(self, sample_items):
        """Test adding an item to the collection."""
        collection = ItemCollection()
        original_modified = collection.modified_at

        # Sleep briefly to ensure time difference
        time.sleep(0.001)

        collection.add_item(sample_items['item1'])

        assert sample_items['item1'].id in collection.items
        assert collection.items[sample_items['item1'].id] == sample_items['item1']
        assert sample_items['item1'].parent_id == collection.id
        assert collection.modified_at != original_modified

    def test_add_multiple_items(self, sample_items):
        """Test adding multiple items to the collection."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])
        collection.add_item(sample_items['item3'])

        assert len(collection.items) == 3
        assert sample_items['item1'].id in collection.items
        assert sample_items['item2'].id in collection.items
        assert sample_items['item3'].id in collection.items

    def test_remove_item(self, sample_items):
        """Test removing an item from the collection."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        original_modified = collection.modified_at
        time.sleep(0.001)

        collection.remove_item(sample_items['item1'])

        assert sample_items['item1'].id not in collection.items
        assert sample_items['item2'].id in collection.items
        assert sample_items['item1'].parent_id is None
        assert collection.modified_at != original_modified

    def test_remove_item_not_in_collection(self, sample_items):
        """Test removing an item that's not in the collection."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])

        # Should not raise an error
        collection.remove_item(sample_items['item2'])
        assert sample_items['item1'].id in collection.items

    def test_remove_item_by_id(self, sample_items):
        """Test removing an item by ID."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        collection.remove_item_by_id(sample_items['item1'].id)

        assert sample_items['item1'].id not in collection.items
        assert sample_items['item2'].id in collection.items
        assert sample_items['item1'].parent_id is None

    def test_remove_item_by_id_not_exists(self, sample_items):
        """Test removing an item by ID that doesn't exist."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])

        # Should not raise an error
        collection.remove_item_by_id("non-existent-id")
        assert sample_items['item1'].id in collection.items

    def test_get_item_by_id(self, sample_items):
        """Test getting an item by ID."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        result = collection.get_item_by_id(sample_items['item1'].id)
        assert result == sample_items['item1']

        result = collection.get_item_by_id("non-existent")
        assert result is None

    def test_get_items(self, sample_items):
        """Test getting all items as a list."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        items = collection.get_items()
        assert isinstance(items, list)
        assert len(items) == 2
        assert sample_items['item1'] in items
        assert sample_items['item2'] in items

    def test_len_empty_collection(self):
        """Test length of empty collection."""
        collection = ItemCollection()
        assert len(collection) == 0

    def test_len_with_items(self, sample_items):
        """Test length calculation with regular items."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])
        assert len(collection) == 2

    def test_len_with_nested_collections(self, sample_items):
        """Test length calculation with nested collections."""
        collection = ItemCollection()
        subcollection = ItemCollection()

        collection.add_item(sample_items['item1'])  # 1 item
        # This subcollection counts as items inside it
        collection.add_item(subcollection)
        # 1 item in subcollection
        subcollection.add_item(sample_items['item2'])
        # 1 item in subcollection
        subcollection.add_item(sample_items['item3'])

        # Should count items in subcollections
        assert len(collection) == 3  # 1 direct + 2 in subcollection

    def test_to_dict_empty_collection(self, collection_data):
        """Test serialization of empty collection."""
        collection = ItemCollection(
            id=collection_data['id'], name=collection_data['name'])
        result = collection.to_dict()

        assert result['id'] == collection_data['id']
        assert result['name'] == collection_data['name']
        assert result['items'] == []

    def test_to_dict_with_items(self, sample_items):
        """Test serialization of collection with items."""
        collection = ItemCollection()
        collection.add_item(sample_items['item1'])
        collection.add_item(sample_items['item2'])

        result = collection.to_dict()

        assert len(result['items']) == 2
        assert isinstance(result['items'], list)

        # Check that items are serialized as dictionaries
        item_dicts = result['items']
        item_ids = [item['id'] for item in item_dicts]
        assert sample_items['item1'].id in item_ids
        assert sample_items['item2'].id in item_ids

    def test_from_dict_empty_collection(self, collection_data):
        """Test deserialization of empty collection."""
        data = {
            'id': collection_data['id'],
            'name': collection_data['name'],
            'items': []
        }

        collection = ItemCollection.from_dict(data)

        assert collection.id == collection_data['id']
        assert collection.name == collection_data['name']
        assert len(collection.items) == 0

    def test_from_dict_minimal_data(self):
        """Test deserialization from minimal data."""
        data = {}
        collection = ItemCollection.from_dict(data)

        # ID should be auto-generated when not provided
        assert isinstance(collection.id, str)
        assert collection.id != ""
        # Verify it's a valid UUID
        uuid.UUID(collection.id)  # This will raise ValueError if invalid

        assert collection.name == "Collection"
        assert len(collection.items) == 0


# Edge Cases Tests
class TestItemCollectionEdgeCases:
    """Test edge cases and error conditions for ItemCollection."""

    def test_add_same_item_twice(self):
        """Test adding the same item twice (should overwrite)."""
        collection = ItemCollection()
        item = Item(id="test-item", name="Test")

        collection.add_item(item)
        collection.add_item(item)  # Add same item again

        assert len(collection.items) == 1
        assert collection.items["test-item"] == item

    def test_nested_collection_parent_ids(self):
        """Test that parent IDs are set correctly in nested collections."""
        parent = ItemCollection(name="Parent")
        child = ItemCollection(name="Child")
        item = Item(name="Item")

        parent.add_item(child)
        child.add_item(item)

        assert child.parent_id == parent.id
        assert item.parent_id == child.id

    def test_move_item_between_collections(self):
        """Test moving an item from one collection to another."""
        collection1 = ItemCollection(name="Collection1")
        collection2 = ItemCollection(name="Collection2")
        item = Item(name="MovableItem")

        # Add to first collection
        collection1.add_item(item)
        assert item.parent_id == collection1.id
        assert item.id in collection1.items

        # Remove from first and add to second
        collection1.remove_item(item)
        collection2.add_item(item)

        assert item.parent_id == collection2.id
        assert item.id not in collection1.items
        assert item.id in collection2.items
