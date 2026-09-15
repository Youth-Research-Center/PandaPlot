"""Shared note lookup for note commands."""

import logging
from typing import Optional

from pandaplot.models.project.items import Note

logger = logging.getLogger(__name__)


class NoteFinder:
    """Resolves a note by id within an already-loaded project.

    A resolved item that isn't a Note logs a warning rather than failing
    silently, since it usually means the stored note_id is stale or wrong.
    """

    @staticmethod
    def find(project, note_id: str) -> Optional[Note]:
        item = project.find_item(note_id)
        if item is None:
            return None

        if not isinstance(item, Note):
            logger.warning(
                "NoteFinder: item '%s' is not a Note (got %s)",
                note_id, type(item).__name__,
            )
            return None

        return item
