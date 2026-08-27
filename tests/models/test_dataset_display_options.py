"""Tests for dataset_display_options -- the folder-path disambiguation used
by dataset-selection combo boxes when two datasets share a name (issue #114).
"""

from pandaplot.models.project import Project
from pandaplot.models.project.items.dataset import Dataset, dataset_display_options
from pandaplot.models.project.items.folder import Folder


def test_unique_names_are_left_plain():
    project = Project(name="Test Project")
    a = Dataset(name="Sensor A")
    b = Dataset(name="Sensor B")
    project.add_item(a)
    project.add_item(b)

    options = dict(dataset_display_options(project))

    assert options[a.id] == "Sensor A"
    assert options[b.id] == "Sensor B"


def test_duplicate_names_are_suffixed_with_folder_path():
    project = Project(name="Test Project")
    runs = Folder(name="Runs")
    trial2 = Folder(name="Trial 2")
    project.add_item(runs)
    project.add_item(trial2, runs.id)

    root_dataset = Dataset(name="Sensor A")
    nested_dataset = Dataset(name="Sensor A")
    project.add_item(root_dataset)
    project.add_item(nested_dataset, trial2.id)

    options = dict(dataset_display_options(project))

    assert options[root_dataset.id] == "Sensor A  (project root)"
    assert options[nested_dataset.id] == "Sensor A  (Runs / Trial 2)"


def test_options_preserve_get_all_items_order():
    project = Project(name="Test Project")
    a = Dataset(name="Sensor A")
    b = Dataset(name="Sensor B")
    project.add_item(a)
    project.add_item(b)

    ids = [item_id for item_id, _ in dataset_display_options(project)]

    assert ids == [a.id, b.id]


def test_non_dataset_items_are_excluded():
    project = Project(name="Test Project")
    folder = Folder(name="Runs")
    dataset = Dataset(name="Sensor A")
    project.add_item(folder)
    project.add_item(dataset, folder.id)

    options = dataset_display_options(project)

    assert [item_id for item_id, _ in options] == [dataset.id]
