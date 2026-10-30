"""Event wiring of the statistics side panels: results are announced once, and
column pickers follow column renames."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.gui.components.sidebar.statistics.descriptive_panel import DescriptiveStatsPanel
from pandaplot.gui.components.sidebar.statistics.statistics_panel import StatisticsPanel
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_data import DatasetColumnRenamedData
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset


@pytest.fixture
def context():
    project = Project(name="Stats events")
    rng = np.random.default_rng(0)
    dataset = Dataset(name="data", data=pd.DataFrame({"a": rng.normal(size=20), "b": rng.normal(1.0, size=20)}))
    project.add_item(dataset)
    bus = EventBus()
    app_state = SimpleNamespace(has_project=True, current_project=project, event_bus=bus)
    ctx = Mock()
    ctx.event_bus = bus
    ctx.app_state = app_state
    ctx.get_app_state.return_value = app_state
    ctx.get_manager.return_value.get_surface_palette.return_value = {}
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9}

    def execute(command):
        return command.execute().value == "success"

    ctx.get_command_executor.return_value.execute_command.side_effect = execute
    return SimpleNamespace(ctx=ctx, bus=bus, project=project, dataset=dataset)


def _open(panel_cls, context, qtbot):
    panel = panel_cls(context.ctx)
    qtbot.addWidget(panel)
    panel.on_tab_changed({"tab_type": "dataset", "tab_id": context.dataset.id})
    return panel


def _record_created(bus):
    created = []
    bus.subscribe(DatasetEvents.DATASET_CREATED, created.append)
    return created


def test_descriptive_panel_announces_result_dataset_once(qtbot, context):
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    created = _record_created(context.bus)
    panel.add_results_to_project()
    assert len(created) == 1
    assert context.project.find_item(created[0]["dataset_id"]) is not None


def test_statistics_panel_announces_result_dataset_once(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    columns = panel._selected_columns()
    assert columns and columns[0] == "a"
    if len(panel.column_combos) > 1:
        panel.column_combos[1].setCurrentText("b")
    created = _record_created(context.bus)
    panel.add_results_to_project()
    assert len(created) == 1
    assert context.project.find_item(created[0]["dataset_id"]) is not None


def _rename_column(context, old, new):
    context.dataset.data.rename(columns={old: new}, inplace=True)
    context.bus.emit(
        DatasetOperationEvents.DATASET_COLUMN_RENAMED,
        DatasetColumnRenamedData(dataset_id=context.dataset.id, column_index=0, old_name=old, new_name=new).to_dict(),
    )


def test_descriptive_panel_column_list_follows_rename(qtbot, context):
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    _rename_column(context, "a", "alpha")
    assert [panel.column_list.item(i).text() for i in range(panel.column_list.count())] == ["alpha", "b"]


def test_statistics_panel_column_combos_follow_rename(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    _rename_column(context, "a", "alpha")
    combo = panel.column_combos[0]
    assert [combo.itemText(i) for i in range(combo.count())] == ["alpha", "b"]
