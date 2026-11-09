"""Sidebar panel titles are plain text; the icon comes from each panel's `ICON_NAME`."""

import importlib
import re
from pathlib import Path

import pytest

from pandaplot.gui.resources.icon_library import icon_svg

PANELS_DIR = Path(__file__).resolve().parents[3] / "pandaplot" / "gui" / "components" / "sidebar"

# (module, class name, title, icon name)
PANEL_TITLES = [
    ("project.project_view_panel", "ProjectViewPanel", "Project Explorer", "folder"),
    ("search.search_panel", "SearchPanel", "Search Notes", "magnifying-glass"),
    ("transform.transform_panel", "TransformPanel", "Transform Operations", "wrench"),
    ("preprocessing.preprocessing_panel", "PreprocessingPanel", "Preprocessing", "sliders-horizontal"),
    ("analysis.analysis_panel", "AnalysisPanel", "Analysis Operations", "chart-bar"),
    ("statistics.descriptive_panel", "DescriptiveStatsPanel", "Descriptive Statistics", "table"),
    ("statistics.statistics_panel", "StatisticsPanel", "Statistical Tests", "flask"),
    ("signal.signal_panel", "SignalPanel", "Signal Analysis", "waveform"),
    ("chart.chart_properties_panel", "ChartPropertiesPanel", "Chart Properties", "chart-line"),
    ("fit.fit_panel", "FitPanel", "Curve Fitting", "function"),
    ("chart_analysis.chart_analysis_panel", "ChartAnalysisPanel", "Chart Analysis", "calculator"),
    ("chart_signal.chart_signal_analysis_panel", "ChartSignalAnalysisPanel", "Chart Signal Analysis", "waveform"),
    ("chart_transform.chart_transform_panel", "ChartTransformPanel", "Chart Transform", "wrench"),
]

SET_TITLE_CALL = re.compile(r"self\._set_title\(\s*(['\"])(?P<text>.*?)\1")


def _panel_class(module: str, class_name: str) -> type:
    return getattr(importlib.import_module(f"pandaplot.gui.components.sidebar.{module}"), class_name)


@pytest.mark.parametrize(("module", "class_name", "title", "icon"), PANEL_TITLES)
def test_panel_declares_its_icon(module: str, class_name: str, title: str, icon: str) -> None:
    panel_class = _panel_class(module, class_name)

    assert panel_class.ICON_NAME == icon
    assert icon_svg(icon)


@pytest.mark.parametrize(("module", "class_name", "title", "icon"), PANEL_TITLES)
def test_panel_title_text_is_plain(module: str, class_name: str, title: str, icon: str) -> None:
    source = (PANELS_DIR / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")

    titles = [match.group("text") for match in SET_TITLE_CALL.finditer(source)]

    assert titles == [title]


def test_no_set_title_call_carries_an_emoji() -> None:
    offenders = []
    for path in PANELS_DIR.rglob("*.py"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = SET_TITLE_CALL.search(line)
            if match and not match.group("text").isascii():
                offenders.append(f"{path.name}:{line_number}")

    assert offenders == []
