"""Cross-item migration: backfill column ids on chart series/fits.

Legacy references (and any saved with an empty id) store columns by
name only; assign_* resolves matching names to a stable id so a later
column rename doesn't break the reference. Unmatched names keep an
empty id and fall back to the name at resolve time.

Needs a fully-instantiated Project, not a raw dict, since it looks up
each series' source Dataset by id — data unavailable from one item's
raw dict in isolation. See migrations/per_item/ for the dict -> dict
counterpart used when a migration doesn't need another item's data.
"""
from pandaplot.models.project.items.chart import (
    Chart,
    assign_fit_column_ids,
    assign_series_column_ids,
)
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project


def migrate_column_ids(project: Project) -> None:
    for item in project.get_all_items():
        if not isinstance(item, Chart):
            continue
        for series in item.data_series:
            dataset = project.find_item(series.dataset_id)
            if isinstance(dataset, Dataset):
                assign_series_column_ids(series, dataset)
        for fit in item.fit_data:
            dataset = project.find_item(fit.source_dataset_id)
            if isinstance(dataset, Dataset):
                assign_fit_column_ids(fit, dataset)
