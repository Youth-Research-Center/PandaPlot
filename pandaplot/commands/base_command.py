from abc import ABC, abstractmethod
import logging

class Command(ABC):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def execute(self) -> bool:
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}()"