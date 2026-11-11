import pytest

from examples.smoothing_derivatives.create_smoothing_example import create_project_data_manager
from pandaplot.gui.components.tabs.chart.chart_editor import ChartSizeDefaults, cm_to_inches, render_chart, resolve_chart_series_data
from pandaplot.gui.components.tabs.chart.headless_chart_canvas import HeadlessChartCanvas
from pandaplot.models.project.example_info import ExampleLevel, ExampleSection, example_tag
from pandaplot.models.project.items import Chart, Note
from pandaplot.utils.examples import discover_example_projects, get_examples_dir

# name -> (section, level, tags)
EXPECTED = {
    "Curve Fitting Examples": (ExampleSection.ANALYSING_DATA, ExampleLevel.BEGINNER, {"mathematics", "curve_fitting"}),
    "Damped Pendulum Simulation": (ExampleSection.ANALYSING_DATA, ExampleLevel.INTERMEDIATE, {"physics", "mathematics", "charts"}),
    "Sales Analysis Project": (ExampleSection.GETTING_STARTED, ExampleLevel.BEGINNER, {"business", "descriptive_statistics", "charts"}),
    "Smoothing and Derivatives": (ExampleSection.ANALYSING_DATA, ExampleLevel.INTERMEDIATE, {"signal_processing", "smoothing", "derivatives"}),
    "Functions": (ExampleSection.CHARTS, ExampleLevel.BEGINNER, {"mathematics", "charts"}),
    "Basic Statistics": (
        ExampleSection.ANALYSING_DATA, ExampleLevel.BEGINNER, {"statistics", "descriptive_statistics", "statistical_tests", "charts"},
    ),
}


@pytest.fixture(scope="module")
def examples():
    return {example.name: example for example in discover_example_projects(get_examples_dir())}


def test_six_examples_are_discovered(examples):
    assert set(examples) == set(EXPECTED)
    assert "Funtions" not in examples


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_metadata_is_complete(examples, name):
    example = examples[name]
    section, level, tags = EXPECTED[name]
    assert example.section is section
    assert example.level is level
    assert {tag.id for tag in example.tags} == tags
    assert all(example_tag(tag.id) is tag for tag in example.tags)
    assert 2 <= len(example.featured_chart_ids) <= 3
    assert example.start_note_id is not None
    assert example.summary
    assert example.summary != "A new project created with PandaPlot"
    assert example.description.strip()
    assert example.data_credit.strip()
    assert example.dataset_count >= 1
    assert example.chart_count >= 2


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_loads_and_featured_charts_render(examples, name):
    example = examples[name]
    project = create_project_data_manager().load(example.path)
    assert project.failed_item_ids == []
    assert project.example_info.is_example
    for chart_id in example.featured_chart_ids:
        assert isinstance(project.find_item(chart_id), Chart)
    assert isinstance(project.find_item(example.start_note_id), Note)
    for chart in (item for item in project.get_all_items() if isinstance(item, Chart)):
        # A PNG alone proves little: unresolved series are skipped and an empty chart still renders.
        assert chart.data_series, f"{chart.name} has no series"
        resolved = resolve_chart_series_data(project, chart)
        for series, data in zip(chart.data_series, resolved, strict=True):
            assert data.error is None, f"{chart.name}: series {series.label!r} does not resolve: {data.error}"
            if series.is_fit:
                continue
            dataset = project.find_item(series.dataset_id)
            for column_id in _optional_column_ids(series):
                assert dataset.column_name(column_id) is not None, f"{chart.name}: series {series.label!r} references a missing column"
        canvas = HeadlessChartCanvas(width=cm_to_inches(20), height=cm_to_inches(15), dpi=50)
        result = render_chart(chart, canvas, resolved, ChartSizeDefaults(20.0, 15.0, 50), interactive=False)
        assert result.series_errors == [], f"{chart.name} did not render cleanly: {result.series_errors}"


_OPTIONAL_STYLE_ROLES = ("u", "v", "w", "z", "magnitude", "label", "twin_y")
_ERROR_BAR_COLUMN_FIELDS = ("x_error_column_id", "y_error_column_id", "x_error_minus_column_id", "y_error_minus_column_id")


def _optional_column_ids(series) -> list[str]:
    """Column ids a series references outside x/y; the renderer resolves these leniently, so check them explicitly."""
    style = series.style
    ids = [getattr(style, f"{role}_column_id", "") for role in _OPTIONAL_STYLE_ROLES]
    error_bars = getattr(style, "error_bars", None)
    if error_bars is not None:
        ids += [getattr(error_bars, field, "") for field in _ERROR_BAR_COLUMN_FIELDS]
    return [column_id for column_id in ids if column_id]
