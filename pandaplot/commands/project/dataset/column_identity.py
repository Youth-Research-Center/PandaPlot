"""Keep the ids of columns a command creates stable across undo and redo (#667)."""

from collections.abc import Iterable, Mapping

from pandaplot.models.project.items import Dataset


def keep_created_column_ids(
    dataset: Dataset, column_names: Iterable[object], first_run_ids: Mapping[str, str],
) -> dict[str, str]:
    """Record or restore the ids of the columns a command has just created.

    ``Dataset.set_data`` gives every new column name a fresh id, so a command whose ``redo()`` builds its columns
    again would hand later commands (formula columns, chart series, fits) ids that no longer exist. Call this right
    after ``set_data``: on the first run it records the new ids, and on a replay it gives each column back the id it
    had the first time.

    Args:
        dataset: The dataset the columns were added to.
        column_names: The names of the columns the command created.
        first_run_ids: The mapping this function returned on the first run, or an empty mapping on the first run.

    Returns:
        The column ids by name to keep for the next replay.

    Raises:
        ValueError: If a recorded id already belongs to a different column.
    """
    if first_run_ids:
        for name, column_id in first_run_ids.items():
            dataset.reassign_column_id(name, column_id)
        return dict(first_run_ids)
    names = [str(name) for name in column_names]
    return {name: column_id for name in names if (column_id := dataset.column_id(name)) is not None}
