"""Grouped summary statistics for experimental measurements."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pandaplot.models.project.items.column_role import ColumnRole
from pandaplot.models.project.items.dataset import Dataset


@dataclass
class MeasurementAnalysisResult:
    """Grouped statistics and row/value exclusions for preview and reporting."""

    table: pd.DataFrame
    excluded_control_rows: int
    fixed_missing_counts: tuple[tuple[str, int], ...]
    excluded_measurement_counts: tuple[tuple[str, int], ...]


class MeasurementAnalysisService:
    """Compute repeated-measurement summaries without modifying project data."""

    @staticmethod
    def summarize(
        dataset: Dataset,
        roles: Mapping[str, ColumnRole | str] | None = None,
        *,
        measurement_groups: Mapping[str, str] | None = None,
    ) -> MeasurementAnalysisResult:
        """Group measurement columns by experimental variable and controlled values.

        Missing or non-numeric controlled values exclude that row from all
        groups. Missing, non-numeric, and infinite measured values are excluded
        from their variable's statistics. Multiple measured columns can share a
        measurement-group name, treating wide-format replicate columns as
        repeated observations of one quantity. Fixed columns must have at most
        one distinct observed value; missing fixed values are counted but do
        not exclude otherwise usable rows.

        Args:
            dataset: Dataset to analyze.
            roles: Optional column-id-to-role mapping. Defaults to the roles
                persisted on ``dataset``.
            measurement_groups: Optional measured-column-id-to-variable-name
                mapping. Unspecified measured columns use their column names.

        Raises:
            ValueError: If roles reference unavailable columns, no controlled
                or measured columns are selected, fixed columns vary, or no
                rows remain with valid controlled values.
        """
        if dataset.data is None:
            raise ValueError("Dataset data is not available.")

        selected_roles = roles if roles is not None else dataset.column_roles
        resolved_roles = MeasurementAnalysisService._resolve_roles(dataset, selected_roles)
        controlled = [name for name, role in resolved_roles if role is ColumnRole.CONTROLLED]
        fixed = [name for name, role in resolved_roles if role is ColumnRole.FIXED]
        measured = [name for name, role in resolved_roles if role is ColumnRole.MEASURED]

        if not controlled:
            raise ValueError("Assign at least one controlled column before generating a summary.")
        if not measured:
            raise ValueError("Assign at least one measured column before generating a summary.")

        selected_groups = measurement_groups if measurement_groups is not None else dataset.column_measurement_groups
        group_name_by_column = MeasurementAnalysisService._resolve_measurement_groups(
            dataset,
            measured,
            selected_groups,
        )
        measured_groups: dict[str, list[str]] = {}
        for column in measured:
            group_name = group_name_by_column[column]
            measured_groups.setdefault(group_name, []).append(column)

        frame = dataset.data
        fixed_values: dict[str, Any] = {}
        fixed_missing_counts: list[tuple[str, int]] = []
        for name in fixed:
            observed = frame[name].dropna()
            distinct = observed.drop_duplicates()
            if distinct.empty:
                raise ValueError(
                    f"Fixed column '{name}' has no observed values, so its constant value cannot be verified."
                )
            if len(distinct) > 1:
                raise ValueError(
                    f"Fixed column '{name}' has multiple observed values. "
                    "Correct its values or assign it another role."
                )
            fixed_values[name] = distinct.iloc[0] if not distinct.empty else pd.NA
            missing_count = int(frame[name].isna().sum())
            if missing_count:
                fixed_missing_counts.append((name, missing_count))

        control_mask = frame[controlled].notna().all(axis=1)
        valid_control_frame = frame.loc[control_mask]
        if valid_control_frame.empty:
            raise ValueError("No rows have values for every controlled column.")

        result_columns = MeasurementAnalysisService._result_column_names(
            [*controlled, *fixed, "Measured variable", "Count", "Mean", "Standard deviation", "Standard error"]
        )
        control_result_names = result_columns[:len(controlled)]
        fixed_result_names = result_columns[len(controlled):len(controlled) + len(fixed)]
        measured_name, count_name, mean_name, std_name, sem_name = result_columns[-5:]

        result_rows: list[dict[str, Any]] = []
        excluded_measurements = {name: 0 for name in measured}
        grouping_key = controlled[0] if len(controlled) == 1 else controlled
        grouped = valid_control_frame.groupby(grouping_key, sort=False, observed=True, dropna=True)
        for group_key, group in grouped:
            key_values = (group_key,) if len(controlled) == 1 else group_key
            group_values = dict(zip(control_result_names, key_values, strict=True))
            for name, output_name in zip(fixed, fixed_result_names, strict=True):
                group_values[output_name] = fixed_values[name]

            for measurement_name, source_columns in measured_groups.items():
                numeric_by_column = {
                    name: pd.to_numeric(group[name], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
                    for name in source_columns
                }
                valid_by_column = {
                    name: values[np.isfinite(values)]
                    for name, values in numeric_by_column.items()
                }
                for name in numeric_by_column:
                    excluded_measurements[name] += len(group) - len(valid_by_column[name])
                valid_values = np.concatenate(list(valid_by_column.values()))
                count = len(valid_values)
                mean = float(np.mean(valid_values)) if count else np.nan
                std = float(np.std(valid_values, ddof=1)) if count >= 2 else np.nan
                sem = std / np.sqrt(count) if count >= 2 else np.nan
                result_rows.append({
                    **group_values,
                    measured_name: measurement_name,
                    count_name: count,
                    mean_name: mean,
                    std_name: std,
                    sem_name: sem,
                })

        summary = pd.DataFrame(result_rows, columns=result_columns)
        return MeasurementAnalysisResult(
            table=summary,
            excluded_control_rows=int((~control_mask).sum()),
            fixed_missing_counts=tuple(fixed_missing_counts),
            excluded_measurement_counts=tuple(
                (name, count) for name, count in excluded_measurements.items() if count
            ),
        )

    @staticmethod
    def _resolve_roles(
        dataset: Dataset,
        roles: Mapping[str, ColumnRole | str],
    ) -> list[tuple[str, ColumnRole]]:
        """Resolve role assignments to live column names and validate IDs."""
        resolved: list[tuple[str, ColumnRole]] = []
        for column_id, role_value in roles.items():
            name = dataset.column_name(column_id)
            if name is None or name not in dataset.data.columns:
                raise ValueError(f"Assigned column id '{column_id}' is not available in this dataset.")
            try:
                role = ColumnRole(role_value)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Column '{name}' has an unsupported role.") from error
            resolved.append((name, role))
        return resolved

    @staticmethod
    def _resolve_measurement_groups(
        dataset: Dataset,
        measured_columns: list[str],
        groups: Mapping[str, str],
    ) -> dict[str, str]:
        """Resolve explicit names by stable column id, defaulting to column names."""
        resolved: dict[str, str] = {}
        for column in measured_columns:
            column_id = dataset.column_id(column)
            group_name = groups.get(column_id) if column_id is not None else None
            if group_name is None:
                group_name = column
            normalized_group = group_name.strip()
            if not normalized_group:
                raise ValueError(f"Measured column '{column}' needs a variable name.")
            resolved[column] = normalized_group
        return resolved

    @staticmethod
    def _result_column_names(names: list[str]) -> list[str]:
        """Disambiguate source names that collide with summary headings."""
        resolved: list[str] = []
        used: set[str] = set()
        for name in names:
            candidate = name
            suffix = 2
            while candidate in used:
                candidate = f"{name} ({suffix})"
                suffix += 1
            used.add(candidate)
            resolved.append(candidate)
        return resolved
