"""
Unit tests for pandaplot.models.project.project module.

Tests cover the Project class, including:
- Project creation and initialization
- Item management (add, remove, find)
- Hierarchy operations
- Index management and rebuilding
- Serialization and deserialization
- Edge cases and error handling
"""

import pytest
import uuid
from pandaplot.models.project import Project
from pandaplot.models.project.items import Item, ItemCollection


# Fixtures
@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project(name="Test Project", description="A test project")


@pytest.fixture
def sample_item():
    """Create a sample item for testing."""
    return Item(name="Test Item")


@pytest.fixture
def sample_collection():
    """Create a sample collection for testing."""
    return ItemCollection(name="Test Collection")


@pytest.fixture
def populated_project():
    """Create a project with some items for testing."""
    project = Project(name="Populated Project")
    
    # Create some items
    item1 = Item(name="Item 1")
    item2 = Item(name="Item 2")
    collection1 = ItemCollection(name="Collection 1")
    item3 = Item(name="Item 3")
    
    # Add items to project
    project.add_item(item1)
    project.add_item(collection1)
    project.add_item(item2, collection1.id)
    project.add_item(item3, collection1.id)
    
    return project, item1, item2, collection1, item3


class TestProjectInitialization:
    """Test project initialization and basic properties."""
    
    def test_default_initialization(self):
        """Test project creation with default parameters."""
        project = Project()
        
        assert project.name == "Untitled Project"
        assert project.description == ""
        assert project.version == "1.0"
        assert isinstance(project.root, ItemCollection)
        assert project.root.name == "Untitled Project Root"
        assert isinstance(project.items_index, dict)
        assert len(project.items_index) == 0
        assert isinstance(project.metadata, dict)
        assert len(project.metadata) == 0
    
    def test_custom_initialization(self, sample_project):
        """Test project creation with custom parameters."""
        assert sample_project.name == "Test Project"
        assert sample_project.description == "A test project"
        assert sample_project.version == "1.0"
        assert isinstance(sample_project.root, ItemCollection)
        assert sample_project.root.name == "Test Project Root"
        assert isinstance(sample_project.items_index, dict)
        assert len(sample_project.items_index) == 0
        assert isinstance(sample_project.metadata, dict)
        assert len(sample_project.metadata) == 0


class TestItemManagement:
    """Test item addition, removal, and finding operations."""
    
    def test_add_item_to_root(self, sample_project, sample_item):
        """Test adding an item to the root level."""
        sample_project.add_item(sample_item)
        
        assert sample_item.id in sample_project.items_index
        assert sample_project.items_index[sample_item.id] == sample_item
        assert sample_item in sample_project.root.get_items()
        assert sample_item.parent_id == sample_project.root.id
    
    def test_add_item_to_parent(self, sample_project, sample_item, sample_collection):
        """Test adding an item to a specific parent collection."""
        # First add the collection to the project
        sample_project.add_item(sample_collection)
        
        # Then add the item to the collection
        sample_project.add_item(sample_item, sample_collection.id)
        
        assert sample_item.id in sample_project.items_index
        assert sample_project.items_index[sample_item.id] == sample_item
        assert sample_item in sample_collection.get_items()
        assert sample_item.parent_id == sample_collection.id
    
    def test_add_item_to_nonexistent_parent(self, sample_project, sample_item):
        """Test adding an item to a non-existent parent falls back to root."""
        fake_parent_id = str(uuid.uuid4())
        sample_project.add_item(sample_item, fake_parent_id)
        
        assert sample_item.id in sample_project.items_index
        assert sample_item in sample_project.root.get_items()
        assert sample_item.parent_id == sample_project.root.id
    
    def test_add_item_to_non_collection_parent(self, sample_project, sample_item):
        """Test adding an item to a non-collection parent falls back to root."""
        # Add a regular item first
        regular_item = Item(name="Regular Item")
        sample_project.add_item(regular_item)
        
        # Try to add another item to the regular item (not a collection)
        sample_project.add_item(sample_item, regular_item.id)
        
        assert sample_item.id in sample_project.items_index
        assert sample_item in sample_project.root.get_items()
        assert sample_item.parent_id == sample_project.root.id
    
    def test_remove_item(self, populated_project):
        """Test removing an item from the project."""
        project, item1, item2, collection1, item3 = populated_project
        
        # Remove item from root
        project.remove_item(item1)
        
        assert item1.id not in project.items_index
        assert item1 not in project.root.get_items()
        
        # Remove item from collection
        project.remove_item(item2)
        
        assert item2.id not in project.items_index
        assert item2 not in collection1.get_items()
    
    def test_remove_item_by_id(self, populated_project):
        """Test removing an item by ID."""
        project, item1, item2, collection1, item3 = populated_project
        
        item1_id = item1.id
        project.remove_item_by_id(item1_id)
        
        assert item1_id not in project.items_index
        assert item1 not in project.root.get_items()
    
    def test_remove_nonexistent_item_by_id(self, sample_project):
        """Test removing a non-existent item by ID doesn't raise error."""
        fake_id = str(uuid.uuid4())
        # Should not raise an exception
        sample_project.remove_item_by_id(fake_id)
    
    def test_find_item(self, populated_project):
        """Test finding items by ID."""
        project, item1, item2, collection1, item3 = populated_project
        
        found_item = project.find_item(item1.id)
        assert found_item == item1
        
        found_collection = project.find_item(collection1.id)
        assert found_collection == collection1
        
        found_nested_item = project.find_item(item2.id)
        assert found_nested_item == item2
    
    def test_find_nonexistent_item(self, sample_project):
        """Test finding a non-existent item returns None."""
        fake_id = str(uuid.uuid4())
        result = sample_project.find_item(fake_id)
        assert result is None


class TestProjectQueries:
    """Test project query operations."""
    
    def test_get_all_items_empty_project(self, sample_project):
        """Test getting all items from an empty project."""
        items = sample_project.get_all_items()
        assert isinstance(items, list)
        assert len(items) == 0
    
    def test_get_all_items_populated_project(self, populated_project):
        """Test getting all items from a populated project."""
        project, item1, item2, collection1, item3 = populated_project
        
        items = project.get_all_items()
        assert len(items) == 4  # item1, item2, collection1, item3
        assert item1 in items
        assert item2 in items
        assert collection1 in items
        assert item3 in items
    
    def test_get_root_items_empty_project(self, sample_project):
        """Test getting root items from an empty project."""
        root_items = sample_project.get_root_items()
        assert isinstance(root_items, list)
        assert len(root_items) == 0
    
    def test_get_root_items_populated_project(self, populated_project):
        """Test getting root items from a populated project."""
        project, item1, item2, collection1, item3 = populated_project
        
        root_items = project.get_root_items()
        assert len(root_items) == 2  # item1 and collection1 are at root
        assert item1 in root_items
        assert collection1 in root_items
        assert item2 not in root_items  # item2 is in collection1
        assert item3 not in root_items  # item3 is in collection1


class TestSerialization:
    """Test project serialization and deserialization."""
    
    def test_to_dict_empty_project(self, sample_project):
        """Test serializing an empty project to dictionary."""
        data = sample_project.to_dict()
        
        assert isinstance(data, dict)
        assert data['name'] == "Test Project"
        assert data['description'] == "A test project"
        assert data['version'] == "1.0"
        assert isinstance(data['metadata'], dict)
        assert isinstance(data['root'], dict)
        assert data['root']['name'] == "Test Project Root"
    
    def test_to_dict_populated_project(self, populated_project):
        """Test serializing a populated project to dictionary."""
        project, item1, item2, collection1, item3 = populated_project
        
        data = project.to_dict()
        
        assert isinstance(data, dict)
        assert data['name'] == "Populated Project"
        assert isinstance(data['root'], dict)
        # Root should contain serialized items
        assert 'items' in data['root']
        assert isinstance(data['root']['items'], list)
    
    def test_from_dict_minimal_data(self):
        """Test creating project from minimal dictionary data."""
        data = {
            'name': 'Restored Project',
            'description': 'A restored project'
        }
        
        project = Project.from_dict(data)
        
        assert project.name == 'Restored Project'
        assert project.description == 'A restored project'
        assert project.version == '1.0'  # Default value
        assert isinstance(project.metadata, dict)
        assert len(project.metadata) == 0
    
    def test_from_dict_complete_data(self):
        """Test creating project from complete dictionary data."""
        data = {
            'name': 'Complete Project',
            'description': 'A complete project',
            'version': '2.0',
            'metadata': {'author': 'Test User', 'tags': ['test', 'demo']}
        }
        
        project = Project.from_dict(data)
        
        assert project.name == 'Complete Project'
        assert project.description == 'A complete project'
        assert project.version == '2.0'
        assert project.metadata['author'] == 'Test User'
        assert project.metadata['tags'] == ['test', 'demo']
    
    def test_from_dict_empty_data(self):
        """Test creating project from empty dictionary."""
        data = {}
        
        project = Project.from_dict(data)
        
        assert project.name == 'Untitled Project'  # Default value
        assert project.description == ''  # Default value
        assert project.version == '1.0'  # Default value
        assert isinstance(project.metadata, dict)
        assert len(project.metadata) == 0
    
    def test_serialization_roundtrip(self, sample_project):
        """Test that serialization and deserialization preserve data."""
        # Add some metadata
        sample_project.metadata = {'test': 'value', 'number': 42}
        
        # Serialize
        data = sample_project.to_dict()
        
        # Deserialize
        restored_project = Project.from_dict(data)
        
        assert restored_project.name == sample_project.name
        assert restored_project.description == sample_project.description
        assert restored_project.version == sample_project.version
        assert restored_project.metadata == sample_project.metadata


class TestStringRepresentation:
    """Test string representation methods."""
    
    def test_str_representation_empty_project(self, sample_project):
        """Test string representation of empty project."""
        str_repr = str(sample_project)
        assert "Project" in str_repr
        assert "Test Project" in str_repr
        assert "items=0" in str_repr
    
    def test_str_representation_populated_project(self, populated_project):
        """Test string representation of populated project."""
        project, _, _, _, _ = populated_project
        
        str_repr = str(project)
        assert "Project" in str_repr
        assert "Populated Project" in str_repr
        assert "items=4" in str_repr
    
    def test_repr_representation(self, sample_project):
        """Test repr representation matches str representation."""
        assert repr(sample_project) == str(sample_project)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_add_same_item_twice(self, sample_project, sample_item):
        """Test adding the same item twice (should update index)."""
        sample_project.add_item(sample_item)
        original_count = len(sample_project.items_index)
        
        # Adding the same item again should not increase count
        sample_project.add_item(sample_item)
        
        assert len(sample_project.items_index) == original_count
        assert sample_project.items_index[sample_item.id] == sample_item
    
    def test_remove_item_not_in_project(self, sample_project, sample_item):
        """Test removing an item that's not in the project."""
        # Should not raise an exception
        sample_project.remove_item(sample_item)
        assert len(sample_project.items_index) == 0
    
    def test_add_item_with_duplicate_id(self, sample_project):
        """Test adding items with duplicate IDs."""
        item1 = Item(id="duplicate-id", name="Item 1")
        item2 = Item(id="duplicate-id", name="Item 2")
        
        sample_project.add_item(item1)
        sample_project.add_item(item2)
        
        # The second item should overwrite the first in the index
        assert len(sample_project.items_index) == 1
        assert sample_project.items_index["duplicate-id"] == item2
    
    def test_nested_collections(self, sample_project):
        """Test deeply nested collections."""
        collection1 = ItemCollection(name="Collection 1")
        collection2 = ItemCollection(name="Collection 2")
        collection3 = ItemCollection(name="Collection 3")
        item = Item(name="Deep Item")
        
        sample_project.add_item(collection1)
        sample_project.add_item(collection2, collection1.id)
        sample_project.add_item(collection3, collection2.id)
        sample_project.add_item(item, collection3.id)
        
        assert len(sample_project.items_index) == 4
        assert sample_project.find_item(item.id) == item
        assert item.parent_id == collection3.id
    
    def test_cannot_remove_root_item(self, sample_project):
        """Test that attempting to remove the root item raises ValueError."""
        root_item = sample_project.root
        
        with pytest.raises(ValueError, match="Cannot remove the root item directly"):
            sample_project.remove_item(root_item)
        
        # Root should still be present and unchanged
        assert sample_project.root == root_item
        assert len(sample_project.items_index) == 0  # Root is not in items_index
    
    def test_cannot_remove_root_item_by_id(self, sample_project):
        """Test that attempting to remove the root item by ID raises ValueError."""
        root_id = sample_project.root.id
        original_root = sample_project.root
        
        with pytest.raises(ValueError, match="Cannot remove the root item directly"):
            sample_project.remove_item_by_id(root_id)
        
        # Root should still be present and unchanged
        assert sample_project.root == original_root
        assert sample_project.root.id == root_id
        assert len(sample_project.items_index) == 0  # Root is not in items_index


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_project_reorganization(self, sample_project):
        """Test moving items between collections."""
        # Create structure: Root -> Collection1 -> Item1, Item2
        #                        -> Collection2 -> Item3
        collection1 = ItemCollection(name="Collection 1")
        collection2 = ItemCollection(name="Collection 2")
        item1 = Item(name="Item 1")
        item2 = Item(name="Item 2")
        item3 = Item(name="Item 3")
        
        sample_project.add_item(collection1)
        sample_project.add_item(collection2)
        sample_project.add_item(item1, collection1.id)
        sample_project.add_item(item2, collection1.id)
        sample_project.add_item(item3, collection2.id)
        
        # Move item2 from collection1 to collection2
        sample_project.remove_item(item2)
        sample_project.add_item(item2, collection2.id)
        
        assert item2 not in collection1.get_items()
        assert item2 in collection2.get_items()
        assert item2.parent_id == collection2.id
        assert len(sample_project.items_index) == 5
    
    def test_bulk_operations(self, sample_project):
        """Test adding and removing many items."""
        items = [Item(name=f"Item {i}") for i in range(100)]
        
        # Add all items
        for item in items:
            sample_project.add_item(item)
        
        assert len(sample_project.items_index) == 100
        assert len(sample_project.get_all_items()) == 100
        assert len(sample_project.get_root_items()) == 100
        
        # Remove half the items
        for item in items[:50]:
            sample_project.remove_item(item)
        
        assert len(sample_project.items_index) == 50
        assert len(sample_project.get_all_items()) == 50
        assert len(sample_project.get_root_items()) == 50
    
    def test_project_with_metadata(self, sample_project):
        """Test project with extensive metadata."""
        sample_project.metadata = {
            'author': 'Test Author',
            'created_date': '2023-01-01',
            'tags': ['analysis', 'visualization', 'demo'],
            'settings': {
                'theme': 'dark',
                'auto_save': True,
                'backup_count': 5
            },
            'custom_fields': {
                'priority': 'high',
                'status': 'active'
            }
        }
        
        # Test serialization preserves complex metadata
        data = sample_project.to_dict()
        restored_project = Project.from_dict(data)
        
        assert restored_project.metadata['author'] == 'Test Author'
        assert restored_project.metadata['tags'] == ['analysis', 'visualization', 'demo']
        assert restored_project.metadata['settings']['theme'] == 'dark'
        assert restored_project.metadata['custom_fields']['priority'] == 'high'


if __name__ == '__main__':
    pytest.main([__file__])
