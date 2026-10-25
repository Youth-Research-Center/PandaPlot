"""Tests for grouped repeated-measurement summaries."""

import numpy as np
import pandas as pd
import pytest

from pandaplot.models.project.items.column_role import ColumnRole
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.services.measurement_analysis import MeasurementAnalysisService


def _dataset_with_roles(data: pd.DataFrame, **roles: ColumnRole) -> Dataset:
    dataset = Dataset(name="Experiment", data=data)
    for column, role in roles.items():
        dataset.set_column_role(dataset.column_id(column), role)
    return dataset


def test_summarize_groups_measurements_and_reports_excluded_values():
    dataset = _dataset_with_roles(
        pd.DataFrame({
            "setpoint": [1, 1, 1, 2, 2, np.nan],
            "mode": ["A", "A", "A", "A", "A", None],
            "temperature": [10.0, 12.0, np.nan, 20.0, 22.0, 99.0],
            "pressure": [2.0, np.nan, 4.0, 6.0, 8.0, 10.0],
        }),
        setpoint=ColumnRole.CONTROLLED,
        mode=ColumnRole.FIXED,
        temperature=ColumnRole.MEASURED,
        pressure=ColumnRole.MEASURED,
    )

    result = MeasurementAnalysisService.summarize(dataset)

    first_temperature = result.table.iloc[0]
    assert first_temperature["setpoint"] == 1
    assert first_temperature["mode"] == "A"
    assert first_temperature["Measured variable"] == "temperature"
    assert first_temperature["Count"] == 2
    assert first_temperature["Mean"] == pytest.approx(11)
    assert first_temperature["Standard deviation"] == pytest.approx(np.sqrt(2))
    assert first_temperature["Standard error"] == pytest.approx(1)

    first_pressure = result.table.iloc[1]
    assert first_pressure["Count"] == 2
    assert first_pressure["Mean"] == pytest.approx(3)
    assert result.excluded_control_rows == 1
    assert result.fixed_missing_counts == (("mode", 1),)
    assert result.excluded_measurement_counts == (("temperature", 1), ("pressure", 1))


def test_summarize_combines_wide_format_replicate_columns():
    dataset = _dataset_with_roles(
        pd.DataFrame({
            "Nozzle_Area": [0, 1, 2, 3, 4, 5, 6, 7],
            "Velocity1": [0, 10, 6, 3, 1.5, 1.3, 0.7, 0.5],
            "Velocity2": [0, 10.2, 6, 3.5, 1.7, 1, 0.7, 0.45],
            "Velocity3": [0, 10, 5.8, 3.6, 1.6, 1.1, 0.75, 0.44],
            "Velocity4": [0, 10.2, 5.5, 2.8, 1.4, 0.99, 0.68, 0.43],
            "Velocity5": [0, 9.5, 6.3, 2.7, 1.55, 0.95, 0.66, 0.55],
        }),
        Nozzle_Area=ColumnRole.CONTROLLED,
        Velocity1=ColumnRole.MEASURED,
        Velocity2=ColumnRole.MEASURED,
        Velocity3=ColumnRole.MEASURED,
        Velocity4=ColumnRole.MEASURED,
        Velocity5=ColumnRole.MEASURED,
    )
    velocity_group = {
        dataset.column_id(column): "Velocity"
        for column in ("Velocity1", "Velocity2", "Velocity3", "Velocity4", "Velocity5")
    }

    result = MeasurementAnalysisService.summarize(dataset, measurement_groups=velocity_group)

    assert len(result.table) == 8
    assert result.table["Measured variable"].tolist() == ["Velocity"] * 8
    assert result.table["Count"].tolist() == [5] * 8
    assert result.table.loc[1, "Nozzle_Area"] == 1
    assert result.table.loc[1, "Mean"] == pytest.approx(9.98)
    assert result.table.loc[1, "Standard deviation"] == pytest.approx(np.std([10, 10.2, 10, 10.2, 9.5], ddof=1))
    assert result.table.loc[1, "Standard error"] == pytest.approx(
        result.table.loc[1, "Standard deviation"] / np.sqrt(5)
    )


def test_summarize_preserves_groups_with_no_valid_measurements():
    dataset = _dataset_with_roles(
        pd.DataFrame({"dose": [1, 1, 2], "response": [np.nan, "invalid", 7.0]}),
        dose=ColumnRole.CONTROLLED,
        response=ColumnRole.MEASURED,
    )

    result = MeasurementAnalysisService.summarize(dataset)

    empty_group = result.table.iloc[0]
    assert empty_group["dose"] == 1
    assert empty_group["Count"] == 0
    assert pd.isna(empty_group["Mean"])
    assert pd.isna(empty_group["Standard deviation"])
    assert pd.isna(empty_group["Standard error"])
    assert result.table.iloc[1]["Count"] == 1
    assert pd.isna(result.table.iloc[1]["Standard deviation"])
    assert pd.isna(result.table.iloc[1]["Standard error"])
    assert result.excluded_measurement_counts == (("response", 2),)


def test_summarize_blocks_varying_fixed_column():
    dataset = _dataset_with_roles(
        pd.DataFrame({"dose": [1, 1], "instrument": ["A", "B"], "response": [2, 3]}),
        dose=ColumnRole.CONTROLLED,
        instrument=ColumnRole.FIXED,
        response=ColumnRole.MEASURED,
    )

    with pytest.raises(ValueError, match="multiple observed values"):
        MeasurementAnalysisService.summarize(dataset)


def test_summarize_blocks_fixed_column_with_no_observed_values():
    dataset = _dataset_with_roles(
        pd.DataFrame({"dose": [1, 1], "instrument": [None, None], "response": [2, 3]}),
        dose=ColumnRole.CONTROLLED,
        instrument=ColumnRole.FIXED,
        response=ColumnRole.MEASURED,
    )

    with pytest.raises(ValueError, match="constant value cannot be verified"):
        MeasurementAnalysisService.summarize(dataset)


@pytest.mark.parametrize(
    ("roles", "message"),
    [
        ({"response": ColumnRole.MEASURED}, "at least one controlled"),
        ({"dose": ColumnRole.CONTROLLED}, "at least one measured"),
    ],
)
def test_summarize_requires_controlled_and_measured_columns(roles, message):
    dataset = Dataset(name="Experiment", data=pd.DataFrame({"dose": [1], "response": [2]}))
    for column, role in roles.items():
        dataset.set_column_role(dataset.column_id(column), role)

    with pytest.raises(ValueError, match=message):
        MeasurementAnalysisService.summarize(dataset)


def test_summarize_requires_at_least_one_usable_controlled_row():
    dataset = _dataset_with_roles(
        pd.DataFrame({"dose": [np.nan], "response": [2]}),
        dose=ColumnRole.CONTROLLED,
        response=ColumnRole.MEASURED,
    )

    with pytest.raises(ValueError, match="No rows have values"):
        MeasurementAnalysisService.summarize(dataset)


def test_summarize_disambiguates_result_headers_that_match_source_columns():
    dataset = _dataset_with_roles(
        pd.DataFrame({"Mean": [1, 1], "Count": [2.0, 4.0]}),
        Mean=ColumnRole.CONTROLLED,
        Count=ColumnRole.MEASURED,
    )

    result = MeasurementAnalysisService.summarize(dataset)

    assert list(result.table.columns) == [
        "Mean",
        "Measured variable",
        "Count",
        "Mean (2)",
        "Standard deviation",
        "Standard error",
    ]
    assert result.table.loc[0, "Mean (2)"] == pytest.approx(3)
