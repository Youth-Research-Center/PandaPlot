"""Per-item migrations for sketch raw dicts.

Pure dict -> dict transforms, run before Sketch.from_dict() constructs the
object. Sketches first appear at schema_version 6, so there is nothing to
migrate yet; add an entry here, keyed by the version it upgrades *from*,
when the persisted sketch shape changes.
"""
from collections.abc import Callable

from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION

PER_ITEM_SKETCH_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def migrate_sketch(raw: dict, schema_version: int) -> dict:
    """Upgrade a raw sketch dict saved at `schema_version` to CURRENT_SCHEMA_VERSION."""
    while schema_version < CURRENT_SCHEMA_VERSION:
        migrate = PER_ITEM_SKETCH_MIGRATIONS.get(schema_version)
        if migrate is not None:
            raw = migrate(raw)
        schema_version += 1
    return raw
