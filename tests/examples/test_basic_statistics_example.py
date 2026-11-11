import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from examples.basic_statistics.create_basic_statistics_example import (
    GROUP_HEIGHT_COLUMNS,
    HEIGHT,
    NUMERIC_COLUMNS,
    PEARSON_PAIRS,
    SLEEP,
    SPEARMAN_PAIRS,
    WEIGHT,
    create_basic_statistics_project,
    create_class_measurements,
    create_correlation_matrix,
    create_project,
    create_project_data_manager,
)
from pandaplot.analysis import DescriptiveStatsEngine, StatsEngine, StatTestType
from pandaplot.models.project.items import Chart, Dataset, Note


def _datasets_by_name(project) -> dict[str, Dataset]:
    return {item.name: item for item in project.get_all_items() if isinstance(item, Dataset)}


def _notes_by_name(project) -> dict[str, Note]:
    return {item.name: item for item in project.get_all_items() if isinstance(item, Note)}


def _charts_by_name(project) -> dict[str, Chart]:
    return {item.name: item for item in project.get_all_items() if isinstance(item, Chart)}


def _expected_results(measurements: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Fresh engine output keyed by dataset name, as the panels would create it."""
    descriptive = DescriptiveStatsEngine.describe([measurements[name] for name in NUMERIC_COLUMNS])
    expected = {descriptive.result_name(): descriptive.to_dataframe()}
    for test_type, pairs in ((StatTestType.PEARSON, PEARSON_PAIRS), (StatTestType.SPEARMAN, SPEARMAN_PAIRS)):
        for pair in pairs:
            result = StatsEngine.run_test(test_type, [measurements[name] for name in pair])
            expected[result.result_name()] = result.to_dataframe()
    return expected


def _assert_frames_close(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    """Compare numerically where both sides are numeric and as text otherwise (saving rewrites numeric-looking text, #643)."""
    assert list(actual.columns) == list(expected.columns)
    assert len(actual) == len(expected)
    for column in expected.columns:
        actual_numeric = pd.to_numeric(actual[column], errors="coerce")
        expected_numeric = pd.to_numeric(expected[column], errors="coerce")
        numeric = expected_numeric.notna()
        np.testing.assert_allclose(actual_numeric[numeric].to_numpy(float), expected_numeric[numeric].to_numpy(float), rtol=1e-6)
        assert (actual[column][~numeric].astype(str).to_numpy() == expected[column][~numeric].astype(str).to_numpy()).all()


@pytest.fixture(scope="module")
def measurements() -> pd.DataFrame:
    return create_class_measurements()


@pytest.fixture(scope="module")
def saved_path(tmp_path_factory):
    return create_basic_statistics_project(tmp_path_factory.mktemp("basic_statistics"))


@pytest.fixture(scope="module")
def loaded(saved_path):
    project = create_project_data_manager().load(str(saved_path))
    assert project.failed_item_ids == []
    return project


def test_generation_is_deterministic(tmp_path):
    first = create_project_data_manager().load(str(create_basic_statistics_project(tmp_path / "first")))
    second = create_project_data_manager().load(str(create_basic_statistics_project(tmp_path / "second")))
    first_datasets, second_datasets = _datasets_by_name(first), _datasets_by_name(second)
    assert first_datasets.keys() == second_datasets.keys()
    for name, dataset in first_datasets.items():
        pdt.assert_frame_equal(dataset.data, second_datasets[name].data)
    assert {n: note.content for n, note in _notes_by_name(first).items()} == {n: note.content for n, note in _notes_by_name(second).items()}


def test_measurements_shape_and_types(measurements):
    assert len(measurements) == 120
    assert list(measurements.columns) == ["Student", "Group", "Age (years)", HEIGHT, WEIGHT, "Shoe size (EU)", SLEEP]
    assert measurements["Student"].tolist()[:2] == ["S001", "S002"]
    assert not pd.api.types.is_numeric_dtype(measurements["Student"])
    assert measurements["Group"].value_counts().to_dict() == {"A": 40, "B": 40, "C": 40}
    assert measurements["Age (years)"].dtype == np.int64
    assert set(measurements["Age (years)"]) == {14, 15, 16, 17, 18}
    assert measurements["Age (years)"].mode().tolist() == [16]


def test_blank_cells_only_in_hours_of_sleep(measurements):
    missing = measurements.isna().sum()
    assert missing[SLEEP] == 2
    assert missing.drop(SLEEP).sum() == 0


def test_correlation_targets(measurements):
    assert 0.6 < measurements[HEIGHT].corr(measurements[WEIGHT]) < 0.8
    assert 0.7 < measurements[HEIGHT].corr(measurements["Shoe size (EU)"]) < 0.9
    assert abs(measurements[HEIGHT].corr(measurements[SLEEP])) < 0.2


def test_height_by_group_holds_the_same_heights(measurements):
    project = create_project(measurements)
    by_group = _datasets_by_name(project)["Height by group"].data
    assert list(by_group.columns) == list(GROUP_HEIGHT_COLUMNS)
    assert len(by_group) == 40
    assert not by_group.isna().any().any()
    assert sorted(by_group.to_numpy().ravel()) == sorted(measurements[HEIGHT])


def test_in_memory_results_equal_engine_output_exactly(measurements):
    datasets = _datasets_by_name(create_project(measurements))
    expected = _expected_results(measurements)
    assert len(expected) == 4
    for name, frame in expected.items():
        assert name in datasets
        pdt.assert_frame_equal(datasets[name].data, frame)
    pdt.assert_frame_equal(datasets["Correlation matrix (Pearson r)"].data, create_correlation_matrix(measurements))
    descriptive = DescriptiveStatsEngine.describe([measurements[name] for name in NUMERIC_COLUMNS])
    assert _notes_by_name(create_project(measurements))[descriptive.report_name()].content == descriptive.report()


def test_saved_results_match_engine_output_numerically(loaded):
    datasets = _datasets_by_name(loaded)
    measurements = datasets["Class measurements"].data
    for name, frame in _expected_results(measurements).items():
        _assert_frames_close(datasets[name].data, frame)
    _assert_frames_close(datasets["Correlation matrix (Pearson r)"].data, create_correlation_matrix(measurements))


def test_results_are_at_the_project_root(loaded):
    for item in loaded.get_all_items():
        if isinstance(item, Dataset):
            assert item.parent_id == loaded.root.id, f"{item.name} should be at the project root"


def test_correlation_matrix_is_symmetric_with_unit_diagonal(loaded):
    matrix = _datasets_by_name(loaded)["Correlation matrix (Pearson r)"].data
    assert matrix["Variable"].tolist() == list(NUMERIC_COLUMNS)
    values = matrix[list(NUMERIC_COLUMNS)].to_numpy(float)
    np.testing.assert_allclose(np.diag(values), 1.0)
    np.testing.assert_allclose(values, values.T)


def test_chart_inventory_and_featured_charts(loaded):
    charts = _charts_by_name(loaded)
    assert {name: (chart.chart_type.value, len(chart.data_series)) for name, chart in charts.items()} == {
        "Height (cm)": ("hist", 1),
        "Age (years)": ("hist", 1),
        "Height by group": ("box", 3),
        "Height vs Weight": ("scatter", 1),
        "Height vs Hours of sleep": ("scatter", 1),
    }
    assert charts["Age (years)"].config.hist_bins == 5
    featured = loaded.example_info.featured_chart_ids
    assert featured == (charts["Height (cm)"].id, charts["Height by group"].id, charts["Height vs Weight"].id)
    assert "r = 0.68" in charts["Height vs Weight"].config.title


def test_notes_and_start_note(loaded):
    notes = _notes_by_name(loaded)
    for name in ("Start here", "1 Descriptive statistics", "2 Histograms", "3 Box plots", "4 Correlation", "5 Try it yourself"):
        assert notes[name].content.strip()
    assert loaded.find_item(loaded.example_info.start_note_id) is notes["Start here"]
    assert "does not compute the mode yet" in notes["1 Descriptive statistics"].content
    assert "1.5 x IQR" in notes["3 Box plots"].content
    assert "correlation is not causation" in notes["4 Correlation"].content.lower()
    assert any(name.startswith("Descriptive stats report [") for name in notes)
    for note in notes.values():
        assert {character for character in note.content if not character.isascii()} <= {"α"}
        assert "#6" not in note.content, "learner-facing notes must not cite issue numbers"


def test_correlation_notes_quote_the_computed_results(loaded):
    notes = _notes_by_name(loaded)
    measurements = _datasets_by_name(loaded)["Class measurements"].data
    weight = StatsEngine.run_test(StatTestType.PEARSON, [measurements[HEIGHT], measurements[WEIGHT]])
    sleep = StatsEngine.run_test(StatTestType.PEARSON, [measurements[HEIGHT], measurements[SLEEP]])
    spearman = StatsEngine.run_test(StatTestType.SPEARMAN, [measurements["Age (years)"], measurements[HEIGHT]])
    correlation = notes["4 Correlation"].content
    assert f"p = {weight.p_value:.2g}" in correlation
    assert f"p = {sleep.p_value:.2f}" in correlation
    assert f"rho = {spearman.statistic:.2f}" in correlation
    assert "no straight-line trend" in correlation
    matrix = create_correlation_matrix(measurements)
    weight_shoe = matrix.loc[matrix["Variable"] == WEIGHT, "Shoe size (EU)"].item()
    assert f"r = {weight_shoe:.2f}" in notes["5 Try it yourself"].content
    assert "Reading the p-value" in correlation
