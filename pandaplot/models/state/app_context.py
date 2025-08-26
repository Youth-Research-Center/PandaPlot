"""
Facade for accessing application state and services.
"""
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import EventBus
from pandaplot.models.state import AppState
from pandaplot.services.config_manager import ConfigManager
from pandaplot.services.theme_manager import ThemeManager


class AppContext:
    def __init__(self, app_state: AppState, event_bus: EventBus, command_executor: CommandExecutor, ui_controller: UIController, config_manager: ConfigManager, theme_manager: ThemeManager):
        self.app_state = app_state
        self.event_bus = event_bus
        self.command_executor = command_executor
        self.ui_controller = ui_controller
        self.config_manager = config_manager
        self.theme_manager = theme_manager

    def get_app_state(self) -> AppState:
        return self.app_state

    def get_event_bus(self) -> EventBus:
        return self.event_bus

    def get_command_executor(self) -> CommandExecutor:
        return self.command_executor

    def get_ui_controller(self) -> UIController:
        return self.ui_controller

    def get_config_manager(self) -> ConfigManager:
        if self.config_manager is None:
            raise RuntimeError("ConfigManager not initialized in AppContext")
        return self.config_manager
    
    def get_theme_manager(self) -> ThemeManager:
        if self.theme_manager is None:
            raise RuntimeError("ThemeManager not initialized in AppContext")
        return self.theme_manager
