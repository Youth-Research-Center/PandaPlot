from __future__ import annotations

from pandaplot.gui.components.common.busy_spinner import BusySpinner
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, ChoiceControl, IntControl, StoryDef, story

_COLOR_PRESETS = ["#4A90E2", "#3FA46A", "#DC3545", "#E09A1F"]


@story("BusySpinner")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        spinner = BusySpinner(color=values["color"], diameter=values["diameter"])
        if values["running"]:
            spinner.start()
        else:
            # start()/stop() both control visibility; show() alone keeps a
            # stopped spinner visible (frozen mid-arc) so it's still
            # inspectable in the gallery instead of disappearing entirely.
            spinner.show()
        return spinner

    return StoryDef(
        controls=[
            BoolControl("running", default=True),
            ChoiceControl("color", "#4A90E2", _COLOR_PRESETS),
            IntControl("diameter", default=20, minimum=10, maximum=64),
        ],
        make_widget=make_widget,
    )
