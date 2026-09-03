"""Disambiguated display labels for project items shown in name-only
selectors (dataset/chart combo boxes, pick-a-chart lists, ...).

Plain names disambiguate items almost everywhere, but two items of the same
type can share a name -- two datasets in different folders, or two
wizard-created charts both defaulted to "New Chart" (see
`CreateChartFromWizardCommand._default_chart_name`). This module resolves
that by suffixing a colliding name with the item's folder path. It lives
here rather than on Dataset/Chart themselves: the models don't care that a
UI selector needs a unique label, so that's a presentation concern, not a
model one.
"""
from collections import Counter
from typing import TYPE_CHECKING, List, Tuple

from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.item import Item

if TYPE_CHECKING:
    from pandaplot.models.project.project import Project


def disambiguated_display_options(items: List[Item], project: "Project") -> List[Tuple[str, str]]:
    """(id, display_name) for each of `items`, in the given order.

    When a name collides, the display name is suffixed with the item's
    folder path so it still reads as unique; unambiguous names are left
    untouched.
    """
    name_counts = Counter(item.name for item in items)
    options: List[Tuple[str, str]] = []
    for item in items:
        if name_counts[item.name] <= 1:
            options.append((item.id, item.name))
            continue
        folder_path = project.get_folder_path(item.id)
        location = " / ".join(folder_path) if folder_path else "project root"
        options.append((item.id, f"{item.name}  ({location})"))
    return options


def dataset_display_options(project: "Project") -> List[Tuple[str, str]]:
    """(id, display_name) for every dataset in `project`, in `get_all_items()`
    order. See `disambiguated_display_options` for how collisions are resolved.
    """
    datasets = [item for item in project.get_all_items() if isinstance(item, Dataset)]
    return disambiguated_display_options(datasets, project)


def chart_display_options(project: "Project") -> List[Tuple[str, str]]:
    """(id, display_name) for every chart in `project`, in `get_all_items()`
    order. See `disambiguated_display_options` for how collisions are resolved.
    """
    charts = [item for item in project.get_all_items() if isinstance(item, Chart)]
    return disambiguated_display_options(charts, project)
