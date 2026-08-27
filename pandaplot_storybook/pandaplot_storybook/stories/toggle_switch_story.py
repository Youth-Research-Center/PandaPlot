from __future__ import annotations

from pandaplot.gui.components.common.toggle_switch import ToggleSwitch
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, StoryDef, story


@story("ToggleSwitch")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        return ToggleSwitch(checked=values["checked"])

    return StoryDef(controls=[BoolControl("checked", default=False)], make_widget=make_widget)
