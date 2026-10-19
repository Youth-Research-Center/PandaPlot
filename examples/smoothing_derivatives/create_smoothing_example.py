"""Generate a noisy-signal project using the Analysis panel's engine."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from pandaplot.analysis.analysis_engine import AnalysisEngine
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Folder, Note
from pandaplot.models.project.items.chart import DataSeries
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager

WINDOW_LENGTH = 51
POLYNOMIAL_ORDER = 3


def create_project_data_manager() -> ProjectDataManager:
    factory = ItemDataManagerFactory()
    for name, item_class, manager in (
        ("note", Note, NoteDataManager()),
        ("folder", Folder, FolderDataManager()),
        ("chart", Chart, ChartDataManager()),
        ("dataset", Dataset, DatasetDataManager()),
    ):
        factory.register(type_name=name, item_class=item_class, manager=manager, extension=name)
    return ProjectDataManager(factory)


def create_signal_data() -> pd.DataFrame:
    """Use a fixed seed so rerunning the example gives the same signal."""
    time = np.linspace(0, 10, 501)
    clean = np.sin(2 * np.pi * 0.3 * time) + 0.25 * np.sin(2 * np.pi * 0.7 * time)
    data = pd.DataFrame({"Time (s)": time, "Clean signal": clean})
    data["Noisy signal"] = clean + np.random.default_rng(452).normal(0, 0.18, len(time))
    data["Smoothed signal"] = AnalysisEngine.smooth_data(
        data["Time (s)"], data["Noisy signal"], method="savgol",
        window_length=WINDOW_LENGTH, polynomial_order=POLYNOMIAL_ORDER,
    ).result_data
    data["First derivative"] = AnalysisEngine.calculate_derivative(
        data["Time (s)"], data["Smoothed signal"], method="central",
    ).result_data
    data["Clean derivative"] = 0.6 * np.pi * np.cos(0.6 * np.pi * time) + 0.35 * np.pi * np.cos(1.4 * np.pi * time)
    return data


def create_smoothing_project(output_directory: Path | None = None) -> Path:
    output_directory = Path(output_directory) if output_directory is not None else Path(__file__).resolve().parent
    output_directory.mkdir(parents=True, exist_ok=True)
    data = create_signal_data()
    project = Project(name="Smoothing and Derivatives", description="Savitzky-Golay smoothing before numerical differentiation.")
    folder = Folder(name="Signal Analysis")
    project.add_item(folder)
    dataset = Dataset(name="Noisy periodic signal", data=data)
    project.add_item(dataset, folder.id)

    panels = (
        ("1. Raw noisy data", "Signal", (("Noisy signal", "#8b97a2"), ("Clean signal", "#253746"))),
        ("2. Savitzky-Golay smoothing", "Signal", (("Smoothed signal", "#176b73"), ("Clean signal", "#253746"))),
        ("3. First derivative of smoothed data", "Signal / s", (("First derivative", "#bc4052"), ("Clean derivative", "#253746"))),
    )
    figure = Figure(figsize=(11, 10), layout="constrained")
    FigureCanvasAgg(figure)
    figure.suptitle(f"Smoothing before differentiation: window {WINDOW_LENGTH}, polynomial order {POLYNOMIAL_ORDER}", fontsize=15)
    axes = figure.subplots(3, 1)
    for axis, (title, ylabel, series) in zip(axes, panels, strict=True):
        chart = Chart(name=title, chart_type="line")
        chart.config.title = title
        chart.config.x.label = "Time (s)"
        chart.config.y.label = ylabel
        for column, color in series:
            chart.data_series.append(DataSeries(
                dataset_id=dataset.id, x_column="Time (s)", y_column=column,
                x_column_id=dataset.column_id("Time (s)") or "",
                y_column_id=dataset.column_id(column) or "", label=column,
                series_type=SeriesType.LINE, style=LineSeriesStyle(color=color),
            ))
            axis.plot(data["Time (s)"], data[column], color=color, linewidth=1.5, label=column)
        project.add_item(chart, folder.id)
        axis.set_title(title, loc="left")
        axis.set_xlabel("Time (s)")
        axis.set_ylabel(ylabel)
        axis.grid(visible=True, alpha=0.25)
        axis.legend(loc="upper right", frameon=False)

    note = Note(name="How to reproduce and adjust the analysis")
    note.content = (
        "This example uses a reproducible noisy periodic signal (seed 452). The clean signal and its analytical "
        "derivative are references, not measurements.\n\n"
        "Select the raw chart's Noisy signal series. In the Analysis panel, choose Smoothing, then Savitzky-Golay, "
        "window length 51 and polynomial order 3. Apply it to the full range. Select the resulting smoothed series "
        "and choose Derivative with the Central method. The generator uses the same AnalysisEngine operations.\n\n"
        "Window length is a number of samples. With samples 0.02 seconds apart, 51 samples cover 1 second from "
        "first to last. A longer window removes more noise but can flatten short features; a shorter window "
        "preserves detail but leaves more noise. Use an odd window no longer than the data.\n\n"
        "Polynomial order controls the local curve fitted within each window. Higher orders can preserve "
        "curvature but can also retain more noise. It must be smaller than the window length. Try windows 21, 51 "
        "and 101 with order 3, then compare orders 2 and 4 with window 51.\n\n"
        "Differentiation amplifies noise, so smooth first. The derivative still differs from the clean reference, "
        "especially near the endpoints, where smoothing uses edge interpolation and the central method uses "
        "one-sided differences. Avoid interpreting endpoint artifacts as real features."
    )
    project.add_item(note, folder.id)
    path = output_directory / "smoothing_derivatives.pplot"
    create_project_data_manager().save(project, str(path))
    figure.savefig(output_directory / "smoothing_derivatives.png", dpi=140)
    print(f"Saved project: {path}")
    return path


if __name__ == "__main__":
    create_smoothing_project()
