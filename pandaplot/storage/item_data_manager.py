from abc import ABC, abstractmethod

class ItemDataManager(ABC):
    @abstractmethod
    def save(self, item, zip_file, path_in_zip: str) -> None:
        """Serialize and write item data to given path in the zip."""
        raise NotImplementedError

    @abstractmethod
    def load(self, item_class, zip_file, path_in_zip: str):
        """Read and deserialize item data from given path in the zip."""
        raise NotImplementedError
