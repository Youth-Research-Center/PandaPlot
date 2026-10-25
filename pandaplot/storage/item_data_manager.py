from abc import ABC, abstractmethod
from typing import TypeVar
from zipfile import ZipFile

from pandaplot.models.project.items.item import Item

TItem = TypeVar("TItem", bound=Item)


class ItemDataManager[TItem: Item](ABC):
    """Base class for (de)serializing one Item subtype to/from a project zip.

    Generic over the concrete Item subtype so each manager (e.g.
    ItemDataManager[Chart]) gets accurately typed item/item_class parameters
    instead of a narrowing override of an untyped/Item-typed base signature.
    """

    @abstractmethod
    def save(self, item: TItem, zip_file: ZipFile, path_in_zip: str) -> None:
        """Serialize and write item data to given path in the zip."""
        raise NotImplementedError

    @abstractmethod
    def load(self, item_class: type[TItem], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> TItem:
        """Read and deserialize item data from given path in the zip."""
        raise NotImplementedError
