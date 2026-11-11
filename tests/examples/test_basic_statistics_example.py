import math
import re
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from examples.basic_statistics.create_basic_statistics_example import (
    EXAMPLE_SUMMARY,
    GLOSSARY_ENTRIES,
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
from pandaplot.models.project.items import Chart, Dataset, Folder, Note

BUNDLED_PROJECT = Path(__file__).resolve().parents[2] / "examples" / "basic_statistics" / "basic_statistics.pplot"
REGENERATE_COMMAND = "uv run python examples/basic_statistics/create_basic_statistics_example.py"


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


EXPECTED_LAYOUT = {
    "0 The data": [("Note", "About the data"), ("Dataset", "Class measurements"), ("Dataset", "Height by group")],
    "1 Descriptive statistics": [
        ("Note", "Descriptive statistics"),
        ("Dataset", "Descriptive stats [Age (years), Height (cm), Weight (kg), Shoe size (EU), Hours of sleep]"),
        ("Note", "Descriptive stats report [Age (years), Height (cm), Weight (kg), Shoe size (EU), Hours of sleep]"),
    ],
    "2 Histograms": [("Note", "Histograms"), ("Chart", "Height (cm)"), ("Chart", "Age (years)")],
    "3 Box plots": [("Note", "Box plots"), ("Chart", "Height by group")],
    "4 Correlation": [
        ("Note", "Scatter plots and correlation"),
        ("Note", "Is it real? p-values, Pearson or Spearman, causation"),
        ("Chart", "Height vs Weight"),
        ("Chart", "Height vs Hours of sleep"),
        ("Dataset", "Pearson correlation [Height (cm), Weight (kg)]"),
        ("Dataset", "Pearson correlation [Height (cm), Hours of sleep]"),
        ("Dataset", "Spearman rank correlation [Age (years), Height (cm)]"),
        ("Dataset", "Correlation matrix (Pearson r)"),
    ],
    "5 Try it yourself": [("Note", "Try it yourself")],
}


def test_project_layout(loaded):
    root_children = [(type(item).__name__, item.name) for item in loaded.root.get_items()]
    assert root_children == [("Note", "Start here"), ("Note", "Glossary"), *(("Folder", name) for name in EXPECTED_LAYOUT)]
    folders = {item.name: item for item in loaded.root.get_items() if isinstance(item, Folder)}
    for name, expected in EXPECTED_LAYOUT.items():
        assert [(type(item).__name__, item.name) for item in folders[name].get_items()] == expected, name
        assert all(item.parent_id == folders[name].id for item in folders[name].get_items())
    assert sum(isinstance(item, Folder) for item in loaded.get_all_items()) == len(EXPECTED_LAYOUT), "no nested folders"


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


NOTE_NAMES = (
    "Start here",
    "Glossary",
    "About the data",
    "Descriptive statistics",
    "Histograms",
    "Box plots",
    "Scatter plots and correlation",
    "Is it real? p-values, Pearson or Spearman, causation",
    "Try it yourself",
)


def _taught_notes(notes: dict[str, Note]) -> dict[str, Note]:
    return {name: notes[name] for name in NOTE_NAMES}


def test_notes_and_start_note(loaded):
    notes = _notes_by_name(loaded)
    for note in _taught_notes(notes).values():
        assert note.content.strip()
    assert loaded.find_item(loaded.example_info.start_note_id) is notes["Start here"]
    assert "does not compute the mode yet" in notes["Descriptive statistics"].content
    assert "1.5 x IQR" in notes["Box plots"].content
    assert "correlation is not causation" in notes["Is it real? p-values, Pearson or Spearman, causation"].content.lower()
    assert any(name.startswith("Descriptive stats report [") for name in notes)
    for note in notes.values():
        assert {character for character in note.content if not character.isascii()} <= {"α"}
        assert not re.search(r"#\d", note.content), "learner-facing notes must not cite issue numbers"
        assert "{" not in note.content and "}" not in note.content, "every placeholder must be filled"


def test_each_note_starts_with_its_name_as_the_title(loaded):
    for name, note in _taught_notes(_notes_by_name(loaded)).items():
        assert note.content.splitlines()[0] == f"# {name}"


def test_notes_refer_to_each_other_and_to_folders_by_name(loaded):
    notes = _notes_by_name(loaded)
    names_in_notes = " ".join(note.content for note in _taught_notes(notes).values())
    for phrase in ("next note", "previous note", "note 4", "note 5"):
        assert phrase not in names_in_notes
    open_data = "In the project tree, expand the **0 The data** folder and double-click **Class measurements**."
    open_groups = "In the project tree, expand the **0 The data** folder and double-click **Height by group**."
    for name in ("Start here", "About the data", "Descriptive statistics", "Scatter plots and correlation"):
        assert open_data in notes[name].content
    for name in ("About the data", "Try it yourself"):
        assert open_groups in notes[name].content


def test_notes_say_where_results_land(loaded):
    notes = _notes_by_name(loaded)
    descriptive = notes["Descriptive statistics"].content
    assert "puts your copy next to the dataset, in the **0 The data** folder" in descriptive
    assert "Drag items onto any folder in the project tree to tidy up" in descriptive
    correlation = notes["Scatter plots and correlation"].content
    assert "puts your copy at the top level of the project tree, not in a folder" in correlation
    assert "Drag it onto a folder in the project tree to tidy up" in correlation


def test_notes_use_the_exact_panel_labels(loaded):
    notes = _notes_by_name(loaded)
    descriptive = notes["Descriptive statistics"].content
    for label in (
        "**Columns**", "*Select one or more numeric columns (Ctrl/Shift-click).*", "**Select all**", "**Options**",
        "**Significant digits:**", "**Also add a written report (note)**", "**Compute**", "**Add to Project**", "**Clear**",
    ):
        assert label in descriptive
    correlation = notes["Scatter plots and correlation"].content
    for label in (
        "**Test:**", "**Pearson correlation**", "**Data Selection**", "**Column A:**", "**Column B:**", "**Parameters**",
        "**Significance (α):**", "**Alternative:**", "**Run**", "**Correlation r**", "**R-squared**", "**Strength**", "**p-value**",
        "**Conclusion**",
    ):
        assert label in correlation
    exercises = notes["Try it yourself"].content
    for label in (
        "**Spearman correlation (rank)**", "**One-way ANOVA**", "**Kruskal-Wallis (nonparametric)**", "**Groups:**",
        "*Select 2+ numeric group columns (Ctrl/Shift-click).*", "**Challenge.**",
    ):
        assert label in exercises
    assert "**Chart** tab of Chart Properties" in notes["Histograms"].content
    assert "**Bins:**" in notes["Histograms"].content


def test_summary_is_one_short_sentence():
    assert len(EXAMPLE_SUMMARY) <= 160
    assert EXAMPLE_SUMMARY.count(". ") == 0


def _glossary_terms(note: Note) -> list[str]:
    return re.findall(r"^- \*\*(.+?)\*\*:", note.content, flags=re.MULTILINE)


EXPECTED_GLOSSARY_TERMS = (
    "ANOVA", "Bin", "Box plot", "Categorical", "Causation", "Coefficient of variation", "Continuous", "Correlation", "Dataset",
    "Discrete", "Distribution", "e-notation", "Fail to reject H0", "Histogram", "IQR", "Kruskal-Wallis", "Kurtosis", "Linear", "Mean",
    "Median", "Mode", "Monotonic", "Null hypothesis (H0)", "Numerical", "Outlier", "p-value", "Pearson", "Population",
    "Quartile (Q1, Q3)", "r (correlation coefficient)", "R-squared", "Range", "Rank", "Reject H0", "rho", "Sample", "Scatter plot",
    "SEM (standard error of the mean)", "Significance level (α)", "Skewed", "Skewness", "Spearman", "Standard deviation", "Symmetric",
    "Two-sided", "Variable", "Variance", "Whisker",
)


def test_glossary_entries_are_one_line_each_and_sorted(loaded):
    glossary = _notes_by_name(loaded)["Glossary"]
    terms = _glossary_terms(glossary)
    assert terms == sorted(EXPECTED_GLOSSARY_TERMS, key=str.casefold)
    entry_lines = [line for line in glossary.content.splitlines() if line.startswith("- ")]
    assert len(entry_lines) == len(terms) == len(GLOSSARY_ENTRIES)
    assert all(line.split(": ", 1)[1].strip() for line in entry_lines)


def _height_stats(measurements: pd.DataFrame) -> dict[str, str]:
    """Descriptive values for Height as the panel prints them, from an independent describe() call."""
    table = DescriptiveStatsEngine.describe([measurements[HEIGHT]]).to_dataframe().set_index("Statistic")[HEIGHT]
    return {label: str(table[label]) for label in ("Mean", "Median (Q2)", "Std. deviation", "Minimum", "Maximum")}


def test_descriptive_note_quotes_the_computed_values(loaded):
    notes = _notes_by_name(loaded)
    measurements = _datasets_by_name(loaded)["Class measurements"].data
    heights = measurements[HEIGHT].to_numpy(float)
    stats = _height_stats(measurements)
    # The panel strings are shortened to 6 significant digits, so check them against numpy as well.
    assert float(stats["Mean"]) == pytest.approx(heights.mean(), rel=1e-5)
    assert float(stats["Median (Q2)"]) == pytest.approx(np.median(heights))
    assert float(stats["Std. deviation"]) == pytest.approx(heights.std(ddof=1), rel=1e-5)
    assert (float(stats["Minimum"]), float(stats["Maximum"])) == (heights.min(), heights.max())
    mean, sd = heights.mean(), heights.std(ddof=1)
    within = int(np.sum((heights >= mean - sd) & (heights <= mean + sd)))
    assert 0.6 <= within / len(heights) <= 0.75
    descriptive = notes["Descriptive statistics"].content
    assert (
        f"For **Height (cm)**: mean {stats['Mean']}, median {stats['Median (Q2)']}, SD {stats['Std. deviation']}, "
        f"minimum {stats['Minimum']}, maximum {stats['Maximum']}."
    ) in descriptive
    assert (
        f"the mean height is {mean:.1f} cm and the SD is {sd:.1f} cm, so mean plus or minus SD runs from {mean - sd:.1f} to {mean + sd:.1f} cm. "
        f"{within} of the {len(heights)} heights ({100 * within / len(heights):.1f}%) are in that range."
    ) in descriptive
    assert f"**Hours of sleep** shows a **Count** of {measurements[SLEEP].notna().sum()} and **Missing** of {measurements[SLEEP].isna().sum()}" in descriptive
    assert f"**Group** has {measurements['Group'].value_counts().iloc[0]} students in each of A, B and C" in descriptive
    assert f"The mean ({stats['Mean']}) and the median ({stats['Median (Q2)']})" in notes["Histograms"].content


def test_age_mode_and_group_claims(loaded):
    notes = _notes_by_name(loaded)
    measurements = _datasets_by_name(loaded)["Class measurements"].data
    modes = measurements["Age (years)"].mode()
    assert len(modes) == 1
    mode = int(modes.item())
    count = int((measurements["Age (years)"] == mode).sum())
    assert f"the mode is {mode}, with {count} students" in notes["Descriptive statistics"].content
    assert f"age {mode}, with {count} students" in notes["Histograms"].content
    assert "uses 5 bins" in notes["Histograms"].content
    assert measurements["Group"].value_counts().nunique() == 1, "Group has no single mode"


def _beyond_whiskers(values: np.ndarray) -> np.ndarray:
    """Points outside matplotlib's default whiskers (whis=1.5 on linearly interpolated quartiles)."""
    q1, q3 = np.percentile(values, [25, 75])
    return values[(values < q1 - 1.5 * (q3 - q1)) | (values > q3 + 1.5 * (q3 - q1))]


def test_box_plot_note_quotes_medians_and_the_single_outlier(loaded):
    notes = _notes_by_name(loaded)
    datasets = _datasets_by_name(loaded)
    by_group = datasets["Height by group"].data
    table = DescriptiveStatsEngine.describe([by_group[column] for column in GROUP_HEIGHT_COLUMNS]).to_dataframe().set_index("Statistic")
    medians = [str(table.loc["Median (Q2)", column]) for column in GROUP_HEIGHT_COLUMNS]
    for column, median in zip(GROUP_HEIGHT_COLUMNS, medians, strict=True):
        assert float(median) == pytest.approx(by_group[column].median())
    box = notes["Box plots"].content
    assert f"are {medians[0]} cm for A, {medians[1]} cm for B and {medians[2]} cm for C" in box
    beyond = {column: _beyond_whiskers(by_group[column].to_numpy(float)) for column in GROUP_HEIGHT_COLUMNS}
    assert sum(len(points) for points in beyond.values()) == 1
    assert len(beyond["Group C (cm)"]) == 1
    outlier = float(beyond["Group C (cm)"][0])
    measurements = datasets["Class measurements"].data
    students = measurements[(measurements["Group"] == "C") & (measurements[HEIGHT] == outlier)]["Student"]
    assert len(students) == 1
    assert f"One point lies beyond a whisker: {outlier:g} cm, in group C (student {students.item()})." in box
    assert outlier == by_group["Group C (cm)"].max() == measurements[HEIGHT].max()


def test_correlation_notes_quote_the_computed_results(loaded):
    notes = _notes_by_name(loaded)
    measurements = _datasets_by_name(loaded)["Class measurements"].data
    weight = StatsEngine.run_test(StatTestType.PEARSON, [measurements[HEIGHT], measurements[WEIGHT]])
    sleep = StatsEngine.run_test(StatTestType.PEARSON, [measurements[HEIGHT], measurements[SLEEP]])
    spearman = StatsEngine.run_test(StatTestType.SPEARMAN, [measurements["Age (years)"], measurements[HEIGHT]])
    weight_rows, sleep_rows, spearman_rows = dict(weight.rows), dict(sleep.rows), dict(spearman.rows)
    real, scatter = notes["Is it real? p-values, Pearson or Spearman, causation"].content, notes["Scatter plots and correlation"].content
    assert weight_rows["p-value"] == "8.49e-18" and f"p = {weight_rows['p-value']}." in real
    assert f"p = {sleep_rows['p-value']} (about {sleep.p_value:.2f})" in real
    assert f"rho = {spearman.statistic:.2f} and p = {spearman_rows['p-value']}" in real
    assert f"That is a {spearman_rows['Strength']} correlation" in real
    assert "no straight-line trend" in real
    pearson_h0, spearman_h0 = weight_rows["H0"], spearman_rows["H0"]
    assert f'"{pearson_h0}"' in real
    assert f'"{spearman_h0}"' in real
    assert weight_rows["Conclusion"].startswith("Reject H0 (p = ") and sleep_rows["Conclusion"].startswith("Fail to reject H0 (p = ")
    assert "no significant evidence that" in sleep_rows["Conclusion"]
    assert f"r = {weight.statistic:.2f}, which PandaPlot calls {weight_rows['Strength']}. R-squared is {weight.statistic**2:.0%}" in scatter
    assert f"Here r = {sleep.statistic:.2f}, which PandaPlot calls {sleep_rows['Strength']}." in scatter
    assert f"This agrees with the tiny r = {sleep.statistic:.2f}." in real
    assert f"use {sleep_rows['N pairs']} students and the rest use {len(measurements)}" in scatter
    assert weight.p_value < 0.05 <= sleep.p_value
    matrix = create_correlation_matrix(measurements)
    weight_shoe = matrix.loc[matrix["Variable"] == WEIGHT, "Shoe size (EU)"].item()
    assert f"r = {weight_shoe:.2f} for them" in real
    assert f"r = {weight_shoe:.2f} in **Correlation matrix (Pearson r)**" in notes["Try it yourself"].content
    assert "Reading the p-value" not in real
    assert weight_rows["p-value"] in notes["Glossary"].content


def test_coin_example_is_computed_and_two_sided(loaded):
    real = _notes_by_name(loaded)["Is it real? p-values, Pearson or Spearman, causation"].content
    ways = 2 * (math.comb(10, 9) + math.comb(10, 10))
    assert ways == 22
    assert f"{ways} of them have at least 9 tosses on the same side" in real
    assert f"{ways} out of 1024 cases, which is about {ways / 1024:.2g}" in real
    assert f"{ways / 1024:.2g}" == "0.021"


def test_spearman_and_pearson_claims(loaded):
    measurements = _datasets_by_name(loaded)["Class measurements"].data
    pearson = StatsEngine.run_test(StatTestType.PEARSON, [measurements[HEIGHT], measurements[WEIGHT]]).statistic
    spearman = StatsEngine.run_test(StatTestType.SPEARMAN, [measurements[HEIGHT], measurements[WEIGHT]]).statistic
    assert abs(pearson - spearman) < 0.1, "the Spearman warm-up says the two are similar"
    groups = [_datasets_by_name(loaded)["Height by group"].data[column] for column in GROUP_HEIGHT_COLUMNS]
    for test_type in (StatTestType.ONE_WAY_ANOVA, StatTestType.KRUSKAL_WALLIS):
        conclusion = dict(StatsEngine.run_test(test_type, groups).rows)["Conclusion"]
        assert conclusion.startswith("Reject H0"), "the challenges say the two tests agree"
    assert dict(StatsEngine.run_test(StatTestType.ONE_WAY_ANOVA, groups).rows)["H0"] == "all group means are equal"
    assert dict(StatsEngine.run_test(StatTestType.KRUSKAL_WALLIS, groups).rows)["H0"] == "all groups have the same distribution"


def test_worked_examples_in_the_notes_are_correct():
    scores = [2, 3, 3, 4, 8]
    assert (statistics.mean(scores), statistics.median(scores), statistics.mode(scores)) == (4, 3, 3)
    pocket = [5, 6, 6, 7, 8]
    assert (sum(pocket), statistics.mean(pocket), statistics.median(pocket)) == (32, 6.4, 6)
    with_outlier = [5, 6, 6, 7, 100]
    assert (sum(with_outlier), statistics.mean(with_outlier), statistics.median(with_outlier)) == (124, 24.8, 6)
    assert statistics.mean([4, 4, 4, 4, 4]) == statistics.mean([0, 0, 4, 8, 8]) == 4
    assert statistics.stdev([4, 4, 4, 4, 4]) < statistics.stdev([0, 0, 4, 8, 8])
    assert (statistics.mean([3, 5, 7]), statistics.variance([3, 5, 7]), statistics.stdev([3, 5, 7])) == (5, 4, 2)
    assert 10 - 1.5 * (14 - 10) == 4 and 14 + 1.5 * (14 - 10) == 20
    squares = [1, 4, 9, 16, 25]
    assert np.corrcoef([1, 2, 3, 4, 5], squares)[0, 1] == pytest.approx(0.98, abs=0.005)
    assert 0.5**2 == 0.25


def _normalise(value, names: dict[str, str]):
    """Replace item and column ids by names and drop timestamps, so two generated projects compare equal."""
    if isinstance(value, dict):
        return {key: _normalise(item, names) for key, item in value.items() if key not in {"created_at", "modified_at"}}
    if isinstance(value, (list, tuple)):
        return [_normalise(item, names) for item in value]
    return names.get(value, value) if isinstance(value, str) else value


def _id_names(project) -> dict[str, str]:
    names = {}
    for item in project.get_all_items():
        names[item.id] = f"item:{item.name}"
        if isinstance(item, Dataset):
            for column in item.data.columns:
                column_id = item.column_id(column)
                if column_id:
                    names[column_id] = f"column:{item.name}.{column}"
    return names


def _parent_name(project, item) -> str:
    parent = project.find_item(item.parent_id) if item.parent_id else None
    return parent.name if parent is not None else ""


def test_bundled_project_file_is_current(tmp_path):
    """The committed .pplot must equal a fresh generation; both go through the same save and load round trip."""
    message = f"examples/basic_statistics/basic_statistics.pplot is stale; regenerate it with: {REGENERATE_COMMAND}"
    assert BUNDLED_PROJECT.is_file(), message
    manager = create_project_data_manager()
    bundled = manager.load(str(BUNDLED_PROJECT))
    fresh = manager.load(str(create_basic_statistics_project(tmp_path)))
    assert bundled.failed_item_ids == [] and fresh.failed_item_ids == []

    def tree(project):
        return [(type(item).__name__, item.name, _parent_name(project, item)) for item in project.get_all_items()]

    assert tree(bundled) == tree(fresh), message
    assert bundled.description == fresh.description, message
    bundled_items = {(type(item).__name__, item.name): item for item in bundled.get_all_items()}
    fresh_items = {(type(item).__name__, item.name): item for item in fresh.get_all_items()}
    assert bundled_items.keys() == fresh_items.keys(), message
    bundled_names, fresh_names = _id_names(bundled), _id_names(fresh)
    for key, item in bundled_items.items():
        other = fresh_items[key]
        if isinstance(item, Note):
            assert item.content == other.content, f"{key}: {message}"
        elif isinstance(item, Dataset):
            pdt.assert_frame_equal(item.data, other.data, obj=f"{key[1]}: {message}")
        elif isinstance(item, Chart):
            assert _normalise(item.to_dict(), bundled_names) == _normalise(other.to_dict(), fresh_names), f"{key}: {message}"
    assert _normalise(bundled.example_info.to_dict(), bundled_names) == _normalise(fresh.example_info.to_dict(), fresh_names), message
