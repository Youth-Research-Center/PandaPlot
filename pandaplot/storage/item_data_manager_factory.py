from pandaplot.storage.item_data_manager import ItemDataManager

class RegistryItem:
    def __init__(self, item_class: type, manager: ItemDataManager, extension: str):
        self.item_class = item_class
        self.manager = manager
        self.extension = extension

class ItemDataManagerFactory:
    def __init__(self):
        self._registry : dict[str, RegistryItem] = {}

    def register(self, type_name: str, item_class: type, manager: ItemDataManager, extension: str):
        """
        Register a new item type with:
          - type_name: string identifier ("note", "chart", etc.)
          - item_class: Python class implementing the Item
          - manager: Data manager instance implementing IItemDataManager
          - extension: base file extension (without dot) for save/load
        """
        self._registry[type_name] = RegistryItem(item_class, manager, extension)

    def get_manager(self, type_name: str) -> ItemDataManager:
        try:
            return self._registry[type_name].manager
        except KeyError:
            raise ValueError(f"No data manager registered for type '{type_name}'")

    def resolve_item_class(self, type_name: str) -> type:
        try:
            return self._registry[type_name].item_class
        except KeyError:
            raise ValueError(f"No item class registered for type '{type_name}'")

    def get_extension_for_type(self, type_name: str) -> str:
        try:
            return self._registry[type_name].extension
        except KeyError:
            raise ValueError(f"No extension registered for type '{type_name}'")

    def get_registered_types(self) -> list[str]:
        return list(self._registry.keys())

