"""Tests for chart_display_options -- the same folder-path disambiguation
dataset_display_options uses (see test_dataset_display_options.py),
via the shared disambiguated_display_options. Charts need this because the
dataset-less wizard defaults every chart it creates to "New Chart", so a
project can easily end up with several same-named charts.
"""

from pandaplot.models.project import Project
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.folder import Folder
from pandaplot.utils.item_display_options import chart_display_options


def test_unique_names_are_left_plain():
    project = Project(name="Test Project")
    a = Chart(name="Sales Trend")
    b = Chart(name="Cost Breakdown")
    project.add_item(a)
    project.add_item(b)

    options = dict(chart_display_options(project))

    assert options[a.id] == "Sales Trend"
    assert options[b.id] == "Cost Breakdown"


def test_duplicate_names_are_suffixed_with_folder_path():
    project = Project(name="Test Project")
    runs = Folder(name="Runs")
    project.add_item(runs)

    root_chart = Chart(name="New Chart")
    nested_chart = Chart(name="New Chart")
    project.add_item(root_chart)
    project.add_item(nested_chart, runs.id)

    options = dict(chart_display_options(project))

    assert options[root_chart.id] == "New Chart  (project root)"
    assert options[nested_chart.id] == "New Chart  (Runs)"


def test_options_preserve_get_all_items_order():
    project = Project(name="Test Project")
    a = Chart(name="Sales Trend")
    b = Chart(name="Cost Breakdown")
    project.add_item(a)
    project.add_item(b)

    ids = [item_id for item_id, _ in chart_display_options(project)]

    assert ids == [a.id, b.id]


def test_non_chart_items_are_excluded():
    project = Project(name="Test Project")
    folder = Folder(name="Runs")
    chart = Chart(name="Sales Trend")
    project.add_item(folder)
    project.add_item(chart, folder.id)

    options = chart_display_options(project)

    assert [item_id for item_id, _ in options] == [chart.id]
