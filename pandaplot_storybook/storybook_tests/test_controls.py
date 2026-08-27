from PySide6.QtWidgets import QComboBox, QLabel

from pandaplot_storybook.controls import NO_CONTROLS_MESSAGE, ControlsPanel
from pandaplot_storybook.registry import BoolControl, ChoiceControl, TextControl


def test_values_reflect_defaults(qtbot):
    panel = ControlsPanel([TextControl("text", "hi"), BoolControl("enabled", default=True)])
    qtbot.addWidget(panel)
    assert panel.values() == {"text": "hi", "enabled": True}


def test_changing_an_editor_updates_values_and_emits(qtbot):
    panel = ControlsPanel([ChoiceControl("role", "secondary", ["primary", "secondary"])])
    qtbot.addWidget(panel)
    combo = panel.findChild(QComboBox)
    assert combo is not None

    with qtbot.waitSignal(panel.valuesChanged, timeout=1000) as blocker:
        combo.setCurrentText("primary")

    assert blocker.args[0] == {"role": "primary"}
    assert panel.values() == {"role": "primary"}


def test_no_controls_shows_empty_state_label(qtbot):
    panel = ControlsPanel([])
    qtbot.addWidget(panel)
    label = panel.findChild(QLabel, "controlsEmptyState")
    assert label is not None
    assert label.text() == NO_CONTROLS_MESSAGE
    assert panel.values() == {}
