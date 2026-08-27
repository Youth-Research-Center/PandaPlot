from __future__ import annotations

from pandaplot.gui.components.common.dirty_footer import DirtyFooter
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import BoolControl, IntControl, StoryDef, story


@story("DirtyFooter")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        widget = DirtyFooter()
        widget.setModified(is_modified=values["modified"], change_count=values["change_count"])
        return widget

    return StoryDef(
        controls=[
            BoolControl("modified", default=True),
            IntControl("change_count", default=3, minimum=0, maximum=20),
        ],
        make_widget=make_widget,
    )
