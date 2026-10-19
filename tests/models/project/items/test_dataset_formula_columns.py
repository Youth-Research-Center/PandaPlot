"""Tests for Dataset's formula-column registry (#154).

A formula column's expression is part of the dataset, not just a side effect of
one transform run, so it must round-trip and must stay keyed by stable column id
(so renaming a source column doesn't detach the formula).
"""

import pandas as pd

from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec


def _dataset() -> Dataset:
    return Dataset(id="ds", name="Data", data=pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}))


class TestRegistry:
    def test_columns_are_plain_by_default(self):
        dataset = _dataset()
        assert dataset.formula_columns == {}
        assert dataset.formula_column_by_name("a") is None

    def test_set_and_look_up_by_name(self):
        dataset = _dataset()
        b_id = dataset.column_id("b")
        dataset.set_formula_column(b_id, FormulaColumnSpec(expression="x * 2", source_column_ids=[dataset.column_id("a")]))

        spec = dataset.formula_column_by_name("b")
        assert spec is not None
        assert spec.expression == "x * 2"
        assert spec.live is False

    def test_a_renamed_source_column_keeps_the_formula_attached(self):
        dataset = _dataset()
        a_id = dataset.column_id("a")
        dataset.set_formula_column(
            dataset.column_id("b"), FormulaColumnSpec(expression="x * 2", source_column_ids=[a_id]),
        )

        dataset.rename_column("a", "alpha")
        dataset.data = dataset.data.rename(columns={"a": "alpha"})

        spec = dataset.formula_column_by_name("b")
        assert spec.source_column_ids == [a_id]
        assert dataset.column_name(a_id) == "alpha"

    def test_remove_turns_the_column_back_into_a_plain_one(self):
        dataset = _dataset()
        b_id = dataset.column_id("b")
        dataset.set_formula_column(b_id, FormulaColumnSpec(expression="x"))

        assert dataset.remove_formula_column(b_id) is not None
        assert dataset.formula_column(b_id) is None

    def test_dropping_a_column_drops_its_formula(self):
        dataset = _dataset()
        b_id = dataset.column_id("b")
        dataset.set_formula_column(b_id, FormulaColumnSpec(expression="x"))

        dataset.set_data(dataset.data.drop(columns=["b"]))

        assert dataset.formula_columns == {}


class TestLiveFormulaColumns:
    """Live formula columns are derived data: they are the ones that can't be edited by hand."""

    def test_a_live_formula_column_is_reported_as_live(self):
        dataset = _dataset()
        dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(expression="x", live=True))

        assert dataset.is_live_formula_column("b") is True

    def test_a_static_formula_column_is_not_live(self):
        dataset = _dataset()
        dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(expression="x", live=False))

        assert dataset.is_live_formula_column("b") is False

    def test_a_plain_or_unknown_column_is_not_live(self):
        dataset = _dataset()

        assert dataset.is_live_formula_column("a") is False
        assert dataset.is_live_formula_column("no such column") is False


class TestReassignColumnId:
    def test_rekeys_the_column_in_place_keeping_order_and_name(self):
        dataset = _dataset()
        original_order = list(dataset.column_ids.values())

        dataset.reassign_column_id("a", "stable-a")

        assert dataset.column_id("a") == "stable-a"
        assert dataset.column_name("stable-a") == "a"
        assert list(dataset.column_ids.values()) == original_order
        assert next(iter(dataset.column_ids)) == "stable-a"

    def test_an_unknown_name_is_ignored(self):
        dataset = _dataset()
        before = dict(dataset.column_ids)

        dataset.reassign_column_id("nope", "stable")

        assert dict(dataset.column_ids) == before


class TestSerialization:
    def test_to_dict_from_dict_round_trip(self):
        dataset = _dataset()
        a_id = dataset.column_id("a")
        b_id = dataset.column_id("b")
        dataset.set_formula_column(b_id, FormulaColumnSpec(
            expression="x * 2", transform_type="column", source_column_ids=[a_id],
            source_aliases=["a"], live=True,
        ))

        restored = Dataset.from_dict(dataset.to_dict())

        spec = restored.formula_column(b_id)
        assert spec is not None
        assert spec.expression == "x * 2"
        assert spec.transform_type == "column"
        assert spec.source_column_ids == [a_id]
        assert spec.source_aliases == ["a"]
        assert spec.live is True

    def test_a_spec_saved_before_aliases_existed_loads_with_none(self):
        spec = FormulaColumnSpec.from_dict({"expression": "x", "source_column_ids": ["id-a"]})

        assert spec.source_aliases == []

    def test_from_dict_tolerates_a_legacy_project_without_the_field(self):
        dataset = _dataset()
        data = dataset.to_dict()
        del data["formula_columns"]

        restored = Dataset.from_dict(data)

        assert restored.formula_columns == {}

    def test_specs_for_columns_that_no_longer_exist_are_dropped_on_load(self):
        dataset = _dataset()
        data = dataset.to_dict()
        data["formula_columns"] = {"ghost-id": {"expression": "x", "source_column_ids": []}}

        restored = Dataset.from_dict(data)

        assert restored.formula_columns == {}
