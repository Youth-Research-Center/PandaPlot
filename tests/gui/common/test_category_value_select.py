import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.category_value_select import CategoryValueSelect

_GROUPS = [
    ("Fruit", [("Apple", "apple"), ("Pear", "pear")]),
    ("Veg", [("Kale", "kale"), ("Leek", "leek"), ("Beet", "beet")]),
    ("Nuts", [("Pecan", "pecan")]),
]


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _labels(combo) -> list[str]:
    return [combo.itemText(i) for i in range(combo.count())]


def test_lists_categories_and_only_the_first_categorys_values():
    select = CategoryValueSelect(_GROUPS)

    assert _labels(select.category_combo) == ["Fruit", "Veg", "Nuts"]
    assert _labels(select.value_combo) == ["Apple", "Pear"]
    assert select.currentValue() == "apple"
    assert select.category_combo.accessibleName() == "Category"
    assert select.value_combo.accessibleName() == "Type"


def test_choosing_a_category_selects_its_first_value_and_emits_once():
    select = CategoryValueSelect(_GROUPS)
    emitted = []
    select.currentValueChanged.connect(emitted.append)

    select.category_combo.setCurrentIndex(1)

    assert _labels(select.value_combo) == ["Kale", "Leek", "Beet"]
    assert select.currentValue() == "kale"
    assert emitted == ["kale"]


def test_choosing_a_value_emits_it():
    select = CategoryValueSelect(_GROUPS)
    emitted = []
    select.currentValueChanged.connect(emitted.append)

    select.value_combo.setCurrentIndex(1)

    assert emitted == ["pear"]


def test_set_current_value_switches_category_without_emitting():
    select = CategoryValueSelect(_GROUPS)
    emitted = []
    select.currentValueChanged.connect(emitted.append)

    select.setCurrentValue("beet")

    assert select.category_combo.currentText() == "Veg"
    assert select.value_combo.currentText() == "Beet"
    assert select.currentValue() == "beet"
    assert emitted == []


def test_set_current_value_ignores_an_unknown_value():
    select = CategoryValueSelect(_GROUPS)

    select.setCurrentValue("granite")

    assert select.currentValue() == "apple"
    assert select.category_combo.currentText() == "Fruit"


def test_a_disabled_value_is_disabled_with_a_tooltip_and_can_be_re_enabled():
    select = CategoryValueSelect(_GROUPS)

    select.set_value_enabled("pear", enabled=False, tooltip="no pears")

    item = select.value_combo.model().item(1)
    assert item.isEnabled() is False
    assert item.toolTip() == "no pears"
    assert select.is_value_enabled("pear") is False
    assert select.value_tooltip("pear") == "no pears"

    select.set_value_enabled("pear", enabled=True)

    assert item.isEnabled() is True
    assert select.value_tooltip("pear") == ""


def test_disabled_state_survives_switching_category_back_and_forth():
    select = CategoryValueSelect(_GROUPS)
    select.set_value_enabled("leek", enabled=False, tooltip="no leeks")

    select.category_combo.setCurrentIndex(1)

    assert select.value_combo.model().item(1).isEnabled() is False
    select.category_combo.setCurrentIndex(0)
    select.category_combo.setCurrentIndex(1)
    assert select.value_combo.model().item(1).isEnabled() is False


def test_a_category_with_every_value_disabled_is_disabled_unless_current():
    select = CategoryValueSelect(_GROUPS)

    select.set_value_enabled("pecan", enabled=False, tooltip="no nuts")
    nuts = select.category_combo.model().item(2)

    assert nuts.isEnabled() is False
    assert nuts.toolTip() != ""
    # A category with one enabled value stays enabled.
    assert select.category_combo.model().item(1).isEnabled() is True

    select.setCurrentValue("pecan")
    assert nuts.isEnabled() is True


def test_choosing_a_category_skips_disabled_values():
    select = CategoryValueSelect(_GROUPS)
    select.set_value_enabled("kale", enabled=False, tooltip="no kale")
    emitted = []
    select.currentValueChanged.connect(emitted.append)

    select.category_combo.setCurrentIndex(1)

    assert select.currentValue() == "leek"
    assert emitted == ["leek"]


def test_requires_at_least_one_category():
    with pytest.raises(ValueError, match="at least one category"):
        CategoryValueSelect([])


def test_rejects_a_category_without_values():
    with pytest.raises(ValueError, match="Empty"):
        CategoryValueSelect([("Fruit", [("Apple", "apple")]), ("Empty", [])])
