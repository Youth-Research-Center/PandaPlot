"""
Visitor pattern implementation for traversing project item hierarchies.
"""

from typing import Protocol, Any
from pandaplot.models.project.items import Item, ItemCollection, Folder, Note, Dataset, Chart


class ItemVisitor(Protocol):
    """Protocol defining the visitor interface for project items."""
    
    def visit_folder(self, folder: Folder, context: Any = None) -> Any:
        """Visit a folder item."""
        ...
    
    def visit_note(self, note: Note, context: Any = None) -> Any:
        """Visit a note item."""
        ...
    
    def visit_dataset(self, dataset: Dataset, context: Any = None) -> Any:
        """Visit a dataset item."""
        ...
    
    def visit_chart(self, chart: Chart, context: Any = None) -> Any:
        """Visit a chart item."""
        ...
    
    def visit_item_collection(self, collection: ItemCollection, context: Any = None) -> Any:
        """Visit a generic item collection."""
        ...
    
    def visit_item(self, item: Item, context: Any = None) -> Any:
        """Visit a generic item (fallback)."""
        ...


class ProjectTreeBuilder:
    """
    Visitor that builds a tree representation of project items.
    This can be used with different UI frameworks by providing different tree item factories.
    """
    
    def __init__(self, tree_item_factory):
        """
        Initialize with a factory function that creates tree items.
        
        Args:
            tree_item_factory: Function that takes (name, item_type, item_data) and returns a tree item
        """
        self.tree_item_factory = tree_item_factory
    
    def build_tree(self, root_collection: ItemCollection, parent_tree_item: Any = None) -> Any:
        """
        Build a tree structure from the project hierarchy.
        
        Args:
            root_collection: The root ItemCollection to start from
            parent_tree_item: The parent tree item to attach children to
            
        Returns:
            The root tree item
        """
        # Create tree item for root if not provided
        if parent_tree_item is None:
            parent_tree_item = self.tree_item_factory(
                f"📁 {root_collection.name}",
                "project", 
                {'type': 'project', 'id': root_collection.id, 'data': root_collection}
            )
        
        # Visit all items in the collection
        for item in root_collection.get_items():
            tree_item = self.visit(item, parent_tree_item)
            self.attach_tree_item(parent_tree_item, tree_item)
        
        return parent_tree_item
    
    def visit(self, item: Item, parent_context: Any = None) -> Any:
        """
        Visit an item and dispatch to the appropriate method based on type.
        """
        # Dispatch based on item type
        if isinstance(item, Folder):
            return self.visit_folder(item, parent_context)
        elif isinstance(item, Note):
            return self.visit_note(item, parent_context)
        elif isinstance(item, Dataset):
            return self.visit_dataset(item, parent_context)
        elif isinstance(item, Chart):
            return self.visit_chart(item, parent_context)
        elif isinstance(item, ItemCollection):
            return self.visit_item_collection(item, parent_context)
        else:
            return self.visit_item(item, parent_context)
    
    def visit_folder(self, folder: Folder, parent_context: Any = None) -> Any:
        """Visit a folder and recursively build its children."""
        tree_item = self.tree_item_factory(
            f"📁 {folder.name}",
            "folder",
            {'type': 'folder', 'id': folder.id, 'data': folder}
        )
        
        # Recursively add child items
        for child_item in folder.get_items():
            child_tree_item = self.visit(child_item, tree_item)
            self.attach_tree_item(tree_item, child_tree_item)
        
        return tree_item
    
    def visit_note(self, note: Note, parent_context: Any = None) -> Any:
        """Visit a note item."""
        return self.tree_item_factory(
            f"📝 {note.name}",
            "note",
            {'type': 'note', 'id': note.id, 'data': note}
        )
    
    def visit_dataset(self, dataset: Dataset, parent_context: Any = None) -> Any:
        """Visit a dataset item."""
        return self.tree_item_factory(
            f"📊 {dataset.name}",
            "dataset",
            {'type': 'dataset', 'id': dataset.id, 'data': dataset}
        )
    
    def visit_chart(self, chart: Chart, parent_context: Any = None) -> Any:
        """Visit a chart item."""
        return self.tree_item_factory(
            f"📈 {chart.name}",
            "chart",
            {'type': 'chart', 'id': chart.id, 'data': chart}
        )
    
    def visit_item_collection(self, collection: ItemCollection, parent_context: Any = None) -> Any:
        """Visit a generic item collection."""
        tree_item = self.tree_item_factory(
            f"📁 {collection.name}",
            "collection",
            {'type': 'collection', 'id': collection.id, 'data': collection}
        )
        
        # Recursively add child items
        for child_item in collection.get_items():
            child_tree_item = self.visit(child_item, tree_item)
            self.attach_tree_item(tree_item, child_tree_item)
        
        return tree_item
    
    def visit_item(self, item: Item, parent_context: Any = None) -> Any:
        """Visit a generic item (fallback)."""
        return self.tree_item_factory(
            f"📄 {item.name}",
            "item",
            {'type': 'item', 'id': item.id, 'data': item}
        )
    
    def attach_tree_item(self, parent_tree_item: Any, child_tree_item: Any):
        """
        Attach a child tree item to a parent tree item.
        This method should be overridden or the tree_item_factory should handle this.
        """
        # Default implementation - assumes parent has addChild method (like QTreeWidgetItem)
        if hasattr(parent_tree_item, 'addChild'):
            parent_tree_item.addChild(child_tree_item)
        else:
            # For other tree implementations, this would need to be customized
            pass


class QTreeItemFactory:
    """Factory for creating QTreeWidgetItem instances."""
    
    def __init__(self, qt_tree_widget_item_class):
        """Initialize with the QTreeWidgetItem class."""
        self.QTreeWidgetItem = qt_tree_widget_item_class
    
    def __call__(self, display_text: str, item_type: str, item_data: dict) -> Any:
        """Create a QTreeWidgetItem with the given parameters."""
        from PySide6.QtCore import Qt
        
        tree_item = self.QTreeWidgetItem([display_text])
        tree_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        
        # Set item flags based on type
        if item_type == 'project':
            # Project root is not editable
            tree_item.setFlags(tree_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        else:
            # Other items are editable
            tree_item.setFlags(tree_item.flags() | Qt.ItemFlag.ItemIsEditable)
        
        return tree_item
