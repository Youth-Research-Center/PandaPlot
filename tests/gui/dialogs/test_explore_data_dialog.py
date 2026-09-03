"""Tests for ExploreDataDialog: which branch it builds (dataset list vs.
import/create actions) and what each interaction does.
"""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from pandaplot.gui.dialogs.explore_data_dialog import ExploreDataDialog
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.folder import Folder


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_dialog(app_context, on_import_data=None, on_create_dataset=None):
    return ExploreDataDialog(
        app_context,
        on_import_data=on_import_data or Mock(),
        on_create_dataset=on_create_dataset or Mock(),
        parent=None,
    )


def _dataset(name="Sales", rows=3, cols=2):
    data = pd.DataFrame({f"c{i}": range(rows) for i in range(cols)})
    return Dataset(id=f"ds-{name}", name=name, data=data)


def test_get_datasets_empty_when_no_project_open():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False

    dialog = _make_dialog(app_context)

    assert dialog._get_datasets() == []


def test_get_datasets_empty_when_project_has_no_datasets():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = []
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert dialog._get_datasets() == []


def test_get_datasets_filters_to_dataset_items_only():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    ds1, ds2 = _dataset("A"), _dataset("B")
    non_dataset_item = Mock()
    project = Mock()
    project.get_all_items.return_value = [ds1, non_dataset_item, ds2]
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert dialog._get_datasets() == [ds1, ds2]


def test_dialog_builds_empty_state_actions_when_no_datasets():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False

    dialog = _make_dialog(app_context)

    assert hasattr(dialog, "import_btn")
    assert hasattr(dialog, "create_btn")


def test_dialog_shows_an_intro_explanation_regardless_of_branch():
    empty_context = Mock()
    empty_context.get_app_state.return_value.has_project = False
    empty_dialog = _make_dialog(empty_context)
    assert empty_dialog.intro_label.text().strip()

    populated_context = Mock()
    populated_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = [_dataset("A")]
    populated_context.get_app_state.return_value.current_project = project
    populated_dialog = _make_dialog(populated_context)
    assert populated_dialog.intro_label.text().strip()


def test_dialog_builds_dataset_list_when_datasets_exist():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    project = Mock()
    project.get_all_items.return_value = [_dataset("A")]
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    assert not hasattr(dialog, "import_btn")
    assert not hasattr(dialog, "create_btn")


def test_dataset_list_disambiguates_duplicate_dataset_names():
    # Uses a real Project (not a Mock) so dataset_display_options' folder-path
    # lookup (project.get_folder_path) has something real to resolve.
    project = Project(name="Test Project")
    runs = Folder(name="Runs")
    project.add_item(runs)

    # Built directly (not via the shared _dataset() helper, which derives a
    # fixed id from the name) so the two same-named datasets get distinct ids.
    root_dataset = Dataset(name="Sensor A", data=pd.DataFrame({"c0": [1, 2, 3]}))
    nested_dataset = Dataset(name="Sensor A", data=pd.DataFrame({"c0": [1, 2, 3]}))
    project.add_item(root_dataset)
    project.add_item(nested_dataset, runs.id)

    app_context = Mock()
    app_context.get_app_state.return_value.has_project = True
    app_context.get_app_state.return_value.current_project = project

    dialog = _make_dialog(app_context)

    buttons = dialog.findChildren(QPushButton, "DatasetItemButton")
    names = {button.accessibleName() for button in buttons}
    assert names == {"Sensor A  (project root)", "Sensor A  (Runs)"}
    assert len(buttons) == 2


def test_open_dataset_emits_tab_open_requested_and_accepts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    dialog = _make_dialog(app_context)
    dataset = _dataset("Sales")

    dialog._open_dataset(dataset)

    from pandaplot.models.events.event_types import UIEvents
    event_bus = app_context.get_app_state.return_value.event_bus
    event_bus.emit.assert_called_once_with(
        UIEvents.TAB_OPEN_REQUESTED, {"item_id": "ds-Sales", "item_name": "Sales"}
    )
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_handle_import_data_invokes_callback_and_accepts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    on_import_data = Mock()
    dialog = _make_dialog(app_context, on_import_data=on_import_data)

    dialog._handle_import_data()

    on_import_data.assert_called_once()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_handle_create_dataset_invokes_callback_and_accepts():
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = False
    on_create_dataset = Mock()
    dialog = _make_dialog(app_context, on_create_dataset=on_create_dataset)

    dialog._handle_create_dataset()

    on_create_dataset.assert_called_once()
    assert dialog.result() == QDialog.DialogCode.Accepted
