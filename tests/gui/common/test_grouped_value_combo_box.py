import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.grouped_value_combo_box import GroupedValueComboBox


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


_GROUPS = [
    ("Lines", [("Line", "line"), ("Scatter", "scatter")]),
    ("Bars", [("Bar", "bar")]),
]


def test_headers_precede_their_items():
    combo = GroupedValueComboBox(_GROUPS)

    assert [combo.itemText(i) for i in range(combo.count())] == ["Lines", "Line", "Scatter", "Bars", "Bar"]
    assert [combo.is_header(i) for i in range(combo.count())] == [True, False, False, True, False]


def test_headers_are_disabled():
    combo = GroupedValueComboBox(_GROUPS)

    for index in (0, 3):
        assert not combo.model().item(index).isEnabled()
    for index in (1, 2, 4):
        assert combo.model().item(index).isEnabled()


def test_defaults_to_first_value_not_first_header():
    combo = GroupedValueComboBox(_GROUPS)

    assert combo.currentIndex() == 1
    assert combo.currentValue() == "line"


def test_set_current_value_and_selection_signal():
    combo = GroupedValueComboBox(_GROUPS)
    seen = []
    combo.currentValueChanged.connect(seen.append)

    combo.setCurrentValue("bar")
    assert combo.currentValue() == "bar"
    assert seen == []

    combo.setCurrentIndex(2)
    assert seen == ["scatter"]


def test_arrow_keys_skip_headers():
    combo = GroupedValueComboBox(_GROUPS)
    combo.setCurrentValue("scatter")
    combo.show()
    combo.setFocus()

    QTest.keyClick(combo, Qt.Key.Key_Down)
    assert combo.currentValue() == "bar"

    QTest.keyClick(combo, Qt.Key.Key_Up)
    QTest.keyClick(combo, Qt.Key.Key_Up)
    QTest.keyClick(combo, Qt.Key.Key_Up)
    assert combo.currentValue() == "line"


def test_empty_group_gets_no_header():
    combo = GroupedValueComboBox([("Empty", []), *_GROUPS])

    assert combo.itemText(0) == "Lines"
    assert combo.count() == 5
