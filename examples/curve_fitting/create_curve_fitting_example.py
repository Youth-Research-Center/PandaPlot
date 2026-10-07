"""Generate a project demonstrating curve fits on the bundled example data."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style.scatter import ScatterSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Folder, Note
from pandaplot.models.project.items.chart import DataSeries, FitData
from pandaplot.services.fit.fit_service import FitResult, FitService
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager


@dataclass(frozen=True)
class FitExample:
    filename: str
    dataset_name: str
    fit_type: str
    explanation: str
    custom_function: str | None = None
    custom_parameters: str | None = None
    fixed_parameters: str | None = None
    uncertainty_column: str | None = None


FIT_EXAMPLES = (
    FitExample(
        filename="f_x_4.2x_minus_2.3.csv",
        dataset_name="Linear: 4.2x - 2.3",
        fit_type="Linear",
        explanation=(
            "A straight-line model is appropriate because the values change at a constant rate. "
            "The fitted slope and intercept recover the relationship y = 4.2x - 2.3."
        ),
    ),
    FitExample(
        filename="errorbars-linear.csv",
        dataset_name="Noisy linear data with uncertainties",
        fit_type="Linear",
        uncertainty_column="std",
        explanation=(
            "A straight line captures the overall trend. The fit is weighted by the supplied "
            "standard deviations, so measurements with smaller uncertainty have more influence."
        ),
    ),
    FitExample(
        filename="f_x_spring.csv",
        dataset_name="Spring response",
        fit_type="Quadratic",
        explanation=(
            "A quadratic model captures the smooth curvature in this spring-response dataset, "
            "where a straight line would miss the gradual change in slope."
        ),
    ),
    FitExample(
        filename="f_x_spring-cos.csv",
        dataset_name="Spring response: cosine",
        fit_type="Custom Function",
        custom_function="a*cos(b*x+c)",
        custom_parameters="a,b,c",
        fixed_parameters="c=0",
        explanation=(
            "A cosine model is appropriate because the measurements oscillate periodically. "
            "The phase is fixed at zero to match the dataset's starting point."
        ),
    ),
    FitExample(
        filename="f_x_spring-cos-damped.csv",
        dataset_name="Spring response: damped cosine",
        fit_type="Custom Function",
        custom_function="a*exp(-b*x)*cos(c*x+d)",
        custom_parameters="a,b,c,d",
        fixed_parameters="a=1,d=0",
        explanation=(
            "A damped cosine describes oscillations whose amplitude gradually shrinks. "
            "The initial amplitude and phase are fixed to the observed starting point."
        ),
    ),
    FitExample(
        filename="f_x_spring-cos-damped2.csv",
        dataset_name="Spring response: second damped cosine",
        fit_type="Custom Function",
        custom_function="a*exp(-b*x)*cos(c*x+d)",
        custom_parameters="a,b,c,d",
        fixed_parameters="a=1,d=0",
        explanation=(
            "This dataset also oscillates while its amplitude decays, so the damped-cosine model "
            "is a natural choice. Its decay rate is fitted independently of the other example."
        ),
    ),
)


def create_project_data_manager() -> ProjectDataManager:
    """Create a manager capable of saving every item type used here."""
    factory = ItemDataManagerFactory()
    factory.register(type_name="note", item_class=Note, manager=NoteDataManager(), extension="note")
    factory.register(type_name="folder", item_class=Folder, manager=FolderDataManager(), extension="folder")
    factory.register(type_name="chart", item_class=Chart, manager=ChartDataManager(), extension="chart")
    factory.register(type_name="dataset", item_class=Dataset, manager=DatasetDataManager(), extension="dataset")
    return ProjectDataManager(factory)


def _fit_dataset(dataset: Dataset, example: FitExample, fit_service: FitService) -> FitResult:
    x_values = dataset.data["x"].to_numpy(dtype=float)
    y_column = "y" if "y" in dataset.data.columns else "f(x)"
    y_values = dataset.data[y_column].to_numpy(dtype=float)
    sigma_y = (
        dataset.data[example.uncertainty_column].to_numpy(dtype=float)
        if example.uncertainty_column is not None
        else None
    )

    result = fit_service.perform_fit(
        example.fit_type,
        x_values,
        y_values,
        confidence_bands=True,
        sigma_y=sigma_y,
        custom_function=example.custom_function,
        custom_parameters=example.custom_parameters,
        fixed_parameters=example.fixed_parameters,
    )
    if result is None:
        raise RuntimeError(f"Fit service returned no result for {example.dataset_name}.")
    return result


def _save_preview(
    preview_items: list[tuple[FitExample, pd.DataFrame, FitResult]],
    output_path: Path,
) -> None:
    """Save a six-panel PNG preview of the fitted datasets."""
    figure = Figure(figsize=(13, 11), layout="constrained", facecolor="#f7f8fa")
    FigureCanvasAgg(figure)
    figure.suptitle("Curve fitting examples", fontsize=20, fontweight="bold", color="#17212b")
    axes = figure.subplots(3, 2)

    for axis, (example, data, result) in zip(axes.flat, preview_items, strict=True):
        x_values = data["x"].to_numpy(dtype=float)
        y_column = "y" if "y" in data.columns else "f(x)"
        y_values = data[y_column].to_numpy(dtype=float)
        if example.uncertainty_column is not None:
            axis.errorbar(
                x_values,
                y_values,
                yerr=data[example.uncertainty_column].to_numpy(dtype=float),
                fmt="o",
                markersize=3.5,
                color="#176b73",
                ecolor="#8da7aa",
                capsize=2,
                linewidth=0.8,
                label="Measured data ± 1σ",
            )
        else:
            axis.scatter(x_values, y_values, s=16, color="#176b73", label="Measured data", zorder=3)

        axis.plot(result.x_fit, result.y_fit, color="#d1495b", linewidth=2, label="Fitted curve")
        if result.confidence_lower is not None and result.confidence_upper is not None:
            axis.fill_between(
                result.x_fit,
                result.confidence_lower,
                result.confidence_upper,
                color="#d1495b",
                alpha=0.16,
                linewidth=0,
                label="95% confidence band",
            )

        axis.set_title(example.dataset_name, loc="left", fontsize=11, fontweight="bold", color="#17212b")
        if result.r_squared is not None:
            axis.set_title(f"R² = {result.r_squared:.4f}", loc="right", fontsize=9, color="#344451")
        axis.set_xlabel("x")
        axis.set_ylabel(y_column)
        axis.grid(visible=True, color="#cbd2d9", alpha=0.55, linewidth=0.7)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.tick_params(colors="#4b5966")
        axis.legend(frameon=False, fontsize=8, loc="best")

    figure.savefig(output_path, dpi=170, facecolor=figure.get_facecolor())


def create_curve_fitting_project() -> Path:
    """Fit each bundled dataset, save the project, and return its path."""
    project = Project(
        name="Curve Fitting Examples",
        description="Six examples of choosing and applying curve-fit models.",
    )
    examples_folder = Folder(name="Datasets, Charts, and Fit Notes")
    project.add_item(examples_folder)
    fit_service = FitService()
    preview_items: list[tuple[FitExample, pd.DataFrame, FitResult]] = []

    for example in FIT_EXAMPLES:
        data_path = REPOSITORY_ROOT / "examples" / "fit-test-data" / example.filename
        data = pd.read_csv(data_path)
        dataset = Dataset(name=example.dataset_name, data=data)
        project.add_item(dataset, examples_folder.id)

        x_column = "x"
        y_column = "y" if "y" in data.columns else "f(x)"
        result = _fit_dataset(dataset, example, fit_service)
        preview_items.append((example, data, result))

        chart = Chart(name=f"{example.dataset_name} Fit", chart_type="scatter")
        chart.config.title = f"{example.dataset_name}: {example.fit_type} fit"
        chart.config.x.label = x_column
        chart.config.y.label = y_column
        error_bars = ErrorBarConfig()
        if example.uncertainty_column is not None:
            error_bars.y_error_column_id = dataset.column_id(example.uncertainty_column) or ""
            error_bars.y_error_column = example.uncertainty_column
        chart.data_series.append(
            DataSeries(
                dataset_id=dataset.id,
                x_column=x_column,
                y_column=y_column,
                x_column_id=dataset.column_id(x_column) or "",
                y_column_id=dataset.column_id(y_column) or "",
                label="Measured data",
                series_type=SeriesType.SCATTER,
                style=ScatterSeriesStyle(error_bars=error_bars),
            )
        )
        chart.fit_data.append(
            FitData(
                source_dataset_id=dataset.id,
                source_x_column_id=dataset.column_id(x_column) or "",
                source_y_column_id=dataset.column_id(y_column) or "",
                source_x_column=x_column,
                source_y_column=y_column,
                fit_type=example.fit_type,
                x_data=result.x_fit,
                y_data=result.y_fit,
                label=result.equation or f"{example.fit_type} fit",
                fit_params={name: float(value) for name, value in result.params.items()},
                fit_stats={
                    "equation": result.equation,
                    "r_squared": float(result.r_squared) if result.r_squared is not None else None,
                    "parameter_errors": result.errors.tolist(),
                },
                confidence_lower=result.confidence_lower,
                confidence_upper=result.confidence_upper,
                style=FitStyle(color="#d1495b", line_style="solid", line_width=2.0),
            )
        )
        project.add_item(chart, examples_folder.id)

        note = Note(name=f"Fit note: {example.dataset_name}")
        parameter_summary = ", ".join(
            f"{name} = {value:.6g}" for name, value in result.params.items()
        )
        r_squared_summary = f"{result.r_squared:.6g}" if result.r_squared is not None else "not available"
        note.content = (
            f"Model: {example.fit_type}. {example.explanation}\n\n"
            f"Fitted equation: {result.equation}\n"
            f"Parameters: {parameter_summary}\n"
            f"R²: {r_squared_summary}"
        )
        project.add_item(note, examples_folder.id)

        print(f"Fitted {example.dataset_name}: R² = {result.r_squared!s}")

    output_path = Path(__file__).with_name("curve_fitting_examples.pplot")
    preview_path = Path(__file__).with_name("curve_fitting_examples.png")
    create_project_data_manager().save(project, str(output_path))
    _save_preview(preview_items, preview_path)
    print(f"Saved project: {output_path}")
    print(f"Saved plot preview: {preview_path}")
    return output_path


if __name__ == "__main__":
    create_curve_fitting_project()