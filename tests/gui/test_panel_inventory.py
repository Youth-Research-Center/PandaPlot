"""The panel inventory records what a panel contains, independent of widget classes, and diffs it against a golden."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from pytestqt.qtbot import QtBot

from pandaplot.gui.components.common.number_input import DecimalInput
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.gui.components.common.slider_with_spinbox import SliderWithSpinbox
from tests.gui.panel_inventory import assert_matches_golden, panel_inventory


def _build_panel(qtbot: QtBot) -> QWidget:
    panel = QWidget()
    qtbot.addWidget(panel)
    layout = QVBoxLayout(panel)
    group = QGroupBox("Method", panel)
    form = QFormLayout(group)
    combo = QComboBox(group)
    combo.addItems(["Savitzky-Golay", "Rolling mean"])
    combo.setCurrentIndex(1)
    form.addRow("Smoothing method", combo)
    window = QSpinBox(group)
    window.setRange(3, 101)
    window.setValue(11)
    window.setSuffix(" pts")
    form.addRow("Window", window)
    alpha = QDoubleSpinBox(group)
    alpha.setRange(0.001, 0.5)
    alpha.setDecimals(3)
    alpha.setValue(0.05)
    alpha.setAccessibleName("Significance")
    form.addRow(alpha)
    layout.addWidget(group)
    check = QCheckBox("Show residuals", panel)
    check.setChecked(True)
    layout.addWidget(check)
    name = QLineEdit(panel)
    name.setPlaceholderText("Result name")
    name.setText("smoothed")
    layout.addWidget(name)
    hidden = QLabel("Advanced options", panel)
    hidden.hide()
    layout.addWidget(hidden)
    columns = QListWidget(panel)
    columns.addItems(["time", "signal"])
    columns.setAccessibleName("Columns")
    layout.addWidget(columns)
    slider = QSlider(panel)
    slider.setRange(0, 10)
    slider.setValue(4)
    slider.setAccessibleName("Opacity")
    layout.addWidget(slider)
    apply_button = QPushButton("Apply", panel)
    apply_button.setEnabled(False)
    layout.addWidget(apply_button)
    return panel


def test_inventory_records_roles_labels_and_values_in_focus_order(qtbot: QtBot) -> None:
    panel = _build_panel(qtbot)

    assert panel_inventory(panel) == [
        'group | "Method" |',
        'combo | "Smoothing method" | value="Rolling mean" items=["Savitzky-Golay", "Rolling mean"]',
        'number | "Window" | value=11 range=3..101 decimals=0 suffix=" pts"',
        'number | "Significance" | value=0.05 range=0.001..0.5 decimals=3',
        'checkable | "Show residuals" | checked=true',
        'text | "" | value="smoothed" placeholder="Result name"',
        'label | "Advanced options" | hidden',
        'list | "Columns" | items=["time", "signal"]',
        'slider | "Opacity" | value=4 range=0..10',
        'button | "Apply" | disabled',
    ]


def test_inventory_treats_compound_inputs_as_one_control(qtbot: QtBot) -> None:
    panel = QWidget()
    qtbot.addWidget(panel)
    layout = QVBoxLayout(panel)
    number = DecimalInput(panel)
    number.setRange(0.0, 2.5)
    number.setDecimals(2)
    number.setValue(1.25)
    number.setAccessibleName("Line width")
    layout.addWidget(number)
    slider = SliderWithSpinbox(minimum=0.0, maximum=1.0, parent=panel)
    slider.setValue(0.5)
    slider.setAccessibleName("Alpha")
    layout.addWidget(slider)
    segments = SegmentedControl([("Linear", "linear"), ("Log", "log")], panel)
    segments.setCurrentValue("log")
    segments.setAccessibleName("Scale")
    layout.addWidget(segments)

    assert panel_inventory(panel) == [
        'number | "Line width" | value=1.25 range=0..2.5 decimals=2',
        'slider | "Alpha" | value=0.5 range=0..1 decimals=1',
        'choice | "Scale" | value="Log" items=["Linear", "Log"]',
    ]


def test_inventory_lists_tab_names_and_can_skip_pages(qtbot: QtBot) -> None:
    panel = QWidget()
    qtbot.addWidget(panel)
    layout = QVBoxLayout(panel)
    tabs = QTabWidget(panel)
    page = QWidget()
    QVBoxLayout(page).addWidget(QPushButton("Inside", page))
    tabs.addTab(page, "Data")
    tabs.addTab(QWidget(), "Style")
    layout.addWidget(tabs)

    assert panel_inventory(panel, exclude=[page]) == ['tabs | "" | value="Data" items=["Data", "Style"]']


def test_matching_ignores_label_case_only(tmp_path: Path) -> None:
    golden = tmp_path / "panel.txt"
    golden.write_text('label | "Window Length" |\ncombo | "" | value="Mean" items=["Mean"]\n', encoding="utf-8")

    assert_matches_golden(['label | "WINDOW LENGTH" |', 'combo | "" | value="Mean" items=["Mean"]'], golden)
    with pytest.raises(AssertionError):
        assert_matches_golden(['label | "Window length" |', 'combo | "" | value="mean" items=["mean"]'], golden)


def test_a_changed_label_fails_with_a_readable_diff(qtbot: QtBot, tmp_path: Path) -> None:
    panel = _build_panel(qtbot)
    golden = tmp_path / "panel.txt"
    golden.write_text("\n".join(panel_inventory(panel)) + "\n", encoding="utf-8")
    check = panel.findChild(QCheckBox)
    assert check is not None
    check.setText("Show fit residuals")

    with pytest.raises(AssertionError) as failure:
        assert_matches_golden(panel_inventory(panel), golden)

    message = str(failure.value)
    assert '-checkable | "Show residuals" | checked=true' in message
    assert '+checkable | "Show fit residuals" | checked=true' in message
    assert "PANDAPLOT_UPDATE_GOLDENS=1" in message


def test_missing_golden_fails_and_update_mode_writes_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    golden = tmp_path / "goldens" / "panel.txt"
    lines = ['button | "Apply" |']

    with pytest.raises(AssertionError, match="PANDAPLOT_UPDATE_GOLDENS=1"):
        assert_matches_golden(lines, golden)

    monkeypatch.setenv("PANDAPLOT_UPDATE_GOLDENS", "1")
    assert_matches_golden(lines, golden)
    assert golden.read_text(encoding="utf-8") == 'button | "Apply" |\n'
