from __future__ import annotations

from pandaplot.gui.components.common.number_input import DecimalInput
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, FloatControl, IntControl, StoryDef, story


@story("DecimalInput")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        widget = DecimalInput(steppers=values["steppers"])
        widget.setDecimals(values["decimals"])
        widget.setRange(-100.0, 100.0)
        widget.setSingleStep(0.5)
        widget.setSuffix(" pt")
        widget.setValue(values["value"])
        return widget

    return StoryDef(
        controls=[
            FloatControl("value", 12.5, -100.0, 100.0),
            IntControl("decimals", 2, 0, 6),
            BoolControl("steppers", default=True),
        ],
        make_widget=make_widget,
    )
