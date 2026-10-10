"""Tests for the shared formula engine (#154): expression evaluation and the
single topological sort used both to reject circular formulas at creation time
and to order a live recompute cascade."""

import pandas as pd
import pytest

from pandaplot.services.transform import formula_engine


class TestEvaluateFormula:
    def test_column_transform_uses_the_first_source_column(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        result = formula_engine.evaluate_formula(
            df, expression="x * 2", transform_type="column", source_columns=["a"],
        )
        assert list(result) == [2.0, 4.0, 6.0]

    def test_column_transform_exposes_cols_by_real_name(self):
        df = pd.DataFrame({"my col": [1.0, 2.0]})
        result = formula_engine.evaluate_formula(
            df, expression='cols["my col"] + 1', transform_type="column", source_columns=["my col"],
        )
        assert list(result) == [2.0, 3.0]

    def test_multi_column_transform_sees_all_sources(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [10.0, 20.0]})
        result = formula_engine.evaluate_formula(
            df, expression='cols["a"] + cols["b"]', transform_type="multi_column",
            source_columns=["a", "b"],
        )
        assert list(result) == [11.0, 22.0]

    def test_row_transform_sees_each_row(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [10.0, 20.0]})
        result = formula_engine.evaluate_formula(
            df, expression='row["a"] + row["b"]', transform_type="row", source_columns=["a", "b"],
        )
        assert list(result) == [11.0, 22.0]

    def test_scalar_result_is_broadcast_to_the_full_index(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        result = formula_engine.evaluate_formula(
            df, expression="5", transform_type="column", source_columns=["a"],
        )
        assert list(result) == [5, 5, 5]

    def test_missing_source_column_is_rejected(self):
        df = pd.DataFrame({"a": [1.0]})
        with pytest.raises(ValueError, match="Source columns not found"):
            formula_engine.evaluate_formula(
                df, expression="x", transform_type="column", source_columns=["nope"],
            )

    def test_unknown_transform_type_is_rejected(self):
        df = pd.DataFrame({"a": [1.0]})
        with pytest.raises(ValueError, match="Unknown transform type"):
            formula_engine.evaluate_formula(
                df, expression="x", transform_type="sideways", source_columns=["a"],
            )


class TestResolveRecomputeOrder:
    def test_multi_hop_chain_is_ordered_dependencies_first(self):
        # C reads B, B reads A; A is a plain column (not a node).
        order = formula_engine.resolve_recompute_order(
            ["b", "c"], {"b": ["a"], "c": ["b"]},
        )
        assert order.index("b") < order.index("c")

    def test_independent_nodes_are_all_returned(self):
        order = formula_engine.resolve_recompute_order(
            ["b", "c"], {"b": ["a"], "c": ["a"]},
        )
        assert set(order) == {"b", "c"}

    def test_dependencies_outside_the_node_set_are_treated_as_leaves(self):
        order = formula_engine.resolve_recompute_order(["b"], {"b": ["a", "z"]})
        assert order == ["b"]

    def test_two_node_cycle_raises(self):
        with pytest.raises(formula_engine.CircularFormulaDependencyError):
            formula_engine.resolve_recompute_order(["a", "b"], {"a": ["b"], "b": ["a"]})

    def test_self_reference_is_a_cycle(self):
        with pytest.raises(formula_engine.CircularFormulaDependencyError):
            formula_engine.resolve_recompute_order(["a"], {"a": ["a"]})

    def test_cycle_error_names_the_columns_involved(self):
        with pytest.raises(formula_engine.CircularFormulaDependencyError) as excinfo:
            formula_engine.resolve_recompute_order(
                ["a", "b", "c"], {"a": ["b"], "b": ["c"], "c": ["a"]},
            )
        assert set(excinfo.value.cycle) == {"a", "b", "c"}


class TestFindCircularDependency:
    def test_returns_none_for_a_valid_chain(self):
        assert formula_engine.find_circular_dependency({"b": ["a"], "c": ["b"]}) is None

    def test_returns_the_cycle_when_there_is_one(self):
        cycle = formula_engine.find_circular_dependency({"a": ["b"], "b": ["a"]})
        assert cycle is not None
        assert set(cycle) == {"a", "b"}
