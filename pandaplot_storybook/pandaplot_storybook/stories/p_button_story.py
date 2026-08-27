from __future__ import annotations

from pandaplot.gui.components.common.p_button import PButton
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, ChoiceControl, StoryDef, TextControl, story

_ROLES = ["primary", "secondary", "destructive"]


@story("PButton")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        return PButton(values["text"], role=values["role"], enabled=values["enabled"])

    return StoryDef(
        controls=[
            TextControl("text", "Click me"),
            ChoiceControl("role", "secondary", _ROLES),
            BoolControl("enabled", default=True),
        ],
        make_widget=make_widget,
    )
