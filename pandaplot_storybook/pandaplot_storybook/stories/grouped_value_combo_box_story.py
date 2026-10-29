from __future__ import annotations

from pandaplot.gui.components.common.grouped_value_combo_box import GroupedValueComboBox
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_CATEGORIES, CHART_TYPE_SPECS
from PySide6.QtWidgets import QWidget

from pandaplot_storybook.registry import ChoiceControl, StoryDef, story

# The chart tab's Type combo: chart types under their category headers.
_GROUPS = [
    (category.value, [(CHART_TYPE_SPECS[chart_type].display_name, chart_type.value) for chart_type in chart_types])
    for category, chart_types in CHART_TYPE_CATEGORIES.items()
]
_VALUES = [value for _header, items in _GROUPS for _label, value in items]


@story("GroupedValueComboBox")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        widget = GroupedValueComboBox(_GROUPS)
        widget.setCurrentValue(values["selected"])
        return widget

    return StoryDef(controls=[ChoiceControl("selected", _VALUES[0], _VALUES)], make_widget=make_widget)
