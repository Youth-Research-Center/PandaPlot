"""
Unit tests for pandaplot.models.project.items.note module.

Tests cover the Note class, including:
- Note creation and initialization
- Content management operations
- Tag management (add, remove)
- Serialization and deserialization
- Inheritance from Item class
- Edge cases and error handling
"""

import pytest
import uuid
import time
from pandaplot.models.project.items import Note, Item


# Fixtures
@pytest.fixture
def sample_note_data():
    """Fixture providing test data for notes."""
    return {
        'id': "test-note-123",
        'name': "Test Note",
        'content': "This is a test note content.",
        'tags': ['test', 'sample', 'demo']
    }


@pytest.fixture
def sample_note():
    """Create a sample note for testing."""
    return Note(
        name="Sample Note",
        content="Sample content for testing",
        tags=['sample', 'test']
    )


@pytest.fixture
def empty_note():
    """Create an empty note for testing."""
    return Note()


class TestNoteInitialization:
    """Test note initialization and basic properties."""
    
    def test_default_initialization(self):
        """Test note creation with default parameters."""
        note = Note()
        
        # Check inherited properties from Item
        assert isinstance(note.id, str)
        assert note.id != ""
        # Verify it's a valid UUID
        uuid.UUID(note.id)  # This will raise ValueError if invalid
        
        assert note.name == ""
        assert note.parent_id is None
        assert isinstance(note.created_at, str)
        assert note.modified_at == note.created_at
        assert isinstance(note.metadata, dict)
        assert len(note.metadata) == 0
        
        # Check note-specific properties
        assert note.content == ""
        assert isinstance(note.tags, list)
        assert len(note.tags) == 0
    
    def test_custom_initialization(self, sample_note_data):
        """Test note creation with custom parameters."""
        note = Note(
            id=sample_note_data['id'],
            name=sample_note_data['name'],
            content=sample_note_data['content'],
            tags=sample_note_data['tags'].copy()
        )
        
        assert note.id == sample_note_data['id']
        assert note.name == sample_note_data['name']
        assert note.content == sample_note_data['content']
        assert note.tags == sample_note_data['tags']
        assert note.tags is not sample_note_data['tags']  # Should be a copy
    
    def test_partial_initialization(self):
        """Test note creation with partial parameters."""
        note = Note(name="Partial Note", content="Some content")
        
        assert isinstance(note.id, str)
        assert note.name == "Partial Note"
        assert note.content == "Some content"
        assert isinstance(note.tags, list)
        assert len(note.tags) == 0
    
    def test_tags_none_initialization(self):
        """Test note creation with tags=None."""
        note = Note(name="Test", tags=None)
        
        assert isinstance(note.tags, list)
        assert len(note.tags) == 0


class TestContentManagement:
    """Test content management operations."""
    
    def test_update_content(self, sample_note):
        """Test updating note content."""
        original_content = sample_note.content
        original_modified = sample_note.modified_at
        new_content = "Updated content for the note"
        
        # Sleep briefly to ensure time difference
        time.sleep(0.001)
        
        sample_note.update_content(new_content)
        
        assert sample_note.content == new_content
        assert sample_note.content != original_content
        assert sample_note.modified_at != original_modified
        assert sample_note.modified_at > original_modified
    
    def test_update_content_empty_string(self, sample_note):
        """Test updating content to empty string."""
        original_modified = sample_note.modified_at
        
        time.sleep(0.001)
        sample_note.update_content("")
        
        assert sample_note.content == ""
        assert sample_note.modified_at != original_modified
    
    def test_update_content_with_special_characters(self, sample_note):
        """Test updating content with special characters."""
        special_content = "Content with special chars: äöü, 中文, 🚀, \n\t"
        
        sample_note.update_content(special_content)
        
        assert sample_note.content == special_content


class TestTagManagement:
    """Test tag management operations."""
    
    def test_add_tag_to_empty_note(self, empty_note):
        """Test adding a tag to a note with no tags."""
        original_modified = empty_note.modified_at
        
        time.sleep(0.001)
        empty_note.add_tag("new-tag")
        
        assert "new-tag" in empty_note.tags
        assert len(empty_note.tags) == 1
        assert empty_note.modified_at != original_modified
    
    def test_add_tag_to_existing_tags(self, sample_note):
        """Test adding a tag to a note that already has tags."""
        original_tags = sample_note.tags.copy()
        original_modified = sample_note.modified_at
        
        time.sleep(0.001)
        sample_note.add_tag("additional-tag")
        
        assert "additional-tag" in sample_note.tags
        assert len(sample_note.tags) == len(original_tags) + 1
        assert all(tag in sample_note.tags for tag in original_tags)
        assert sample_note.modified_at != original_modified
    
    def test_add_duplicate_tag(self, sample_note):
        """Test adding a tag that already exists."""
        original_tags = sample_note.tags.copy()
        original_modified = sample_note.modified_at
        existing_tag = original_tags[0]
        
        time.sleep(0.001)
        sample_note.add_tag(existing_tag)
        
        # Should not add duplicate, and should not update modified time
        assert sample_note.tags == original_tags
        assert len(sample_note.tags) == len(original_tags)
        assert sample_note.modified_at == original_modified
    
    def test_remove_existing_tag(self, sample_note):
        """Test removing an existing tag."""
        original_tags = sample_note.tags.copy()
        original_modified = sample_note.modified_at
        tag_to_remove = original_tags[0]
        
        time.sleep(0.001)
        sample_note.remove_tag(tag_to_remove)
        
        assert tag_to_remove not in sample_note.tags
        assert len(sample_note.tags) == len(original_tags) - 1
        assert sample_note.modified_at != original_modified
    
    def test_remove_nonexistent_tag(self, sample_note):
        """Test removing a tag that doesn't exist."""
        original_tags = sample_note.tags.copy()
        original_modified = sample_note.modified_at
        
        time.sleep(0.001)
        sample_note.remove_tag("nonexistent-tag")
        
        # Should not change tags or modified time
        assert sample_note.tags == original_tags
        assert sample_note.modified_at == original_modified
    
    def test_remove_tag_from_empty_note(self, empty_note):
        """Test removing a tag from a note with no tags."""
        original_modified = empty_note.modified_at
        
        time.sleep(0.001)
        empty_note.remove_tag("any-tag")
        
        assert len(empty_note.tags) == 0
        assert empty_note.modified_at == original_modified
    
    def test_tag_operations_sequence(self, empty_note):
        """Test a sequence of tag operations."""
        # Add multiple tags
        empty_note.add_tag("tag1")
        empty_note.add_tag("tag2")
        empty_note.add_tag("tag3")
        
        assert len(empty_note.tags) == 3
        assert "tag1" in empty_note.tags
        assert "tag2" in empty_note.tags
        assert "tag3" in empty_note.tags
        
        # Remove one tag
        empty_note.remove_tag("tag2")
        
        assert len(empty_note.tags) == 2
        assert "tag1" in empty_note.tags
        assert "tag2" not in empty_note.tags
        assert "tag3" in empty_note.tags
        
        # Try to add duplicate
        empty_note.add_tag("tag1")
        assert len(empty_note.tags) == 2  # Should not increase


class TestSerialization:
    """Test serialization and deserialization."""
    
    def test_to_dict_complete_note(self, sample_note_data):
        """Test serializing a complete note to dictionary."""
        note = Note(
            id=sample_note_data['id'],
            name=sample_note_data['name'],
            content=sample_note_data['content'],
            tags=sample_note_data['tags'].copy()
        )
        note.parent_id = "parent-123"
        note.metadata = {"key": "value", "number": 42}
        
        result = note.to_dict()
        
        # Check inherited Item fields
        assert result['id'] == sample_note_data['id']
        assert result['name'] == sample_note_data['name']
        assert result['parent_id'] == "parent-123"
        assert 'created_at' in result
        assert 'modified_at' in result
        assert result['metadata'] == {"key": "value", "number": 42}
        
        # Check Note-specific fields
        assert result['content'] == sample_note_data['content']
        assert result['tags'] == sample_note_data['tags']
    
    def test_to_dict_empty_note(self, empty_note):
        """Test serializing an empty note to dictionary."""
        result = empty_note.to_dict()
        
        assert isinstance(result, dict)
        assert 'id' in result
        assert result['name'] == ""
        assert result['content'] == ""
        assert result['tags'] == []
        assert result['parent_id'] is None
        assert 'created_at' in result
        assert 'modified_at' in result
        assert result['metadata'] == {}
    
    def test_from_dict_complete_data(self, sample_note_data):
        """Test creating note from complete dictionary data."""
        data = {
            'id': sample_note_data['id'],
            'name': sample_note_data['name'],
            'content': sample_note_data['content'],
            'tags': sample_note_data['tags'].copy(),
            'parent_id': "parent-123",
            'created_at': "2023-01-01T12:00:00",
            'modified_at': "2023-01-01T13:00:00",
            'metadata': {"key": "value"}
        }
        
        note = Note.from_dict(data)
        
        # Check all fields are correctly set
        assert note.id == sample_note_data['id']
        assert note.name == sample_note_data['name']
        assert note.content == sample_note_data['content']
        assert note.tags == sample_note_data['tags']
        assert note.parent_id == "parent-123"
        assert note.created_at == "2023-01-01T12:00:00"
        assert note.modified_at == "2023-01-01T13:00:00"
        assert note.metadata == {"key": "value"}
    
    def test_from_dict_minimal_data(self):
        """Test creating note from minimal dictionary data."""
        data = {}
        
        note = Note.from_dict(data)
        
        # Check defaults are applied
        assert isinstance(note.id, str)
        assert note.id != ""
        # Verify it's a valid UUID
        uuid.UUID(note.id)
        
        assert note.name == ""
        assert note.content == ""
        assert note.tags == []
        assert note.parent_id is None
        assert isinstance(note.created_at, str)
        assert note.modified_at == note.created_at
        assert note.metadata == {}
    
    def test_from_dict_partial_data(self):
        """Test creating note from partial dictionary data."""
        data = {
            'name': 'Partial Note',
            'content': 'Some content',
            'tags': ['tag1', 'tag2']
        }
        
        note = Note.from_dict(data)
        
        assert isinstance(note.id, str)
        assert note.name == 'Partial Note'
        assert note.content == 'Some content'
        assert note.tags == ['tag1', 'tag2']
        assert note.parent_id is None
    
    def test_serialization_roundtrip(self, sample_note):
        """Test that serialization and deserialization preserve data."""
        # Add some metadata
        sample_note.metadata = {'test': 'value', 'number': 42}
        sample_note.parent_id = "test-parent"
        
        # Serialize
        data = sample_note.to_dict()
        
        # Deserialize
        restored_note = Note.from_dict(data)
        
        # Compare all attributes
        assert restored_note.id == sample_note.id
        assert restored_note.name == sample_note.name
        assert restored_note.content == sample_note.content
        assert restored_note.tags == sample_note.tags
        assert restored_note.parent_id == sample_note.parent_id
        assert restored_note.created_at == sample_note.created_at
        assert restored_note.modified_at == sample_note.modified_at
        assert restored_note.metadata == sample_note.metadata


class TestInheritance:
    """Test inheritance from Item class."""
    
    def test_is_instance_of_item(self, sample_note):
        """Test that Note is an instance of Item."""
        assert isinstance(sample_note, Item)
    
    def test_inherited_methods(self, sample_note):
        """Test that inherited methods work correctly."""
        original_name = sample_note.name
        original_modified = sample_note.modified_at
        new_name = "Updated Note Name"
        
        time.sleep(0.001)
        sample_note.update_name(new_name)
        
        assert sample_note.name == new_name
        assert sample_note.name != original_name
        assert sample_note.modified_at != original_modified
    
    def test_inherited_str_representation(self, sample_note):
        """Test string representation from Item."""
        str_repr = str(sample_note)
        assert "Note" in str_repr
        assert sample_note.id in str_repr
        assert sample_note.name in str_repr
    
    def test_inherited_repr_representation(self, sample_note):
        """Test repr representation from Item."""
        assert repr(sample_note) == str(sample_note)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_very_long_content(self, empty_note):
        """Test note with very long content."""
        long_content = "x" * 10000  # 10KB of content
        
        empty_note.update_content(long_content)
        
        assert empty_note.content == long_content
        assert len(empty_note.content) == 10000
    
    def test_content_with_newlines_and_tabs(self, empty_note):
        """Test content with various whitespace characters."""
        complex_content = "Line 1\nLine 2\n\tIndented line\r\nWindows line ending"
        
        empty_note.update_content(complex_content)
        
        assert empty_note.content == complex_content
    
    def test_unicode_content(self, empty_note):
        """Test content with Unicode characters."""
        unicode_content = "Unicode: äöü ñ 中文 日本語 🚀 💻 📝"
        
        empty_note.update_content(unicode_content)
        
        assert empty_note.content == unicode_content
    
    def test_many_tags(self, empty_note):
        """Test note with many tags."""
        for i in range(100):
            empty_note.add_tag(f"tag{i}")
        
        assert len(empty_note.tags) == 100
        assert "tag0" in empty_note.tags
        assert "tag99" in empty_note.tags
    
    def test_tags_with_special_characters(self, empty_note):
        """Test tags with special characters."""
        special_tags = ["tag-with-dash", "tag_with_underscore", "tag.with.dots", "tag with spaces"]
        
        for tag in special_tags:
            empty_note.add_tag(tag)
        
        assert len(empty_note.tags) == len(special_tags)
        for tag in special_tags:
            assert tag in empty_note.tags
    
    def test_empty_string_tag(self, empty_note):
        """Test adding empty string as tag."""
        empty_note.add_tag("")
        
        assert "" in empty_note.tags
        assert len(empty_note.tags) == 1
    
    def test_duplicate_tags_case_sensitivity(self, empty_note):
        """Test that tag comparison is case-sensitive."""
        empty_note.add_tag("Tag")
        empty_note.add_tag("tag")
        empty_note.add_tag("TAG")
        
        assert len(empty_note.tags) == 3
        assert "Tag" in empty_note.tags
        assert "tag" in empty_note.tags
        assert "TAG" in empty_note.tags


class TestNoteSpecificFunctionality:
    """Test functionality specific to notes."""
    
    def test_note_as_documentation(self):
        """Test using note for documentation purposes."""
        doc_note = Note(
            name="API Documentation",
            content="# API Reference\n\n## Authentication\n\nUse Bearer token...",
            tags=["documentation", "api", "reference"]
        )
        
        assert doc_note.name == "API Documentation"
        assert "# API Reference" in doc_note.content
        assert "documentation" in doc_note.tags
    
    def test_note_as_todo_item(self):
        """Test using note as a todo item."""
        todo_note = Note(
            name="Fix login bug",
            content="- [ ] Investigate login timeout\n- [ ] Update session handling\n- [ ] Test edge cases",
            tags=["todo", "bug", "urgent"]
        )
        
        assert "Fix login bug" in todo_note.name
        assert "- [ ]" in todo_note.content
        assert "urgent" in todo_note.tags
    
    def test_note_content_modification_tracking(self, empty_note):
        """Test that content modifications update timestamps correctly."""
        # Initial state
        original_created = empty_note.created_at
        original_modified = empty_note.modified_at
        assert original_created == original_modified
        
        time.sleep(0.001)
        empty_note.update_content("First update")
        first_modified = empty_note.modified_at
        
        time.sleep(0.001)
        empty_note.update_content("Second update")
        second_modified = empty_note.modified_at
        
        # Verify progression
        assert original_created == original_modified
        assert first_modified > original_modified
        assert second_modified > first_modified
        assert empty_note.created_at == original_created  # Should not change


if __name__ == '__main__':
    pytest.main([__file__])
