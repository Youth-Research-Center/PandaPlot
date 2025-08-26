"""
Test for the tree visitor pattern implementation.
"""

import unittest
from unittest.mock import Mock
from pandaplot.models.project import Project
from pandaplot.models.project.items import (Folder, Note, Dataset)
from pandaplot.models.project.visitors.tree_visitor import ProjectTreeBuilder


class TestTreeVisitor(unittest.TestCase):
    """Test cases for the tree visitor pattern."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock tree item factory
        self.tree_items = []
        self.tree_structure = {}
        
        def mock_tree_item_factory(display_text, item_type, item_data):
            """Mock tree item factory that records calls."""
            mock_item = Mock()
            mock_item.display_text = display_text
            mock_item.item_type = item_type
            mock_item.item_data = item_data
            mock_item.children = []
            
            # Mock addChild method
            def add_child(child):
                mock_item.children.append(child)
            mock_item.addChild = add_child
            
            self.tree_items.append(mock_item)
            return mock_item
        
        self.tree_item_factory = mock_tree_item_factory
        self.tree_builder = ProjectTreeBuilder(self.tree_item_factory)
    
    def test_visitor_with_simple_hierarchy(self):
        """Test visitor with a simple project hierarchy."""
        # Create a project with some items
        project = Project("Test Project")
        
        # Add a folder
        folder = Folder(name="Documents")
        project.add_item(folder)
        
        # Add a note to the folder
        note = Note(name="Meeting Notes")
        project.add_item(note, parent_id=folder.id)
        
        # Add a dataset to the root
        dataset = Dataset(name="Sales Data")
        project.add_item(dataset)
        
        # Build the tree using the visitor
        root_tree_item = self.tree_builder.build_tree(project.root)
        
        # Verify the structure
        self.assertIsNotNone(root_tree_item)
        self.assertEqual(root_tree_item.display_text, f"📁 {project.root.name}")
        
        # Should have created tree items for folder and dataset at root level
        # Plus the note inside the folder
        expected_items = [
            "📁 Test Project Root",  # Root
            "📁 Documents",          # Folder
            "📝 Meeting Notes",      # Note (child of folder)
            "📊 Sales Data"          # Dataset (child of root)
        ]
        
        actual_display_texts = [item.display_text for item in self.tree_items]
        
        # Check that all expected items were created
        for expected in expected_items:
            self.assertIn(expected, actual_display_texts)
        
        print("✅ Visitor test passed - all items created correctly")
        print(f"Created {len(self.tree_items)} tree items:")
        for item in self.tree_items:
            print(f"  - {item.display_text} ({item.item_type})")
    
    def test_visitor_with_nested_folders(self):
        """Test visitor with nested folder structure."""
        project = Project("Nested Test")
        
        # Create nested structure: Root -> Folder1 -> Folder2 -> Note
        folder1 = Folder(name="Level 1")
        project.add_item(folder1)
        
        folder2 = Folder(name="Level 2")
        project.add_item(folder2, parent_id=folder1.id)
        
        note = Note(name="Deep Note")
        project.add_item(note, parent_id=folder2.id)
        
        # Build the tree
        self.tree_builder.build_tree(project.root)
        
        # Check structure
        self.assertEqual(len(self.tree_items), 4)  # Root + Folder1 + Folder2 + Note
        
        # Find the root item and verify hierarchy
        root_item = None
        for item in self.tree_items:
            if item.display_text == f"📁 {project.root.name}":
                root_item = item
                break
        
        self.assertIsNotNone(root_item)
        print("✅ Nested folder test passed")


if __name__ == '__main__':
    unittest.main()
