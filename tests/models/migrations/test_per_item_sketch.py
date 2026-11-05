"""Tests for the per-item sketch migration dispatcher."""
from unittest.mock import patch

from pandaplot.models.migrations.per_item.sketch import PER_ITEM_SKETCH_MIGRATIONS, migrate_sketch
from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION


def test_registry_is_empty_for_the_first_sketch_schema():
    assert PER_ITEM_SKETCH_MIGRATIONS == {}


def test_current_version_sketch_passes_through_unchanged():
    raw = {"id": "s", "layers": []}

    assert migrate_sketch(raw, schema_version=CURRENT_SCHEMA_VERSION) == {"id": "s", "layers": []}


def test_applies_registered_migrations_in_order_from_the_saved_version():
    calls = []

    def step(version):
        def migrate(raw):
            calls.append(version)
            return {**raw, f"v{version}": True}
        return migrate

    with patch(
        "pandaplot.models.migrations.per_item.sketch.PER_ITEM_SKETCH_MIGRATIONS", {5: step(5), 6: step(6)},
    ), patch("pandaplot.models.migrations.per_item.sketch.CURRENT_SCHEMA_VERSION", 7):
        result = migrate_sketch({"id": "s"}, schema_version=5)

    assert calls == [5, 6]
    assert result == {"id": "s", "v5": True, "v6": True}
