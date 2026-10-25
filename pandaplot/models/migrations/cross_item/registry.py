"""Registry of cross-item migrations, keyed by the schema_version they
upgrade *from*. See runner.py for how this is applied."""
from collections.abc import Callable

from pandaplot.models.migrations.cross_item.column_ids import migrate_column_ids
from pandaplot.models.project.project import Project

CROSS_ITEM_MIGRATIONS: dict[int, Callable[[Project], None]] = {
    0: migrate_column_ids,
}
