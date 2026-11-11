"""Generate a project of mathematical functions and a tour of PandaPlot's chart types.

The data for the function charts is computed here; the other datasets are read from ``examples/datasets``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.project import Project
from pandaplot.models.project.example_info import ExampleInfo, ExampleLevel, ExampleSection
from pandaplot.models.project.items import Chart, Dataset, Folder, Note
from pandaplot.models.project.items.column_role import ColumnRole
from pandaplot.services.measurement_analysis.measurement_analysis_service import MeasurementAnalysisService
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager

DATASETS_DIRECTORY = REPOSITORY_ROOT / "examples" / "datasets"

EXAMPLE_SUMMARY = (
    "A gallery of charts for beginners: plot straight lines, parabolas, sine waves and logarithms, then try pie, box, "
    "stacked bar, error bar and vector charts."
)

EXAMPLE_DESCRIPTION = """\
## About this example

This project is a tour of the chart types PandaPlot can draw. It starts with the graphs of familiar \
mathematical functions and then moves on to charts for everyday data. Every chart sits in a folder next to its data, \
so you can click a dataset, look at the table and see how the chart uses it.

## What is inside

- **Linear**, **Quadratic**, **Periodic** and **Logarithm** folders: small tables for y = x + 4 style lines, \
parabolas, a sine wave and a natural logarithm, each with a chart. The **Periodic** chart also draws the sine curve \
as a fit line over the data points.
- **Vector** folder: a grid of arrows, drawn as a flat 2D chart and as a 3D chart.
- **Percentage** folder: a donut chart of sales by category, and a **Distribution** subfolder with a box plot \
of six samples: a control group, two treatments, a skewed sample, a sample with blank cells and a very small sample.
- **Measurements** folder: five repeated velocity readings for each nozzle size, a summary table with the mean \
and standard error, and a chart of the means with error bars.
- **Categorical** folder: a stacked bar chart of quarterly hardware and software revenue.
- A short **Start here** note.

## What you will learn

- Which chart type suits which kind of data.
- How a line, scatter, bar, pie or box chart reads the columns of a dataset.
- How to compare the same idea in different charts, for example one sine wave as points and as a curve.

## Where to start

Open **Start here**, then the **Quadratic** and **Periodic** charts.
"""

DATA_CREDIT = (
    "Synthetic data: the function tables are computed by this example's script, and the other datasets are the "
    "sample files in examples/datasets. None of it is real measurement data."
)

START_NOTE_CONTENT = """\
# Start here

Each folder in this project holds a dataset and a chart made from it.

1. Open **Linear**, **Quadratic** and **Periodic** to see the graphs of simple functions.
2. In **Periodic**, notice the dashed line: it is the curve y = sin(x) drawn over the data points.
3. Open **Percentage**, **Measurements** and **Categorical** to see pie, box, error bar and stacked bar charts.
4. Open **Vector** for arrows in two and three dimensions.

Click any dataset to see the table behind a chart.
"""

FEATURED_CHART_NAMES = ("Quadratic", "Periodic", "Sales by category")


def create_project_data_manager() -> ProjectDataManager:
    """Create a manager capable of saving every item type used here."""
    factory = ItemDataManagerFactory()
    for name, item_class, manager in (
        ("note", Note, NoteDataManager()),
        ("folder", Folder, FolderDataManager()),
        ("chart", Chart, ChartDataManager()),
        ("dataset", Dataset, DatasetDataManager()),
    ):
        factory.register(type_name=name, item_class=item_class, manager=manager, extension=name)
    return ProjectDataManager(factory)


def _build_series(
    chart: Chart, dataset: Dataset, *, x_column: str | None, y_column: str, label: str, alpha: float = 1.0, **style_options: Any,
) -> None:
    """Add one series reading ``y_column`` (and ``x_column`` when given) of ``dataset`` to ``chart``.

    ``style_options`` are passed to ``build_series_style``.
    """
    chart.add_data_series(
        dataset_id=dataset.id,
        x_column_id=(dataset.column_id(x_column) or "") if x_column else "",
        y_column_id=dataset.column_id(y_column) or "",
        x_column=x_column or "",
        y_column=y_column,
        label=label,
        alpha=alpha,
        style=build_series_style(chart.chart_type.value, **style_options),
    )


def _new_chart(name: str, chart_type: str, *, title: str, x_label: str = "", y_label: str = "") -> Chart:
    chart = Chart(name=name, chart_type=chart_type)
    chart.config.title = title
    chart.config.x.label = x_label
    chart.config.y.label = y_label
    return chart


def _function_tables() -> dict[str, pd.DataFrame]:
    """Compute the small function tables that the first four folders plot."""
    t_linear = np.arange(1.0, 9.0)
    t_quadratic = np.array([-4.0, -2.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    t_periodic = np.arange(1.0, 17.0)
    v_logarithm = np.arange(1.0, 11.0)
    positive = np.arange(1.0, 9.0)
    return {
        "linear": pd.DataFrame({"t": t_linear, "x": t_linear + 4.0, "y": 2.0 * t_linear - 3.0}),
        "quadratic": pd.DataFrame({"t": t_quadratic, "x": t_quadratic**2, "y": 5.0 - t_quadratic**2}),
        "positive": pd.DataFrame({"x": positive, "y": positive**2}),
        "periodic": pd.DataFrame({"t": t_periodic, "sin": np.sin(t_periodic)}),
        "logarithm": pd.DataFrame({"v": v_logarithm, "log_v": np.log(v_logarithm)}),
    }


def _add_function_folders(project: Project) -> dict[str, Chart]:
    """Add the Linear, Quadratic, Periodic and Logarithm folders and return their charts by name."""
    tables = _function_tables()
    charts: dict[str, Chart] = {}

    linear_folder = Folder(name="Linear")
    project.add_item(linear_folder)
    linear_data = Dataset(name="Linear data", data=tables["linear"])
    project.add_item(linear_data, linear_folder.id)
    chart = _new_chart("Linear", "line", title="Linear functions", x_label="Time [s]", y_label="Position [cm]")
    _build_series(chart, linear_data, x_column="t", y_column="x", label="x vs t", color="#1f77b4", alpha=0.66)
    _build_series(chart, linear_data, x_column="t", y_column="y", label="y vs t", color="#d62728", alpha=0.33)
    for series, marker in zip(chart.data_series, ("circle", "square"), strict=True):
        series.style.marker = MarkerStyle(marker_style=marker)
    project.add_item(chart, linear_folder.id)
    charts[chart.name] = chart

    quadratic_folder = Folder(name="Quadratic")
    project.add_item(quadratic_folder)
    quadratic_data = Dataset(name="Quadratic data", data=tables["quadratic"])
    positive_data = Dataset(name="Positive quadratic data", data=tables["positive"])
    project.add_item(quadratic_data, quadratic_folder.id)
    chart = _new_chart("Quadratic", "scatter", title="Quadratic", x_label="t", y_label="Value")
    _build_series(chart, quadratic_data, x_column="t", y_column="x", label="x = t²", color="#aa0000")
    _build_series(chart, quadratic_data, x_column="t", y_column="y", label="y = 5 - t²", color="#5500ff")
    project.add_item(chart, quadratic_folder.id)
    charts[chart.name] = chart
    project.add_item(positive_data, quadratic_folder.id)
    chart = _new_chart("Positive quadratic", "scatter", title="Positive quadratic", x_label="x", y_label="y")
    _build_series(chart, positive_data, x_column="x", y_column="y", label="y = x²", color="#aa0000")
    chart.data_series[0].style.marker = MarkerStyle(marker_style="triangle")
    project.add_item(chart, quadratic_folder.id)
    charts[chart.name] = chart

    periodic_folder = Folder(name="Periodic")
    project.add_item(periodic_folder)
    periodic_data = Dataset(name="Periodic data", data=tables["periodic"])
    project.add_item(periodic_data, periodic_folder.id)
    chart = _new_chart("Periodic", "scatter", title="Sine wave", x_label="t", y_label="sin(t)")
    _build_series(chart, periodic_data, x_column="t", y_column="sin", label="data", color="#1f77b4")
    chart.data_series[0].style.marker = MarkerStyle(marker_style="diamond")
    x_curve = np.linspace(1.0, 16.0, 300)
    chart.add_fit_series(
        source_dataset_id=periodic_data.id,
        x_data=x_curve,
        y_data=np.sin(x_curve),
        label="y = sin(x)",
        style=FitStyle(
            color="#00cccc", line_style="dashed", line_width=1.5,
            fit_type="Custom Function", fit_params={"a": 1.0, "b": 1.0},
        ),
        source_x_column_id=periodic_data.column_id("t") or "",
        source_y_column_id=periodic_data.column_id("sin") or "",
        source_x_column="t",
        source_y_column="sin",
    )
    project.add_item(chart, periodic_folder.id)
    charts[chart.name] = chart

    logarithm_folder = Folder(name="Logarithm")
    project.add_item(logarithm_folder)
    logarithm_data = Dataset(name="Logarithm data", data=tables["logarithm"])
    project.add_item(logarithm_data, logarithm_folder.id)
    chart = _new_chart("Logarithm", "scatter", title="Natural logarithm", x_label="v", y_label="ln(v)")
    _build_series(chart, logarithm_data, x_column="v", y_column="log_v", label="ln(v)", color="#1f77b4")
    project.add_item(chart, logarithm_folder.id)
    charts[chart.name] = chart
    return charts


def _add_vector_folder(project: Project) -> dict[str, Chart]:
    folder = Folder(name="Vector")
    project.add_item(folder)
    data = pd.read_csv(DATASETS_DIRECTORY / "sample_vector_field_3d_data.csv")
    dataset = Dataset(name="Vector field data", data=data)
    project.add_item(dataset, folder.id)
    columns = {name: dataset.column_id(name) or "" for name in data.columns}
    charts: dict[str, Chart] = {}

    chart = _new_chart("Vector field (2D)", "vector", title="Vector field (2D)", x_label="x", y_label="y")
    _build_series(
        chart, dataset, x_column="x", y_column="y", label="Vectors",
        color="#1f77b4", u_column_id=columns["u"], v_column_id=columns["v"], magnitude_column_id=columns["magnitude"],
    )
    project.add_item(chart, folder.id)
    charts[chart.name] = chart

    chart = _new_chart("Vector field (3D)", "vector3d", title="Vector field (3D)", x_label="x", y_label="y")
    _build_series(
        chart, dataset, x_column="x", y_column="y", label="Vectors", color="#1f77b4",
        u_column_id=columns["u"], v_column_id=columns["v"], w_column_id=columns["w"],
        magnitude_column_id=columns["magnitude"], z_column_id=columns["z"],
    )
    project.add_item(chart, folder.id)
    charts[chart.name] = chart
    return charts


def _add_percentage_folder(project: Project) -> dict[str, Chart]:
    folder = Folder(name="Percentage")
    project.add_item(folder)
    pie_data = pd.read_csv(DATASETS_DIRECTORY / "pie_test.csv")
    pie_dataset = Dataset(name="Category sales data", data=pie_data)
    project.add_item(pie_dataset, folder.id)
    charts: dict[str, Chart] = {}

    chart = _new_chart("Sales by category", "pie", title="Sales by category")
    chart.config.legend_position = "custom"
    chart.config.legend_custom_x = 1.0
    chart.config.legend_custom_y = 0.2
    style = build_series_style("pie", label_column_id=pie_dataset.column_id("Category") or "")
    style.start_angle = 83.0
    style.donut_width = 0.66
    chart.add_data_series(
        dataset_id=pie_dataset.id, y_column_id=pie_dataset.column_id("Share_Pct") or "", y_column="Share_Pct",
        label="Share of sales (%)", style=style,
    )
    project.add_item(chart, folder.id)
    charts[chart.name] = chart

    distribution = Folder(name="Distribution")
    project.add_item(distribution, folder.id)
    box_data = pd.read_csv(DATASETS_DIRECTORY / "box_plot_test.csv")
    box_dataset = Dataset(name="Treatment data", data=box_data)
    project.add_item(box_dataset, distribution.id)
    chart = _new_chart("Treatment comparison", "box", title="Treatment comparison", y_label="Value")
    for index, column in enumerate(box_data.columns):
        _build_series(chart, box_dataset, x_column=None, y_column=column, label=column, color=_BOX_COLORS[index])
    project.add_item(chart, distribution.id)
    charts[chart.name] = chart
    return charts


_BOX_COLORS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b")


def _add_measurements_folder(project: Project) -> dict[str, Chart]:
    folder = Folder(name="Measurements")
    project.add_item(folder)
    data = pd.read_csv(DATASETS_DIRECTORY / "data_automatic_error_analysis.txt", sep="\t")
    raw = Dataset(name="Velocity readings", data=data)
    velocity_columns = [column for column in data.columns if column.startswith("Velocity")]
    raw.set_column_roles(
        {raw.column_id("Nozzle_Area") or "": ColumnRole.CONTROLLED}
        | {raw.column_id(column) or "": ColumnRole.MEASURED for column in velocity_columns}
    )
    raw.set_column_measurement_groups({raw.column_id(column) or "": "Velocity" for column in velocity_columns})
    project.add_item(raw, folder.id)

    summary_table = MeasurementAnalysisService.summarize(raw).table
    summary = Dataset(name="Velocity readings - Measurement Summary", data=summary_table)
    project.add_item(summary, folder.id)

    chart = _new_chart(
        "Mean velocity by nozzle area", "scatter", title="Mean velocity by nozzle area",
        x_label="Nozzle area", y_label="Mean velocity",
    )
    error_bars = ErrorBarConfig(
        y_error_column_id=summary.column_id("Standard error") or "", y_error_column="Standard error",
    )
    _build_series(chart, summary, x_column="Nozzle_Area", y_column="Mean", label="Mean", color="#1f77b4", error_bars=error_bars)
    project.add_item(chart, folder.id)
    return {chart.name: chart}


def _add_categorical_folder(project: Project) -> dict[str, Chart]:
    folder = Folder(name="Categorical")
    project.add_item(folder)
    data = pd.read_csv(DATASETS_DIRECTORY / "stacked_bar_test.csv")
    dataset = Dataset(name="Quarterly revenue data", data=data)
    project.add_item(dataset, folder.id)
    chart = _new_chart("Quarterly revenue", "stacked_bar", title="Quarterly revenue", x_label="Quarter", y_label="Revenue")
    for column, color in (("Hardware", "#1f77b4"), ("Software", "#ff7f0e")):
        _build_series(chart, dataset, x_column="Quarter", y_column=column, label=column, color=color)
    project.add_item(chart, folder.id)
    return {chart.name: chart}


def create_functions_project(output_directory: Path | None = None) -> Path:
    """Build the Functions project, save it and return the path of the .pplot file.

    Args:
        output_directory: Where to save ``Functions.pplot``; defaults to this script's folder.

    Returns:
        Path of the saved project file.
    """
    output_directory = Path(output_directory) if output_directory is not None else Path(__file__).resolve().parent
    output_directory.mkdir(parents=True, exist_ok=True)

    project = Project(name="Functions", description=EXAMPLE_DESCRIPTION)
    start_note = Note(name="Start here", content=START_NOTE_CONTENT)
    project.add_item(start_note)

    charts: dict[str, Chart] = {}
    for add_folders in (
        _add_function_folders, _add_vector_folder, _add_percentage_folder, _add_measurements_folder, _add_categorical_folder,
    ):
        charts.update(add_folders(project))

    project.example_info = ExampleInfo(
        is_example=True,
        summary=EXAMPLE_SUMMARY,
        section=ExampleSection.CHARTS,
        level=ExampleLevel.BEGINNER,
        tag_ids=("mathematics", "charts"),
        featured_chart_ids=tuple(charts[name].id for name in FEATURED_CHART_NAMES),
        start_note_id=start_note.id,
        data_credit=DATA_CREDIT,
    )

    path = output_directory / "Functions.pplot"
    create_project_data_manager().save(project, str(path))
    print(f"Saved project: {path}")
    return path


if __name__ == "__main__":
    create_functions_project()
