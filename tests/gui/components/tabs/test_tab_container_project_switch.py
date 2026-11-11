"""Loading or creating another project closes the previous project's tabs and floating windows."""

from pathlib import Path

import pandas as pd
import pytest

from pandaplot.app import build_app_context
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
from pandaplot.commands.project.project.new_project_command import NewProjectCommand
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.models.events import UIEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Note
from pandaplot.services.data_managers.project_manager import ProjectManager
from tests.commands.project.conftest import SyncTaskScheduler


def _project(name: str, prefix: str) -> Project:
    project = Project(name=name)
    project.add_item(Note(id=f"{prefix}-note", name=f"{prefix} note"))
    project.add_item(Dataset(id=f"{prefix}-data", name=f"{prefix} data", data=pd.DataFrame({"x": [1, 2, 3], "y": [2, 4, 6]})))
    project.add_item(Chart(id=f"{prefix}-chart", name=f"{prefix} chart"))
    return project


@pytest.fixture
def context(monkeypatch):
    app_context = build_app_context()
    ui = app_context.get_ui_controller()
    monkeypatch.setattr(ui, "show_info_message", lambda *_a, **_k: None)
    monkeypatch.setattr(ui, "show_new_project_dialog", lambda *_a, **_k: "B")
    return app_context


def _make_container(qtbot, context, monkeypatch) -> TabContainer:
    monkeypatch.setattr(TabContainer, "_persist_tab_session", lambda _self: None)
    container = TabContainer(context, parent=None)
    qtbot.addWidget(container)
    return container


def _welcome_count(container: TabContainer) -> int:
    return sum(isinstance(pane.widget(i), WelcomeTab) for pane in container.panes for i in range(pane.count()))


def _record_tab_changes(context) -> list[dict]:
    payloads: list[dict] = []
    context.get_event_bus().subscribe(UIEvents.TAB_CHANGED, payloads.append)
    return payloads


def test_loading_another_project_closes_the_previous_projects_tabs(qtbot, context, monkeypatch):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")
    container.open_tab("a-data")
    old_widgets = list(container.tabs.values())
    assert set(container.tabs) == {"a-note", "a-data"}

    state.load_project(_project("B", "b"))

    assert container.tabs == {}
    for widget in old_widgets:
        assert container._pane_of(widget) is None
    assert _welcome_count(container) == 1


def test_save_as_style_reload_of_the_same_project_keeps_tabs(qtbot, context, monkeypatch):
    state = context.get_app_state()
    project = _project("A", "a")
    state.load_project(project)
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")
    widget = container.tabs["a-note"]

    state.load_project(project)

    assert container.tabs == {"a-note": widget}
    assert container._pane_of(widget) is not None


def test_first_load_closes_nothing_and_keeps_a_single_welcome_tab(qtbot, context, monkeypatch):
    container = _make_container(qtbot, context, monkeypatch)
    assert _welcome_count(container) == 1

    context.get_app_state().load_project(_project("A", "a"))

    assert container.tabs == {}
    assert _welcome_count(container) == 1


def test_switch_from_a_project_loaded_before_the_container_shows_one_welcome_tab(qtbot, context, monkeypatch):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")
    assert _welcome_count(container) == 0

    state.load_project(_project("B", "b"))

    assert _welcome_count(container) == 1


def test_switch_does_not_duplicate_an_existing_welcome_tab(qtbot, context, monkeypatch):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.show_welcome_tab()
    container.open_tab("a-note")
    assert _welcome_count(container) == 1

    state.load_project(_project("B", "b"))

    assert container.tabs == {}
    assert _welcome_count(container) == 1


def test_switch_closes_tabs_in_both_panes_and_collapses_the_second_pane(qtbot, context, monkeypatch):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")
    container.open_tab("a-data")
    container._handle_split(container.panes[0], container.panes[0].indexOf(container.tabs["a-data"]))
    assert len(container.panes) == 2

    state.load_project(_project("B", "b"))

    assert container.tabs == {}
    assert len(container.panes) == 1
    assert _welcome_count(container) == 1


def test_switch_closes_floating_windows(qtbot, context, monkeypatch):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-chart")
    container.popout_tab(container.panes[0], container.panes[0].indexOf(container.tabs["a-chart"]))
    assert "a-chart" in container.floating_windows

    state.load_project(_project("B", "b"))

    assert container.floating_windows == {}
    assert container.tabs == {}


@pytest.mark.parametrize("how", ["close", "switch"])
def test_sidebar_context_moves_to_welcome_when_the_active_floating_chart_closes(qtbot, context, monkeypatch, how):
    state = context.get_app_state()
    state.load_project(_project("A", "a"))
    container = _make_container(qtbot, context, monkeypatch)
    container.show_welcome_tab()
    container.open_tab("a-chart")
    container.popout_tab(container.panes[0], container.panes[0].indexOf(container.tabs["a-chart"]))
    container._on_floating_tab_activated("a-chart")
    payloads = _record_tab_changes(context)

    if how == "close":
        container.on_project_closed()
    else:
        state.load_project(_project("B", "b"))

    assert payloads
    assert payloads[-1]["tab_type"] == "other"
    assert payloads[-1]["tab_title"] == "Welcome"


def test_new_project_command_closes_tabs_on_execute_undo_and_redo(qtbot, context, monkeypatch):
    state = context.get_app_state()
    project_a = _project("A", "a")
    state.load_project(project_a)
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")

    command = NewProjectCommand(context)
    assert command.execute() is CommandResult.SUCCESS
    assert container.tabs == {}
    assert state.current_project is not project_a

    new_project = state.current_project
    new_project.add_item(Note(id="n-note", name="new note"))
    container.open_tab("n-note")
    assert set(container.tabs) == {"n-note"}

    assert command.undo() is CommandResult.SUCCESS
    assert state.current_project is project_a
    assert container.tabs == {}

    container.open_tab("a-note")
    assert command.redo() is CommandResult.SUCCESS
    assert state.current_project is new_project
    assert container.tabs == {}


def test_load_project_command_closes_tabs_on_execute_undo_and_redo(qtbot, context, monkeypatch, tmp_path: Path):
    state = context.get_app_state()
    path = tmp_path / "b.pplot"
    assert context.get_manager(ProjectManager).save_project(_project("B", "b"), str(path))
    project_a = _project("A", "a")
    state.load_project(project_a)
    container = _make_container(qtbot, context, monkeypatch)
    container.open_tab("a-note")

    command = LoadProjectCommand(context, str(path))
    command.task_scheduler = SyncTaskScheduler()
    assert command.execute() is CommandResult.SUCCESS
    assert state.current_project is not project_a
    assert container.tabs == {}

    loaded = state.current_project
    container.open_tab("b-note")
    assert set(container.tabs) == {"b-note"}

    assert command.undo() is CommandResult.SUCCESS
    assert state.current_project is project_a
    assert container.tabs == {}

    container.open_tab("a-note")
    assert command.redo() is CommandResult.SUCCESS
    assert state.current_project is loaded
    assert container.tabs == {}
