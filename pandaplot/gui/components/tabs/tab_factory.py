import logging
from typing import Callable

from PySide6.QtWidgets import QWidget

from pandaplot.models.project.items import Item
from pandaplot.models.state.app_context import AppContext

# Given (app_context, item, parent), lazily import the tab module and
# construct + return the tab widget for that item.
TabLoader = Callable[[AppContext, Item, QWidget], QWidget]


class TabFactory:
    def __init__(self):
        self._registry: dict[type, TabLoader] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, item_class: type, loader: TabLoader) -> None:
        """
        Register a tab loader for an item class:
          - item_class: the Item subclass this loader handles (e.g. Note)
          - loader: callable(app_context, item, parent) -> QWidget; must
            perform its own lazy import of the tab module so registering
            it doesn't force-import heavy tab dependencies.
        """
        self.logger.info(f"Registering tab loader for item type '{item_class.__name__}'")
        self._registry[item_class] = loader

    def create_tab(self, app_context: AppContext, item: Item | None, parent: QWidget) -> QWidget:
        if item is None:
            raise ValueError("Item cannot be None")

        item_class = type(item)
        loader = self._registry.get(item_class)
        if loader is None:
            error_msg = f"Unsupported item type, item class {item_class.__name__}"
            self.logger.error(error_msg + ". Available types: %s", [c.__name__ for c in self._registry])
            raise ValueError(error_msg)

        self.logger.debug("Creating tab for item type '%s'", item_class.__name__)
        return loader(app_context, item, parent)
