"""Look a command's dataset up again by id before undo or redo (#666)."""

import logging
from typing import Any, Protocol

from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext


class DatasetCommand(Protocol):
    """A command that changed one dataset and kept it as ``dataset``."""

    app_context: AppContext
    dataset_id: Any
    dataset: Any
    logger: logging.Logger


def rebind_live_dataset(command: DatasetCommand, action: str) -> bool:
    """Point ``command.dataset`` at the live dataset with ``command.dataset_id`` before an undo or redo.

    A command must not reuse the ``Dataset`` object it found in ``execute()``: deleting the dataset and undoing the
    delete rebuilds it from a snapshot, so the retained object is detached and edits to it would never be seen.

    A command whose ``dataset`` is still None never changed anything; it is left alone so the command's own checks
    report that.

    Args:
        command: The command about to undo or redo.
        action: What is being attempted, such as ``"AddColumnsCommand.undo"``, for the warning.

    Returns:
        False, with a warning logged, if the dataset no longer exists in the current project. The caller then returns
        ``CommandResult.ABORTED`` without changing anything, so the command stays where it is in the history.
    """
    if command.dataset is None:
        return True
    project = get_current_project(command.app_context)
    item = project.find_item(command.dataset_id) if project is not None else None
    if not isinstance(item, Dataset):
        command.logger.warning("%s: dataset '%s' no longer exists; nothing changed", action, command.dataset_id)
        return False
    command.dataset = item
    return True
