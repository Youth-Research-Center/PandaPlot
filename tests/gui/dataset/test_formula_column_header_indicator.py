"""Tests for the data table's formula-column header indicator (#154).

The table has to say which columns are computed and which of those keep
themselves up to date -- otherwise a live column silently rewriting itself
looks like data corruption.
"""

import pandas as pd

from pandaplot.gui.components.tabs.dataset.pheader_view import formula_marker, formula_tooltip
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec


def _dataset() -> Dataset:
    return Dataset(id="ds", name="Data", data=pd.DataFrame({"a": [1.0], "b": [2.0], "c": [3.0]}))


def _with_formulas() -> Dataset:
    dataset = _dataset()
    a_id = dataset.column_id("a")
    dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(
        expression="x * 2", source_column_ids=[a_id], live=False,
    ))
    dataset.set_formula_column(dataset.column_id("c"), FormulaColumnSpec(
        expression="x * 3", source_column_ids=[a_id], live=True,
    ))
    return dataset


class TestFormulaMarker:
    def test_plain_column_has_no_marker(self):
        assert formula_marker(_with_formulas(), "a") == ""

    def test_static_formula_column_is_marked(self):
        assert formula_marker(_with_formulas(), "b") == "fx"

    def test_live_formula_column_is_marked_distinctly(self):
        assert formula_marker(_with_formulas(), "c") == "fx live"

    def test_no_dataset_is_tolerated(self):
        assert formula_marker(None, "a") == ""


class TestFormulaTooltip:
    def test_plain_column_has_no_tooltip(self):
        assert formula_tooltip(_with_formulas(), "a") is None

    def test_static_formula_tooltip_explains_it_is_not_automatic(self):
        tooltip = formula_tooltip(_with_formulas(), "b")
        assert "Formula column" in tooltip
        assert "x * 2" in tooltip

    def test_live_formula_tooltip_says_it_recomputes(self):
        tooltip = formula_tooltip(_with_formulas(), "c")
        assert "recomputes automatically" in tooltip
        assert "x * 3" in tooltip
