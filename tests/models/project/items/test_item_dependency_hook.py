from pandaplot.models.project.items.item import Item


class _DependentItem(Item):
    """Minimal fake item type overriding the dependency hook, used to
    test Item's generic on_items_removed/registration machinery without
    depending on any real item type's fields."""

    def __init__(self, id=None, name="", referenced_id=None):
        super().__init__(id, name)
        self.referenced_id = referenced_id
        self.strip_calls = []
        self.restore_calls = []

    def referenced_item_ids(self):
        if self.referenced_id is None:
            return None
        return {self.referenced_id}

    def _strip_references(self, removed_ids):
        self.strip_calls.append(set(removed_ids))
        snapshot = {"referenced_id": self.referenced_id}
        self.referenced_id = None
        return snapshot

    def restore_removed_items_snapshot(self, snapshot):
        self.restore_calls.append(snapshot)
        self.referenced_id = snapshot["referenced_id"]

    def dependency_update_event(self):
        return "test.dependent_updated", {"item_id": self.id}


class _NonDependentItem(Item):
    """A plain Item subclass that never overrides referenced_item_ids."""


class TestItemDependencyRegistration:
    def test_overriding_subclass_is_registered(self):
        assert _DependentItem in Item._dependency_aware_classes

    def test_non_overriding_subclass_is_not_registered(self):
        assert _NonDependentItem not in Item._dependency_aware_classes

    def test_base_item_is_not_registered(self):
        assert Item not in Item._dependency_aware_classes


class TestItemOnItemsRemoved:
    def test_returns_none_when_referenced_item_ids_is_none(self):
        item = _DependentItem(referenced_id=None)

        assert item.on_items_removed({"ds-1"}) is None
        assert item.strip_calls == []

    def test_returns_none_when_no_overlap(self):
        item = _DependentItem(referenced_id="ds-1")

        assert item.on_items_removed({"ds-2"}) is None
        assert item.strip_calls == []

    def test_strips_and_returns_snapshot_on_overlap(self):
        item = _DependentItem(referenced_id="ds-1")

        snapshot = item.on_items_removed({"ds-1", "ds-3"})

        assert snapshot == {"referenced_id": "ds-1"}
        assert item.strip_calls == [{"ds-1", "ds-3"}]
        assert item.referenced_id is None

    def test_restore_uses_the_returned_snapshot(self):
        item = _DependentItem(referenced_id="ds-1")
        snapshot = item.on_items_removed({"ds-1"})

        item.restore_removed_items_snapshot(snapshot)

        assert item.referenced_id == "ds-1"
        assert item.restore_calls == [snapshot]


class TestItemDefaultDependencyHook:
    def test_plain_item_referenced_item_ids_is_none(self):
        assert Item().referenced_item_ids() is None

    def test_plain_item_on_items_removed_is_none(self):
        assert Item().on_items_removed({"anything"}) is None

    def test_plain_item_dependency_update_event_is_none(self):
        assert Item().dependency_update_event() is None
