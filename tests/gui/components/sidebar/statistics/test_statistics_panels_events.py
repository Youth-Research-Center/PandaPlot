"""Event wiring of the statistics side panels: results are announced once, and
column pickers follow column renames. Also their status messages and info icons."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import STAT_TESTS, StatTestType
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.status_message import StatusKind
from pandaplot.gui.components.sidebar.statistics.descriptive_panel import DescriptiveStatsPanel
from pandaplot.gui.components.sidebar.statistics.statistics_panel import StatisticsPanel
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.events import DatasetEvents, DatasetOperationEvents
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_data import DatasetColumnRenamedData
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset
from pandaplot.utils.errors import UserFacingError
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel


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
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **ICON_TOKENS}

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


def _fail_execution(context):
    context.ctx.get_command_executor.return_value.execute_command.side_effect = lambda command: False


def _status_icon(panel):
    return panel.status_message.findChild(IconLabel)


@pytest.mark.parametrize("panel_cls", [DescriptiveStatsPanel, StatisticsPanel])
class TestStatusMessageShared:
    def test_status_message_sits_directly_above_the_results_text(self, qtbot, context, panel_cls):
        panel = _open(panel_cls, context, qtbot)
        layout = panel.results_text.parentWidget().layout()

        assert layout.indexOf(panel.status_message) == layout.indexOf(panel.results_text) - 1
        assert panel.status_message.isHidden()

    def test_missing_dataset_is_an_error_status(self, qtbot, context, panel_cls):
        panel = panel_cls(context.ctx)
        qtbot.addWidget(panel)
        panel.results_text.setPlainText("stale")

        (panel.compute if panel_cls is DescriptiveStatsPanel else panel.run_test)()

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "No dataset selected."
        assert panel.results_text.toPlainText() == ""

    def test_failed_add_is_an_error_status(self, qtbot, context, panel_cls):
        panel = _open(panel_cls, context, qtbot)
        if panel_cls is DescriptiveStatsPanel:
            panel.column_list.item(0).setSelected(True)
        _fail_execution(context)

        panel.add_results_to_project()

        assert panel.status_message.kind() is StatusKind.ERROR
        assert panel.status_message.message() == "Failed to add results. Please check your selection."
        assert panel.results_text.toPlainText() == ""

    def test_added_results_are_a_success_status_and_the_report_stays_in_the_text_area(self, qtbot, context, panel_cls):
        panel = _open(panel_cls, context, qtbot)
        if panel_cls is DescriptiveStatsPanel:
            panel.column_list.item(0).setSelected(True)

        panel.add_results_to_project()

        name = panel.last_result.result_name()
        assert panel.status_message.kind() is StatusKind.SUCCESS
        assert panel.status_message.message() == f"Results added to project as dataset: '{name}'"
        report = panel.results_text.toPlainText()
        assert report.strip() != ""
        assert "Results added to project" not in report

    def test_clear_clears_the_status_message(self, qtbot, context, panel_cls):
        panel = _open(panel_cls, context, qtbot)
        panel.status_message.set_message(StatusKind.ERROR, "boom")

        panel.clear()

        assert panel.status_message.message() == ""
        assert panel.status_message.kind() is None

    def test_theme_change_retints_the_status_icon(self, qtbot, context, panel_cls):
        panel = _open(panel_cls, context, qtbot)
        panel.status_message.set_message(StatusKind.ERROR, "boom")
        context.ctx.get_manager.return_value.get_design_tokens.return_value["status_danger"] = "#00AA00"

        panel._apply_theme()

        assert_tinted(strongest_pixel(_status_icon(panel).pixmap()), "#00AA00")


def test_descriptive_panel_requires_a_column(qtbot, context):
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    panel.column_list.clearSelection()

    panel.compute()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Please select at least one column."


def test_descriptive_panel_computation_failure_shows_the_exception_as_plain_text(qtbot, context, monkeypatch):
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    panel.column_list.item(0).setSelected(True)
    monkeypatch.setattr(
        "pandaplot.gui.components.sidebar.statistics.descriptive_panel.DescriptiveStatsCommand.compute",
        Mock(side_effect=UserFacingError("<b>bad</b>")),
    )

    panel.compute()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Computation failed: <b>bad</b>"
    assert panel.add_btn.isEnabled() is False


def test_descriptive_panel_successful_compute_clears_an_earlier_status(qtbot, context):
    panel = _open(DescriptiveStatsPanel, context, qtbot)
    panel.column_list.clearSelection()
    panel.compute()
    assert panel.status_message.kind() is StatusKind.ERROR
    panel.column_list.item(0).setSelected(True)

    panel.compute()

    assert panel.status_message.message() == ""
    assert panel.results_text.toPlainText().strip() != ""


def test_statistics_panel_test_failure_shows_the_exception_as_an_error_status(qtbot, context, monkeypatch):
    panel = _open(StatisticsPanel, context, qtbot)
    monkeypatch.setattr(
        "pandaplot.gui.components.sidebar.statistics.statistics_panel.StatisticalTestCommand.run_test",
        Mock(side_effect=UserFacingError("<b>bad</b>")),
    )

    panel.run_test()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Test failed: <b>bad</b>"
    assert panel.add_btn.isEnabled() is False


def test_statistics_panel_requires_two_different_columns(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    panel.test_type_combo.setCurrentIndex(panel.test_type_combo.findData(StatTestType.INDEPENDENT_T))
    for combo in panel.column_combos:
        combo.setCurrentText("a")

    panel.run_test()

    assert panel.status_message.kind() is StatusKind.ERROR
    assert panel.status_message.message() == "Please select two different columns."


def test_statistics_panel_successful_run_clears_an_earlier_status(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    panel.status_message.set_message(StatusKind.ERROR, "old")

    panel.run_test()

    assert panel.status_message.message() == ""
    assert panel.results_text.toPlainText().strip() != ""


def test_statistics_info_button_shows_an_info_icon_and_no_text(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)

    assert panel.info_btn.text() == ""
    assert panel.info_btn.accessibleName() == "About this test"
    assert panel.info_btn.toolTip() == "Learn about this test: explanation, formula and an example"
    assert panel.info_btn.minimumWidth() == panel.info_btn.maximumWidth() == 32
    size = panel.info_btn.iconSize()
    expected = themed_icon(context.ctx, "info")
    assert panel.info_btn.icon().pixmap(size).toImage() == expected.pixmap(size).toImage()
    assert_tinted(strongest_pixel(panel.info_btn.icon()), ICON_TOKENS["text_primary"])


def test_statistics_info_button_icon_follows_the_theme(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    context.ctx.get_manager.return_value.get_design_tokens.return_value["text_primary"] = "#00AA00"

    panel._apply_theme()

    assert_tinted(strongest_pixel(panel.info_btn.icon()), "#00AA00")


def test_statistics_description_has_an_info_icon_and_plain_text(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    info = STAT_TESTS[panel._current_test_type()]

    assert panel.description_label.text() == info.description
    assert isinstance(panel.description_icon, IconLabel)
    assert panel.description_icon.icon_name == "info"
    assert_tinted(strongest_pixel(panel.description_icon.pixmap()), ICON_TOKENS["accent"])


def test_statistics_description_icon_follows_the_theme(qtbot, context):
    panel = _open(StatisticsPanel, context, qtbot)
    context.ctx.get_manager.return_value.get_design_tokens.return_value["accent"] = "#00AA00"

    panel._apply_theme()

    assert_tinted(strongest_pixel(panel.description_icon.pixmap()), "#00AA00")
