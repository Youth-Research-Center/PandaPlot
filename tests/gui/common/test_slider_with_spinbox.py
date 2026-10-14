import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.slider_with_spinbox import (
    SliderWithSpinbox,
    slider_to_value,
    value_to_slider,
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_slider_to_value_at_zero_is_minimum():
    assert slider_to_value(0, minimum=0.0, maximum=10.0, steps=100) == pytest.approx(0.0)


def test_slider_to_value_at_max_step_is_maximum():
    assert slider_to_value(100, minimum=0.0, maximum=10.0, steps=100) == pytest.approx(10.0)


def test_slider_to_value_at_midpoint():
    assert slider_to_value(50, minimum=0.0, maximum=10.0, steps=100) == pytest.approx(5.0)


def test_value_to_slider_round_trips_with_slider_to_value():
    pos = value_to_slider(7.5, minimum=0.0, maximum=10.0, steps=100)
    assert slider_to_value(pos, minimum=0.0, maximum=10.0, steps=100) == pytest.approx(7.5)


def test_value_to_slider_clamps_below_minimum():
    assert value_to_slider(-5.0, minimum=0.0, maximum=10.0, steps=100) == 0


def test_value_to_slider_clamps_above_maximum():
    assert value_to_slider(50.0, minimum=0.0, maximum=10.0, steps=100) == 100


def test_widget_set_value_updates_spinbox_and_slider_in_sync():
    widget = SliderWithSpinbox(minimum=0.0, maximum=10.0)
    widget.setValue(4.0)
    assert widget.value() == pytest.approx(4.0)
    assert widget._spinbox.value() == pytest.approx(4.0)


def test_moving_slider_emits_value_changed():
    widget = SliderWithSpinbox(minimum=0.0, maximum=10.0)
    seen = []
    widget.valueChanged.connect(seen.append)
    widget._slider.setValue(widget._slider.maximum())
    assert seen and seen[-1] == pytest.approx(10.0)


def test_numeric_field_beside_the_slider_has_no_step_buttons():
    """The slider already moves the value; -/+ buttons would crowd the row."""
    widget = SliderWithSpinbox(minimum=0.0, maximum=10.0)
    widget.show()
    try:
        assert not widget._spinbox._increase.isVisible()
        assert not widget._spinbox._decrease.isVisible()
    finally:
        widget.close()


def test_typing_in_the_numeric_field_moves_the_slider():
    widget = SliderWithSpinbox(minimum=0.0, maximum=10.0)
    seen = []
    widget.valueChanged.connect(seen.append)

    widget._spinbox._edit.selectAll()
    QTest.keyClicks(widget._spinbox._edit, "5")

    assert widget._slider.value() == 50
    assert seen and seen[-1] == pytest.approx(5.0)
