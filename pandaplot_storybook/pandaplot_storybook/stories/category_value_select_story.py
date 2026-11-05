from __future__ import annotations

from pandaplot.gui.components.common.category_value_select import CategoryValueSelect
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_CATEGORIES, CHART_TYPE_SPECS
from PySide6.QtWidgets import QFormLayout, QWidget

from pandaplot_storybook.registry import ChoiceControl, StoryDef, story

# The chart tab's Type selector: chart types under their category.
_GROUPS = [
    (category.value, [(CHART_TYPE_SPECS[chart_type].display_name, chart_type.value) for chart_type in chart_types])
    for category, chart_types in CHART_TYPE_CATEGORIES.items()
]
_VALUES = [value for _category, items in _GROUPS for _label, value in items]


@story("CategoryValueSelect")
def _build() -> StoryDef:
    def make_widget(values: dict, tokens: dict) -> QWidget:
        widget = QWidget()
        select = CategoryValueSelect(_GROUPS, parent=widget)
        select.setCurrentValue(values["selected"])
        form = QFormLayout(widget)
        form.addRow("Category:", select.category_combo)
        form.addRow("Type:", select.value_combo)
        return widget

    return StoryDef(controls=[ChoiceControl("selected", _VALUES[0], _VALUES)], make_widget=make_widget)
