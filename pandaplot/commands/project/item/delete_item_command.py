from pandaplot.commands.base_command import Command
from pandaplot.models.project.items.item import Item
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController
from typing import Optional, Dict, Any, Type, override


class DeleteItemCommand(Command):
    """
    Generic command to delete any project item using to_dict/from_dict serialization.
    This command works with any item type that extends the Item base class.
    """
    
    def __init__(self, app_context: AppContext, item_id: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.item_id = item_id
        
        # Store state for undo
        self.deleted_item_data: Optional[Dict[str, Any]] = None
        self.deleted_item_class: Optional[Type[Item]] = None
        self.parent_item: Optional[Item] = None
    
    @override
    def execute(self) -> bool:
        """Execute the delete item command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Delete Item", 
                    "No project is currently loaded."
                )
                return False
                
            project = self.app_state.current_project
            if not project:
                return False
            
            # Find the item to delete
            item = project.find_item(self.item_id)
            if item is None:
                self.ui_controller.show_warning_message(
                    "Delete Item", 
                    f"Item '{self.item_id}' not found in the project."
                )
                return False
            
            # Store the item's class type and serialized data for undo
            self.deleted_item_class = type(item)
            self.deleted_item_data = item.to_dict()
            
            # Find the parent to store the relationship
            if item.parent_id:
                self.parent_item = project.find_item(item.parent_id)
            
            # Get item name for user confirmation
            item_name = getattr(item, 'name', self.item_id)
            item_type = self.deleted_item_class.__name__.lower()
            
            # Confirm deletion
            response = self.ui_controller.show_question(
                "Delete Item",
                f"Are you sure you want to delete the {item_type} '{item_name}'?\nThis action cannot be undone."
            )
            if not response:
                return False
            
            # Remove the item from the project
            project.remove_item(item)
            
            # Emit event
            self.app_state.event_bus.emit('item_deleted', {
                'project': project,
                'item_id': self.item_id,
                'item_type': item_type,
                'item_name': item_name,
                'item_data': self.deleted_item_data
            })
            
            print(f"DeleteItemCommand: Deleted {item_type} '{item_name}' (ID: {self.item_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete item: {str(e)}"
            print(f"DeleteItemCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Delete Item Error", error_msg)
            return False
    
    def undo(self) -> bool:
        """Undo the delete item command."""
        try:
            if (self.deleted_item_data is None or 
                self.deleted_item_class is None or 
                not self.app_state.has_project):
                return False
                
            project = self.app_state.current_project
            if not project:
                return False
            
            # Recreate the item from its serialized data
            restored_item = self.deleted_item_class.from_dict(self.deleted_item_data)
            
            # Determine the parent for restoration
            parent_id = None
            if self.parent_item is not None:
                parent_id = self.parent_item.id
            
            # Add the item back to the project
            project.add_item(restored_item, parent_id=parent_id)
            
            # Get item info for logging
            item_name = getattr(restored_item, 'name', self.item_id)
            item_type = self.deleted_item_class.__name__.lower()
            
            # Emit event
            self.app_state.event_bus.emit('item_restored', {
                'project': project,
                'item_id': self.item_id,
                'item_type': item_type,
                'item_name': item_name,
                'item': restored_item
            })
            
            print(f"DeleteItemCommand: Restored {item_type} '{item_name}' (ID: {self.item_id})")
            return True
                
        except Exception as e:
            error_msg = f"Failed to undo delete item: {str(e)}"
            print(f"DeleteItemCommand Undo Error: {error_msg}")
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return False
            
    def redo(self) -> bool:
        """Redo the delete item command."""
        try:
            if (self.deleted_item_data is None or 
                self.deleted_item_class is None or 
                not self.app_state.has_project):
                return False
                
            project = self.app_state.current_project
            if not project:
                return False
            
            # Find the restored item and delete it again
            item = project.find_item(self.item_id)
            if item is None:
                return False
            
            # Remove the item from the project
            project.remove_item(item)
            
            # Get item info for logging and events
            item_name = getattr(item, 'name', self.item_id)
            item_type = self.deleted_item_class.__name__.lower()
            
            # Emit event
            self.app_state.event_bus.emit('item_deleted', {
                'project': project,
                'item_id': self.item_id,
                'item_type': item_type,
                'item_name': item_name,
                'item_data': self.deleted_item_data
            })
            
            print(f"DeleteItemCommand: Redone deletion of {item_type} '{item_name}' (ID: {self.item_id})")
            return True
                
        except Exception as e:
            error_msg = f"Failed to redo delete item: {str(e)}"
            print(f"DeleteItemCommand Redo Error: {error_msg}")
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
