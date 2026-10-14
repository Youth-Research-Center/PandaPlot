from __future__ import annotations

from pandaplot.gui.components.common.number_input import IntegerInput
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, IntControl, StoryDef, story


@story("IntegerInput")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        widget = IntegerInput(steppers=values["steppers"])
        widget.setRange(0, 100)
        widget.setSuffix(" px")
        widget.setValue(values["value"])
        return widget

    return StoryDef(
        controls=[IntControl("value", 12, 0, 100), BoolControl("steppers", default=True)],
        make_widget=make_widget,
    )
