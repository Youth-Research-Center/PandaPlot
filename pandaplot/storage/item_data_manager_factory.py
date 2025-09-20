import logging
from pandaplot.storage.item_data_manager import ItemDataManager

class RegistryItem:
    def __init__(self, item_class: type, manager: ItemDataManager, extension: str):
        self.item_class = item_class
        self.manager = manager
        self.extension = extension

class ItemDataManagerFactory:
    def __init__(self):
        self._registry : dict[str, RegistryItem] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, type_name: str, item_class: type, manager: ItemDataManager, extension: str):
        """
        Register a new item type with:
          - type_name: string identifier ("note", "chart", etc.)
          - item_class: Python class implementing the Item
          - manager: Data manager instance implementing IItemDataManager
          - extension: base file extension (without dot) for save/load
        """
        self.logger.info(f"Registering item type '{type_name}' with extension '{extension}'")
        self._registry[type_name] = RegistryItem(item_class, manager, extension)

    def get_manager(self, type_name: str) -> ItemDataManager:
        try:
            manager = self._registry[type_name].manager
            self.logger.debug("Retrieved data manager for type '%s': %s", type_name, type(manager).__name__)
            return manager
        except KeyError:
            error_msg = f"No data manager registered for type '{type_name}'"
            self.logger.error(error_msg + ". Available types: %s", list(self._registry.keys()))
            raise ValueError(error_msg)

    def resolve_item_class(self, type_name: str) -> type:
        try:
            item_class = self._registry[type_name].item_class
            self.logger.debug("Resolved item class for type '%s': %s", type_name, item_class.__name__)
            return item_class
        except KeyError:
            error_msg = f"No item class registered for type '{type_name}'"
            self.logger.error(error_msg + ". Available types: %s", list(self._registry.keys()))
            raise ValueError(error_msg)

    def get_extension_for_type(self, type_name: str) -> str:
        try:
            extension = self._registry[type_name].extension
            self.logger.debug("Retrieved extension for type '%s': %s", type_name, extension)
            return extension
        except KeyError:
            error_msg = f"No extension registered for type '{type_name}'"
            self.logger.error(error_msg + ". Available types: %s", list(self._registry.keys()))
            raise ValueError(error_msg)

    def get_registered_types(self) -> list[str]:
        return list(self._registry.keys())

