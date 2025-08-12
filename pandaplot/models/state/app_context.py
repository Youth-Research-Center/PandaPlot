"""
Facade for accessing application state and services.
"""
from pandaplot.models.state.app_state import AppState
from pandaplot.models.events.event_bus import EventBus
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.storage.project_data_manager import ProjectDataManager


class AppContext:
    def __init__(self, app_state: AppState, event_bus: EventBus, command_executor: CommandExecutor, ui_controller: UIController):
        self.app_state = app_state
        self.event_bus = event_bus
        self.command_executor = command_executor
        self.ui_controller = ui_controller

    def get_app_state(self) -> AppState:
        return self.app_state

    def get_event_bus(self) -> EventBus:
        return self.event_bus
    
    def get_command_executor(self) -> CommandExecutor:
        return self.command_executor
    
    def get_ui_controller(self) -> UIController:
        return self.ui_controller