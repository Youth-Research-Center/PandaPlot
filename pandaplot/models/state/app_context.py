"""
Facade for accessing application state and services.
"""
from typing import Any, TypeVar

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import EventBus
from pandaplot.models.state.app_state import AppState
from pandaplot.services.qtasks import TaskScheduler

T = TypeVar("T")


class AppContext:
    def __init__(
            self, 
            app_state: AppState,
            event_bus: EventBus, 
            managers: list[Any]):
        self.app_state = app_state
        self.event_bus = event_bus
        
        # Create managers dictionary mapping type to instance
        self._managers: dict[type, Any] = {}
        for manager in managers:
            self._managers[type(manager)] = manager
        
        # Keep backward compatibility by storing individual references
        self.command_executor = self.get_manager(CommandExecutor)
        self.ui_controller = self.get_manager(UIController)
        self.task_scheduler = self.get_manager(TaskScheduler)

    def get_manager(self, manager_type: type[T]) -> T:
        """
        Generic method to retrieve a manager instance by its type.
        
        Args:
            manager_type: The type/class of the manager to retrieve
            
        Returns:
            The manager instance of the specified type
            
        Raises:
            KeyError: If no manager of the specified type is registered
            RuntimeError: If the manager is None (not initialized)
        """
        if manager_type not in self._managers:
            raise KeyError(f"Manager of type {manager_type.__name__} not found in AppContext")
        
        manager = self._managers[manager_type]
        if manager is None:
            raise RuntimeError(f"{manager_type.__name__} not initialized in AppContext")
        
        return manager

    def get_app_state(self) -> AppState:
        return self.app_state

    def get_event_bus(self) -> EventBus:
        return self.event_bus

    def get_command_executor(self) -> CommandExecutor:
        return self.get_manager(CommandExecutor)

    def get_ui_controller(self) -> UIController:
        return self.get_manager(UIController)

    def get_task_scheduler(self) -> TaskScheduler:
        return self.get_manager(TaskScheduler)
