"""Event wiring of the statistics side panels: results are announced once, and
column pickers follow column renames."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import StatTestType
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


def _add_columns(context, *names):
    rng = np.random.default_rng(1)
    for name in names:
        context.dataset.data[name] = rng.normal(size=len(context.dataset.data))


def _remove_column(context, name):
    context.dataset.data.drop(columns=[name], inplace=True)
    context.bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED, {"dataset_id": context.dataset.id, "column_name": name})


def _select_statistics_columns(panel, names):
    if panel.group_list is not None:
        panel.group_list.clearSelection()
        for i in range(panel.group_list.count()):
            panel.group_list.item(i).setSelected(panel.group_list.item(i).text() in names)
    else:
        for combo, name in zip(panel.column_combos, names, strict=False):
            combo.setCurrentText(name)


@pytest.mark.parametrize("test_type", [StatTestType.ONE_SAMPLE_T, StatTestType.INDEPENDENT_T, StatTestType.ONE_WAY_ANOVA])
def test_statistics_panel_keeps_selection_and_result_across_renames(qtbot, context, test_type):
    _add_columns(context, "c", "d")
    panel = _open(StatisticsPanel, context, qtbot)
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(test_type))
    chosen = ["c", "d"][: 1 if test_type == StatTestType.ONE_SAMPLE_T else 2]
    _select_statistics_columns(panel, chosen)
    panel.run_test()
    assert panel.last_result is not None

    _rename_column(context, "a", "alpha")
    assert sorted(panel._selected_columns()) == chosen
    assert panel.last_result is not None
    assert panel.add_btn.isEnabled() is True

    _rename_column(context, "c", "gamma")
    assert sorted(panel._selected_columns()) == sorted(["gamma", *chosen[1:]])


@pytest.mark.parametrize("test_type", [StatTestType.ONE_SAMPLE_T, StatTestType.INDEPENDENT_T, StatTestType.ONE_WAY_ANOVA])
def test_statistics_panel_invalidates_result_when_selected_column_is_removed(qtbot, context, test_type):
    _add_columns(context, "c", "d")
    panel = _open(StatisticsPanel, context, qtbot)
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(test_type))
    _select_statistics_columns(panel, ["c", "d"])
    panel.run_test()
    assert panel.add_btn.isEnabled() is True

    _remove_column(context, "c")

    assert "c" not in panel._selected_columns()
    assert panel.last_result is None
    assert panel.add_btn.isEnabled() is False
    assert panel.results_text.toPlainText() == ""


@pytest.mark.parametrize("selected", [["a", "b", "c", "d"], ["a"], ["a", "c"]])
def test_descriptive_panel_selection_follows_rename(qtbot, context, selected):
    _add_columns(context, "c", "d")
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    for i in range(panel.column_list.count()):
        panel.column_list.item(i).setSelected(panel.column_list.item(i).text() in selected)
    panel.compute()
    assert panel.add_btn.isEnabled() is True

    _rename_column(context, "a", "alpha")

    assert sorted(panel._selected_columns()) == sorted(["alpha", *selected[1:]])
    assert panel.last_result is not None
    assert panel.add_btn.isEnabled() is True


def test_descriptive_panel_invalidates_result_when_selected_column_is_removed(qtbot, context):
    _add_columns(context, "c", "d")
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    panel.compute()
    assert panel.add_btn.isEnabled() is True

    _remove_column(context, "c")

    assert sorted(panel._selected_columns()) == ["a", "b", "d"]
    assert panel.last_result is None
    assert panel.add_btn.isEnabled() is False


def test_statistics_panel_follows_rename_and_undo_of_int_labelled_column(qtbot, context):
    """Excel imports keep numeric headers as int labels; undoing a rename emits the int label again."""
    context.dataset.data[2020] = context.dataset.data["a"] * 2
    panel = _open(StatisticsPanel, context, qtbot)
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(StatTestType.ONE_SAMPLE_T))
    _select_statistics_columns(panel, ["2020"])
    assert panel._selected_columns() == ["2020"]

    _rename_column(context, 2020, "y2020")
    assert panel._selected_columns() == ["y2020"]

    _rename_column(context, "y2020", 2020)
    assert panel._selected_columns() == ["2020"]


def test_statistics_group_mode_falls_back_to_default_groups_when_all_kept_groups_are_gone(qtbot, context):
    _add_columns(context, "c", "d")
    panel = _open(StatisticsPanel, context, qtbot)
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(StatTestType.ONE_WAY_ANOVA))
    _select_statistics_columns(panel, ["c", "d"])
    panel.run_test()

    _remove_column(context, "c")
    _remove_column(context, "d")

    assert sorted(panel._selected_columns()) == ["a", "b"]
    assert panel.last_result is None
    assert panel.add_btn.isEnabled() is False


def test_descriptive_panel_clears_result_when_a_column_event_widens_an_empty_selection(qtbot, context):
    """With nothing selected the rebuild selects every column, which no longer matches the computed result."""
    _add_columns(context, "c", "d")
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    for i in range(panel.column_list.count()):
        panel.column_list.item(i).setSelected(panel.column_list.item(i).text() in ("a", "b"))
    panel.compute()
    panel.column_list.clearSelection()

    _add_columns(context, "e")
    context.bus.emit(DatasetOperationEvents.DATASET_COLUMN_ADDED, {"dataset_id": context.dataset.id, "column_name": "e"})

    assert sorted(panel._selected_columns()) == ["a", "b", "c", "d", "e"]
    assert panel.last_result is None
    assert panel.add_btn.isEnabled() is False
