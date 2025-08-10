import uuid
from pandaplot.commands.base_command import Command
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController
from typing import Optional
class CreateNoteCommand(Command):
    """
    Command to create a new note in the project.
    """
    
    def __init__(self, app_context: AppContext, note_name: Optional[str] = None, 
                 content: str = "", folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.note_name = note_name
        self.content = content
        self.folder_id = folder_id
        
        # Store state for undo
        self.created_note_id = None
        self.created_note = None
        self.project = None
        
    def execute(self, *args, **kwargs):
        """Execute the create note command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "New Note", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_state.current_project
            if not self.project:
                return False
            
            # Get note name if not provided
            if not self.note_name:
                note_name = "New Note"
            else:
                note_name = self.note_name
            
            # Create note ID
            self.created_note_id = str(uuid.uuid4())
            self.created_note = Note(
                id=self.created_note_id,
                name=note_name,
                content=self.content
            )
            
            # Add note to project using hierarchical structure
            self.project.add_item(self.created_note, parent_id=self.folder_id)
            
            # Emit event
            self.app_state.event_bus.emit('note_created', {
                'project': self.project,
                'note_id': self.created_note_id,
                'note_name': note_name,
                'folder_id': self.folder_id,
                'note': self.created_note
            })
            
            print(f"CreateNoteCommand: Created note '{note_name}' with ID '{self.created_note_id}'")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to create note: {str(e)}"
            print(f"CreateNoteCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Create Note Error", error_msg)
            return False
    
    def undo(self):
        """Undo the create note command."""
        try:
            if self.created_note_id and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    note = project.find_item(self.created_note_id)
                    if note is not None:
                        project.remove_item(note)
                    
                    # Emit event
                    self.app_state.event_bus.emit('note_deleted', {
                        'project': project,
                        'note_id': self.created_note_id,
                        'note': self.created_note
                    })
                    
                    print(f"CreateNoteCommand: Undid creation of note '{self.created_note_id}'")
                
        except Exception as e:
            error_msg = f"Failed to undo create note: {str(e)}"
            print(f"CreateNoteCommand Undo Error: {error_msg}")
            self.ui_controller.show_error_message("Undo Error", error_msg)
            
    def redo(self):
        """Redo the create note command."""
        try:
            if self.created_note_id and self.created_note is not None and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return False
                
                # Re-add the same note object to the project
                project.add_item(self.created_note, parent_id=self.folder_id)
                
                # Emit event
                self.app_state.event_bus.emit('note_created', {
                    'project': project,
                    'note_id': self.created_note_id,
                    'note_name': self.created_note.name,
                    'folder_id': self.folder_id,
                    'note': self.created_note
                })
                
                print(f"CreateNoteCommand: Redone creation of note '{self.created_note.name}' with ID '{self.created_note_id}'")
                return True
            else:
                return False
                
        except Exception as e:
            error_msg = f"Failed to redo create note: {str(e)}"
            print(f"CreateNoteCommand Redo Error: {error_msg}")
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
